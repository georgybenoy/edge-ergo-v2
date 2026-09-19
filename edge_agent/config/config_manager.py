"""
EdgeErgo — Edge Agent Configuration Manager

Loads, validates, and provides access to Edge Agent settings.
Configuration sources (in priority order):
  1. Server-pushed config (GET /api/v1/edge/config)
  2. Local config file (edge_config.json)
  3. Hardcoded defaults
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EdgeConfig:
    """Runtime configuration for the Edge Agent.

    All durations are in seconds unless noted otherwise.
    """

    # ── Identity ──────────────────────────────────────────────────────
    device_id: str = ""
    device_name: str = ""

    # ── Camera ────────────────────────────────────────────────────────
    camera_index: int = 0
    capture_fps: int = 10
    frame_width: int = 640
    frame_height: int = 480

    # ── Analysis ──────────────────────────────────────────────────────
    analysis_interval_sec: float = 1.0
    telemetry_window_sec: int = 300  # 5-minute windows

    # ── Server sync ───────────────────────────────────────────────────
    server_url: str = "http://localhost:8000"
    heartbeat_interval_sec: int = 60
    sync_interval_sec: int = 30
    sync_retry_max: int = 5

    # ── Feedback / alerts ─────────────────────────────────────────────
    rula_alert_threshold: int = 5
    reba_alert_threshold: int = 5
    break_interval_min: int = 45

    # ── Paths ─────────────────────────────────────────────────────────
    local_db_path: Path = field(default_factory=lambda: Path("edgeergo_local.db"))
    config_file_path: Path = field(default_factory=lambda: Path("edge_config.json"))


class ConfigManager:
    """Manages loading, merging, and saving of EdgeConfig.

    TODO (Phase 2+):
      - Load from JSON file on disk.
      - Merge with server-pushed overrides.
      - Persist changes back to disk.
      - Validate ranges and required fields.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config = EdgeConfig()
        if config_path is not None:
            self._config.config_file_path = config_path
        # TODO: load from file if it exists

    @property
    def config(self) -> EdgeConfig:
        """Return the current configuration snapshot."""
        return self._config

    def update(self, overrides: dict[str, Any]) -> None:
        """Apply a dict of overrides to the current config.

        TODO: implement field-level validation.
        """
        for key, value in overrides.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def save(self) -> None:
        """Persist current config to disk.

        TODO: implement JSON serialisation.
        """
        raise NotImplementedError
