"""
Heartbeat client (PRD §46 Edge Agent Health Monitoring).

Periodically pings the Central Server with a lightweight heartbeat
(device_id, software_version, status) so the server and dashboard
track edge workstation availability.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class HeartbeatClient:
    """Sends periodic lightweight heartbeats to the Central Server.

    Runs in a dedicated background daemon thread to ensure non-blocking
    operation that never interrupts frame processing or overlay rendering.
    """

    def __init__(
        self,
        server_url: str,
        device_id: str,
        software_version: str = "0.1.0",
        interval_sec: float = 60.0,
        status_provider: Optional[Callable[[], str]] = None,
        timeout_sec: float = 5.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.device_id = device_id
        self.software_version = software_version
        self.interval_sec = interval_sec
        self.status_provider = status_provider or (lambda: "active")
        self.timeout_sec = timeout_sec

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_heartbeat_time: float = 0.0
        self._last_success: bool = False

    @property
    def is_running(self) -> bool:
        """Return True if background heartbeat loop is running."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_success(self) -> bool:
        """Return True if the most recent heartbeat attempt succeeded."""
        return self._last_success

    def send_heartbeat(self) -> bool:
        """Send a single heartbeat ping to POST /api/v1/edge/heartbeat.

        Returns True on HTTP 200/204 response, False on error or timeout.
        Never raises exceptions so caller loop never crashes.
        """
        if not self.device_id:
            logger.debug("Heartbeat skipped: device_id not set.")
            return False

        endpoint = f"{self.server_url}/api/v1/edge/heartbeat"
        status = self.status_provider()
        payload = {
            "device_id": self.device_id,
            "software_version": self.software_version,
            "status": status,
        }

        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                response = client.post(endpoint, json=payload)
                if response.status_code in (200, 204):
                    logger.debug("Heartbeat sent successfully to %s: %s", endpoint, status)
                    self._last_success = True
                    self._last_heartbeat_time = time.time()
                    return True
                else:
                    logger.warning("Heartbeat returned status %d from %s", response.status_code, endpoint)
                    self._last_success = False
                    return False
        except httpx.RequestError as exc:
            logger.debug("Heartbeat failed (server unreachable at %s): %s", endpoint, exc)
            self._last_success = False
            return False
        except Exception as exc:
            logger.error("Unexpected error during heartbeat: %s", exc)
            self._last_success = False
            return False

    def start(self) -> None:
        """Start periodic heartbeat loop in background daemon thread."""
        if self.is_running:
            logger.warning("HeartbeatClient is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="EdgeErgo-Heartbeat", daemon=True)
        self._thread.start()
        logger.info("Started heartbeat service targeting %s (every %.1fs)", self.server_url, self.interval_sec)

    def stop(self, timeout: float = 2.0) -> None:
        """Stop background heartbeat thread."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("Heartbeat service stopped.")

    def _run_loop(self) -> None:
        """Internal background loop."""
        # Send initial heartbeat immediately
        self.send_heartbeat()

        while not self._stop_event.is_set():
            # Wait with event check so stop() responds quickly
            if self._stop_event.wait(timeout=self.interval_sec):
                break
            self.send_heartbeat()
