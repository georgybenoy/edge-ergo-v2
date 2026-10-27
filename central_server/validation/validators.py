"""
Pydantic validators for API request and response payloads (PRD §89).

Validates every inbound record:
  - Device registration payloads
  - Heartbeat status pings
  - Telemetry window summaries (exact shape, numeric bounds, ISO timestamp formats)
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Registration Models ───────────────────────────────────────────────────────

class RegisterDeviceRequest(BaseModel):
    """Payload sent by an Edge Agent upon first-time setup."""
    device_name: str = Field(..., min_length=1, max_length=100, description="Human-readable workstation label")
    software_version: str = Field(..., min_length=1, max_length=50, description="Edge Agent software release version")
    camera_detected: bool = Field(default=True, description="Whether an active camera was detected")
    camera_index: int = Field(default=0, ge=0, description="Index of the camera selected")


class RegisterDeviceResponse(BaseModel):
    """Central Server registration response assigning unique NODE-xxx ID."""
    device_id: str = Field(..., description="Unique assigned node identifier, e.g. NODE-001")
    device_name: str
    software_version: str
    registered_at: str
    status: str = "active"


# ── Heartbeat Models ──────────────────────────────────────────────────────────

class HeartbeatRequest(BaseModel):
    """Periodic health ping sent by Edge Nodes."""
    device_id: str = Field(..., min_length=1, max_length=64, description="Node identifier")
    software_version: str = Field(default="0.1.0", min_length=1, max_length=50)
    status: str = Field(default="active", min_length=1, max_length=32, description="Node operational status")


class HeartbeatResponse(BaseModel):
    """Server acknowledgment of received heartbeat."""
    received: bool = True
    device_id: str
    server_time: str


# ── Telemetry Window Models (PRD §88, §89) ────────────────────────────────────

class ErgonomicsMetricsPayload(BaseModel):
    """Aggregated ergonomic metrics for a telemetry window."""
    average_rula: float = Field(..., ge=1.0, le=7.0, description="RULA Grand Score average [1.0, 7.0]")
    maximum_rula: int = Field(..., ge=1, le=7, description="Peak RULA score [1, 7]")
    average_reba: float = Field(..., ge=1.0, le=15.0, description="REBA Grand Score average [1.0, 15.0]")
    maximum_reba: int = Field(..., ge=1, le=15, description="Peak REBA score [1, 15]")
    high_risk_percentage: float = Field(..., ge=0.0, le=100.0, description="% frames classified HIGH or VERY_HIGH")
    dominant_posture: str = Field(..., min_length=1, max_length=64, description="Primary posture condition driving risk")


class FacialExpressionPayload(BaseModel):
    """Aggregated broad facial expression distribution percentages."""
    neutral_percentage: float = Field(..., ge=0.0, le=100.0)
    positive_percentage: float = Field(..., ge=0.0, le=100.0)
    negative_percentage: float = Field(..., ge=0.0, le=100.0)
    reduced_expression_percentage: float = Field(..., ge=0.0, le=100.0)


class BreaksPayload(BaseModel):
    """Summary of movement/hydration nudges during window."""
    breaks_recommended: int = Field(default=0, ge=0)
    breaks_acknowledged: int = Field(default=0, ge=0)


class TelemetryWindowPayload(BaseModel):
    """Full telemetry window JSON sent by Edge Nodes."""
    window_id: Optional[str] = Field(default=None, description="Client-side generated window key for idempotency")
    device_id: str = Field(..., min_length=1, max_length=64, description="Registered node ID")
    session_id: str = Field(..., min_length=1, max_length=64, description="Unique session identifier")
    window_start: str = Field(..., description="Window start in ISO 8601 format")
    window_end: str = Field(..., description="Window end in ISO 8601 format")
    ergonomics: ErgonomicsMetricsPayload
    facial_expression: FacialExpressionPayload
    breaks: BreaksPayload = Field(default_factory=BreaksPayload)
    events: list[dict[str, Any]] = Field(default_factory=list, description="Optional window events or alerts")

    @field_validator("window_start", "window_end")
    @classmethod
    def validate_iso_timestamps(cls, v: str) -> str:
        try:
            # Parse ISO timestamp (handling 'Z' or offset)
            clean = v.replace("Z", "+00:00")
            datetime.fromisoformat(clean)
        except Exception:
            raise ValueError(f"Timestamp must be a valid ISO 8601 string, got: {v!r}")
        return v

    @model_validator(mode="after")
    def validate_window_chronology(self) -> TelemetryWindowPayload:
        try:
            start_dt = datetime.fromisoformat(self.window_start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(self.window_end.replace("Z", "+00:00"))
            if end_dt < start_dt:
                raise ValueError(f"window_end ({self.window_end}) cannot precede window_start ({self.window_start})")
        except ValueError as exc:
            raise exc
        return self


class TelemetryUploadResponse(BaseModel):
    """Server response acknowledging telemetry upload."""
    status: str = Field(..., description="'accepted' or 'duplicate'")
    window_id: str
    device_id: str
    received_at: str


# ── Server Config Models ──────────────────────────────────────────────────────

class ServerConfigResponse(BaseModel):
    """Server-managed monitoring configuration overrides."""
    session_interval_min: float = 30.0
    session_duration_min: float = 5.0
    monitoring_start_time: str = "09:00"
    monitoring_end_time: str = "17:00"
    persistence_threshold_sec: float = 20.0
    alert_cooldown_sec: float = 120.0
    rula_alert_threshold: int = 5
    reba_alert_threshold: int = 5
    break_interval_min: int = 45
    hydration_interval_min: int = 60
