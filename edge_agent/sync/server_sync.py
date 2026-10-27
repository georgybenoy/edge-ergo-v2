"""
Edge-to-Server Synchronization Client (PRD §40, §41, §42, §43, §47).

Drains the local sync_queue and POSTs anonymized telemetry-window
JSON summaries to the Central Server. Falls back gracefully when
the server is unreachable — summaries stay queued and are retried
with exponential backoff.

Privacy invariant:
  Only the telemetry window JSON summary shape is ever transmitted;
  NEVER raw frames, face crops, or landmark coordinates.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Optional, Tuple, Union
import uuid

import httpx

from edge_agent.camera.camera import list_available_cameras
from edge_agent.config.config_manager import ConfigManager, EdgeConfig
from edge_agent.storage.local_db import LocalDatabase

logger = logging.getLogger(__name__)


# ── Exponential Backoff Calculator ───────────────────────────────────────────

def compute_backoff_delay(
    retry_count: int,
    base_sec: float = 2.0,
    max_sec: float = 300.0,
) -> float:
    """Compute exponential backoff delay in seconds with a sanity cap.

    Formula: min(base_sec * (2 ** retry_count), max_sec)
    """
    if retry_count <= 0:
        return 0.0
    delay = base_sec * (2 ** (retry_count - 1))
    return float(min(delay, max_sec))


# ── Telemetry Window Payload Builder ──────────────────────────────────────────

def build_telemetry_window_payload(
    session: dict[str, Any],
    assessment: Optional[dict[str, Any]],
    events: list[dict[str, Any]],
    device_id: str,
) -> dict[str, Any]:
    """Construct the exact anonymized Telemetry Window JSON from local DB rows.

    Specification:
    {
      "device_id": "NODE-004",
      "session_id": "S-20260914-001",
      "window_start": "2026-09-14T10:00:00",
      "window_end": "2026-09-14T10:05:00",
      "ergonomics": {
        "average_rula": 4.2, "maximum_rula": 6,
        "average_reba": 5.1, "maximum_reba": 7,
        "high_risk_percentage": 32.5, "dominant_posture": "NECK_FLEXION"
      },
      "facial_expression": {
        "neutral_percentage": 72, "positive_percentage": 15,
        "negative_percentage": 8, "reduced_expression_percentage": 5
      },
      "breaks": { "breaks_recommended": 1, "breaks_acknowledged": 0 }
    }
    """
    assess = assessment or {}
    rula = float(assess.get("rula_score", 1.0))
    reba = float(assess.get("reba_score", 1.0))
    risk_level = str(assess.get("risk_level", "LOW"))
    dominant = str(assess.get("dominant_posture", "NEUTRAL"))

    # High risk percentage
    high_risk_pct = 100.0 if risk_level in ("HIGH", "VERY_HIGH") else 0.0

    # Count break events from session events
    break_events = sum(
        1 for e in events
        if "BREAK" in str(e.get("event_type", "")).upper()
        or "BREAK" in str(e.get("event_value", "")).upper()
    )

    # Expression distribution
    expr_cat = str(assess.get("expression_category", "Neutral")).lower()
    facial_expression = {
        "neutral_percentage": 100 if "neutral" in expr_cat else 0,
        "positive_percentage": 100 if "positive" in expr_cat else 0,
        "negative_percentage": 100 if "negative" in expr_cat else 0,
        "reduced_expression_percentage": 100 if "reduced" in expr_cat else 0,
    }

    # Stable window id for duplicate prevention / idempotency
    start_time_clean = str(session.get("start_time", ""))
    window_id = f"{session.get('session_id')}_{start_time_clean}"

    formatted_events = []
    for ev in events:
        formatted_events.append({
            "event_id": str(ev.get("event_id") or uuid.uuid4()),
            "timestamp": str(ev.get("timestamp", start_time_clean)),
            "event_type": str(ev.get("event_type", "INFO")),
            "event_value": str(ev.get("event_value", "")),
        })

    payload = {
        "window_id": window_id,
        "device_id": device_id,
        "session_id": str(session.get("session_id", "")),
        "window_start": start_time_clean,
        "window_end": str(session.get("end_time", "")),
        "ergonomics": {
            "average_rula": float(max(1.0, min(7.0, round(rula, 2)))),
            "maximum_rula": int(max(1, min(7, round(rula)))),
            "average_reba": float(max(1.0, min(15.0, round(reba, 2)))),
            "maximum_reba": int(max(1, min(15, round(reba)))),
            "high_risk_percentage": float(max(0.0, min(100.0, high_risk_pct))),
            "dominant_posture": dominant,
        },
        "facial_expression": facial_expression,
        "breaks": {
            "breaks_recommended": break_events,
            "breaks_acknowledged": 0,
        },
    }
    if formatted_events:
        payload["events"] = formatted_events

    return payload


# ── ServerSync Class ──────────────────────────────────────────────────────────

class ServerSync:
    """Manages Edge-to-Server registration, telemetry window syncing, and config pulls."""

    def __init__(
        self,
        config_manager: ConfigManager,
        local_db: LocalDatabase,
        timeout_sec: float = 6.0,
    ) -> None:
        self.config_manager = config_manager
        self.local_db = local_db
        self.timeout_sec = timeout_sec
        self._is_syncing: bool = False

    def is_busy(self) -> bool:
        """Return True if an upload or synchronization operation is active."""
        return getattr(self, "_is_syncing", False)

    @property
    def server_url(self) -> str:
        return self.config_manager.config.server_url.rstrip("/")

    @property
    def device_id(self) -> str:
        return self.config_manager.config.device_id

    # ── Connection Test ───────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Test whether the Central Server is reachable."""
        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                # Probe server root or edge api docs/health
                res = client.get(f"{self.server_url}/api/v1/edge/config?probe=1")
                # Any response (even 400/404) proves network reachability to the server
                return res.status_code < 500
        except Exception:
            return False

    # ── First-Time Setup & Node Registration (PRD §42, §43) ───────────────────

    def register_node(
        self,
        device_name: str = "",
        camera_index: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Perform first-time Edge Node registration with Central Server.

        Steps:
          1. Detect camera availability.
          2. Call POST /api/v1/edge/register.
          3. Persist assigned NODE-xxx id in ConfigManager and LocalDatabase.

        Returns:
            (success: bool, device_id_or_error: str)
        """
        cfg = self.config_manager.config
        name = device_name or cfg.device_name or "Workstation-Node"
        cam_idx = camera_index if camera_index is not None else cfg.camera_index

        # 1. Camera detection check
        cameras = list_available_cameras(max_index=2)
        cam_detected = len(cameras) > 0 or cam_idx in cameras

        # 2. Server registration request
        endpoint = f"{self.server_url}/api/v1/edge/register"
        payload = {
            "device_name": name,
            "software_version": cfg.software_version,
            "camera_detected": cam_detected,
            "camera_index": cam_idx,
        }

        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.post(endpoint, json=payload)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    assigned_id = data.get("device_id")
                    if not assigned_id:
                        return False, "Server response missing 'device_id'"

                    # 3. Persist NODE-xxx id locally
                    self.config_manager.update(
                        {"device_id": assigned_id, "device_name": name},
                        save_to_disk=True,
                    )
                    self.local_db.register_device(
                        device_id=assigned_id,
                        device_name=name,
                        software_version=cfg.software_version,
                    )
                    logger.info("Successfully registered node: %s", assigned_id)
                    return True, assigned_id
                else:
                    msg = f"Registration failed with HTTP {resp.status_code}: {resp.text}"
                    logger.warning(msg)
                    return False, msg
        except httpx.RequestError as exc:
            msg = f"Registration connection failure to {endpoint}: {exc}"
            logger.warning(msg)
            return False, msg
        except Exception as exc:
            msg = f"Unexpected registration error: {exc}"
            logger.error(msg)
            return False, msg

    # ── Telemetry Upload & Sync Queue Drain (PRD §40) ─────────────────────────

    def sync_pending_telemetry(self, limit: int = 10) -> int:
        """Process pending sync_queue records and POST them to Central Server.

        PRD §40 flow:
          Connection Test -> Send Summary -> Server Validation -> Success -> Mark Synced.

        Returns:
            Number of records successfully uploaded and marked SYNCED.
        """
        device_id = self.device_id
        if not device_id:
            logger.debug("Sync skipped: Edge Node has no registered device_id.")
            return 0

        self._is_syncing = True
        try:
            pending_items = self.local_db.get_pending_sync_records(limit=limit)
            if not pending_items:
                return 0

            synced_count = 0
            endpoint = f"{self.server_url}/api/v1/edge/assessment"
            now_ts = time.time()
            cfg = self.config_manager.config

            for item in pending_items:
                sync_id = item["sync_id"]
                record_id = item["record_id"]
                retry_count = item["retry_count"]
                last_attempt_str = item["last_attempt"]

                # Exponential backoff check
                if last_attempt_str and retry_count > 0:
                    try:
                        last_attempt_dt = datetime.fromisoformat(last_attempt_str.replace("Z", "+00:00"))
                        last_attempt_sec = last_attempt_dt.timestamp()
                    except Exception:
                        last_attempt_sec = 0.0

                    backoff_delay = compute_backoff_delay(
                        retry_count=retry_count,
                        base_sec=cfg.backoff_base_sec,
                        max_sec=cfg.backoff_max_sec,
                    )
                    if (now_ts - last_attempt_sec) < backoff_delay:
                        logger.debug(
                            "Sync item %s in backoff window (retry=%d, wait=%.1fs); skipping.",
                            sync_id, retry_count, backoff_delay,
                        )
                        continue

                # Fetch session data from local DB
                session = self.local_db.get_session(record_id)
                if not session:
                    logger.warning("Session %s not found for sync_id %s; marking FAILED.", record_id, sync_id)
                    self.local_db.update_sync_status(sync_id, "FAILED")
                    continue

                assessment = self.local_db.get_latest_assessment(record_id)
                events = self.local_db.get_events_for_session(record_id)

                # Build Telemetry Window JSON payload
                payload = build_telemetry_window_payload(session, assessment, events, device_id)
                window_id = payload["window_id"]

                # Mark item IN_PROGRESS
                self.local_db.update_sync_status(sync_id, "IN_PROGRESS")

                # Upload to server
                headers = {
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": window_id,
                }

                try:
                    with httpx.Client(timeout=self.timeout_sec) as client:
                        resp = client.post(endpoint, json=payload, headers=headers)
                        if resp.status_code in (200, 201, 204, 409):
                            # 409 Conflict indicates server already has this idempotent window -> mark SYNCED
                            self.local_db.update_sync_status(sync_id, "SYNCED")
                            self.local_db.update_device_sync(device_id)
                            synced_count += 1
                            logger.info("Successfully synced telemetry window %s (sync_id %s)", window_id, sync_id)
                        else:
                            logger.warning("Server rejected telemetry window %s: HTTP %d", window_id, resp.status_code)
                            self.local_db.update_sync_status(sync_id, "PENDING", retry_increment=True)
                except (httpx.RequestError, Exception) as exc:
                    logger.debug("Network failure syncing window %s: %s", window_id, exc)
                    self.local_db.update_sync_status(sync_id, "PENDING", retry_increment=True)

            return synced_count
        finally:
            self._is_syncing = False

    # ── Remote Config Pull (PRD §16, §47) ─────────────────────────────────────

    def sync_remote_config(self) -> bool:
        """Fetch server-managed configuration overrides and merge locally."""
        if not self.device_id:
            return False

        endpoint = f"{self.server_url}/api/v1/edge/config"
        params = {"device_id": self.device_id}

        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.get(endpoint, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and data:
                        self.config_manager.update(data, save_to_disk=True)
                        for k, v in data.items():
                            self.local_db.set_config(k, v)
                        logger.info("Merged server config overrides: %s", list(data.keys()))
                        return True
        except Exception as exc:
            logger.debug("Config pull failed: %s", exc)

        return False


# ── Background Sync Worker ────────────────────────────────────────────────────

class SyncWorker:
    """Daemon background thread running periodic sync and config maintenance."""

    def __init__(
        self,
        server_sync: ServerSync,
        interval_sec: float = 30.0,
    ) -> None:
        self.server_sync = server_sync
        self.interval_sec = interval_sec
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_busy(self) -> bool:
        """Return True if background sync or ServerSync is active."""
        return getattr(self.server_sync, "is_busy", lambda: False)()

    def start(self) -> None:
        """Start the background sync loop."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="EdgeErgo-SyncWorker", daemon=True)
        self._thread.start()
        logger.info("Started SyncWorker (interval=%.1fs)", self.interval_sec)

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the background sync loop."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("SyncWorker stopped.")

    def trigger_now(self) -> int:
        """Trigger an immediate synchronous sync pass."""
        return self.server_sync.sync_pending_telemetry()

    def _run_loop(self) -> None:
        """Internal background loop."""
        # Initial run
        try:
            self.server_sync.sync_remote_config()
            self.server_sync.sync_pending_telemetry()
        except Exception as exc:
            logger.debug("Initial sync worker pass exception: %s", exc)

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self.interval_sec):
                break
            try:
                self.server_sync.sync_pending_telemetry()
            except Exception as exc:
                logger.debug("Periodic sync iteration exception: %s", exc)
