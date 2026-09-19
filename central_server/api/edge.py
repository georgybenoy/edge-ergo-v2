"""
Edge-facing API Router (PRD §11, §40, §41, §42, §46, §88).

Endpoints:
  POST /api/v1/edge/register    — Register new Edge Node, returns NODE-xxx
  POST /api/v1/edge/heartbeat   — Lightweight status ping
  POST /api/v1/edge/assessment  — Ingest anonymized telemetry window
  GET  /api/v1/edge/config      — Retrieve server-managed monitoring configuration
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from central_server.database.database import CentralDatabase
from central_server.validation.validators import (
    HeartbeatRequest,
    HeartbeatResponse,
    RegisterDeviceRequest,
    RegisterDeviceResponse,
    ServerConfigResponse,
    TelemetryUploadResponse,
    TelemetryWindowPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/edge", tags=["Edge Agent Communication"])


# ── Dependency Injection ──────────────────────────────────────────────────────

def get_database(request: Request) -> CentralDatabase:
    """Retrieve CentralDatabase instance from application state."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database repository not initialized on application state.",
        )
    return db


# ── Optional Auth / API Key Placeholder (PRD §88 Upgrade Path) ────────────────

def verify_edge_api_key(
    x_api_key: Optional[str] = Header(None, description="Optional API key placeholder"),
) -> None:
    """Lightweight API key verification placeholder.

    UPGRADE PATH: In enterprise production, replace this placeholder with
    mutual TLS (mTLS) or cryptographic JWT / token authorization per PRD §88.
    For the MVP, unauthenticated or open API keys are accepted.
    """
    if x_api_key is not None and x_api_key == "REJECT_INVALID_KEY":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided.",
        )


# ── 1. Device Registration (PRD §42, §43) ─────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterDeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Edge Node",
    description="Registers an Edge Node workstation and issues an anonymized NODE-xxx ID.",
)
def register_edge_node(
    payload: RegisterDeviceRequest,
    db: CentralDatabase = Depends(get_database),
    _auth: None = Depends(verify_edge_api_key),
) -> RegisterDeviceResponse:
    device = db.register_device(
        device_name=payload.device_name,
        software_version=payload.software_version,
        camera_detected=payload.camera_detected,
        camera_index=payload.camera_index,
    )
    # PRD §90: Log node registration metadata
    logger.info(
        "Edge node registered: id=%s, name=%s, version=%s",
        device["device_id"],
        device["device_name"],
        device["software_version"],
    )
    return RegisterDeviceResponse(
        device_id=device["device_id"],
        device_name=device["device_name"],
        software_version=device["software_version"],
        registered_at=device["registered_at"],
        status=device.get("status", "active"),
    )


# ── 2. Heartbeat (PRD §46) ────────────────────────────────────────────────────

@router.post(
    "/heartbeat",
    response_model=HeartbeatResponse,
    status_code=status.HTTP_200_OK,
    summary="Heartbeat Ping",
    description="Periodically pings Central Server with health and availability status.",
)
def edge_heartbeat(
    payload: HeartbeatRequest,
    db: CentralDatabase = Depends(get_database),
    _auth: None = Depends(verify_edge_api_key),
) -> HeartbeatResponse:
    now_ts = datetime.now(timezone.utc).isoformat()
    updated = db.update_heartbeat(
        device_id=payload.device_id,
        software_version=payload.software_version,
        status=payload.status,
        heartbeat_time=now_ts,
    )
    if not updated:
        # If device not yet registered, auto-register it so heartbeats do not drop
        db.register_device(
            device_name=f"Auto-{payload.device_id}",
            software_version=payload.software_version,
            assigned_id=payload.device_id,
        )

    logger.debug("Received heartbeat from node: id=%s, status=%s", payload.device_id, payload.status)
    return HeartbeatResponse(
        received=True,
        device_id=payload.device_id,
        server_time=now_ts,
    )


# ── 3. Telemetry Window Upload (PRD §40, §89) ─────────────────────────────────

@router.post(
    "/assessment",
    response_model=TelemetryUploadResponse,
    summary="Upload Telemetry Window",
    description="Ingest an anonymized ergonomic telemetry window summary.",
)
def upload_telemetry_window(
    payload: TelemetryWindowPayload,
    response: Response,
    db: CentralDatabase = Depends(get_database),
    _auth: None = Depends(verify_edge_api_key),
) -> TelemetryUploadResponse:
    # 1. Duplicate check (PRD §89)
    is_duplicate = db.is_duplicate_window(
        device_id=payload.device_id,
        session_id=payload.session_id,
        window_start=payload.window_start,
    )

    now_ts = datetime.now(timezone.utc).isoformat()

    if is_duplicate:
        window_id = payload.window_id or f"{payload.session_id}_{payload.window_start}"
        logger.warning(
            "Duplicate telemetry submission rejected: device=%s, session=%s, window=%s",
            payload.device_id,
            payload.session_id,
            window_id,
        )
        response.status_code = status.HTTP_409_CONFLICT
        return TelemetryUploadResponse(
            status="duplicate",
            window_id=window_id,
            device_id=payload.device_id,
            received_at=now_ts,
        )

    # 2. Persist new telemetry window
    payload_dict = payload.model_dump()
    is_new, window_id = db.save_telemetry_window(payload_dict)

    # PRD §90: Log metadata only, never raw data
    logger.info(
        "Ingested telemetry window: id=%s, device=%s, session=%s, avg_rula=%.1f, dominant=%s",
        window_id,
        payload.device_id,
        payload.session_id,
        payload.ergonomics.average_rula,
        payload.ergonomics.dominant_posture,
    )

    response.status_code = status.HTTP_201_CREATED
    return TelemetryUploadResponse(
        status="accepted",
        window_id=window_id,
        device_id=payload.device_id,
        received_at=now_ts,
    )


# ── 4. Server Config Pull (PRD §16, §47) ──────────────────────────────────────

@router.get(
    "/config",
    response_model=ServerConfigResponse,
    summary="Get Server Config",
    description="Fetch server-managed monitoring schedule and threshold configuration.",
)
def get_edge_config(
    device_id: Optional[str] = None,
    db: CentralDatabase = Depends(get_database),
    _auth: None = Depends(verify_edge_api_key),
) -> ServerConfigResponse:
    logger.debug("Delivering server monitoring config to node: %s", device_id or "generic")
    return ServerConfigResponse(
        session_interval_min=30.0,
        session_duration_min=5.0,
        monitoring_start_time="09:00",
        monitoring_end_time="17:00",
        persistence_threshold_sec=20.0,
        alert_cooldown_sec=120.0,
        rula_alert_threshold=5,
        reba_alert_threshold=5,
        break_interval_min=45,
        hydration_interval_min=60,
    )
