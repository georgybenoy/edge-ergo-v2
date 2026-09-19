"""
EdgeErgo — Edge Agent Configuration Manager (PRD §16, §47).

Loads, validates, and provides access to Edge Agent settings.
Configuration sources (in priority order):
  1. Server-pushed config overrides (GET /api/v1/edge/config)
  2. Local config file (edge_config.json)
  3. Hardcoded defaults
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── EdgeConfig Dataclass ──────────────────────────────────────────────────────

@dataclass
class EdgeConfig:
    """Runtime configuration for the Edge Agent.

    All durations are in seconds unless noted otherwise.
    """

    # ── Identity ──────────────────────────────────────────────────────
    device_id: str = ""
    device_name: str = ""
    software_version: str = "0.1.0"

    # ── Camera ────────────────────────────────────────────────────────
    camera_index: int = 0
    capture_fps: int = 10
    frame_width: int = 640
    frame_height: int = 480

    # ── Analysis & Scheduling (PRD §15, §16, §26, §36) ────────────────
    analysis_interval_sec: float = 1.0
    telemetry_window_sec: int = 300           # 5-minute windows
    monitoring_start_time: str = "09:00"      # HH:MM
    monitoring_end_time: str = "17:00"        # HH:MM
    session_interval_min: float = 30.0        # Time between monitoring sessions
    session_duration_min: float = 5.0         # Duration of active monitoring session
    persistence_threshold_sec: float = 20.0   # Time condition must persist before warning
    alert_cooldown_sec: float = 120.0         # Cooldown window before repeating alert for same condition

    # ── Server sync & health (PRD §40, §41, §46) ──────────────────────
    server_url: str = "http://localhost:8000"
    heartbeat_interval_sec: int = 60
    sync_interval_sec: int = 30
    sync_retry_max: int = 5
    backoff_base_sec: float = 2.0
    backoff_max_sec: float = 300.0

    # ── Feedback / alerts ─────────────────────────────────────────────
    rula_alert_threshold: int = 5
    reba_alert_threshold: int = 5
    break_interval_min: int = 45
    hydration_interval_min: int = 60

    # ── Paths ─────────────────────────────────────────────────────────
    local_db_path: Path = field(default_factory=lambda: Path("edgeergo_local.db"))
    config_file_path: Path = field(default_factory=lambda: Path("edge_config.json"))

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary with stringified paths."""
        d = asdict(self)
        d["local_db_path"] = str(self.local_db_path)
        d["config_file_path"] = str(self.config_file_path)
        return d


# ── ConfigManager Class ───────────────────────────────────────────────────────

class ConfigManager:
    """Manages loading, validating, merging, and persisting EdgeConfig."""

    TIME_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

    def __init__(self, config_path: Optional[Path | str] = None, auto_load: bool = True) -> None:
        self._config = EdgeConfig()
        if config_path is not None:
            self._config.config_file_path = Path(config_path)

        if auto_load and self._config.config_file_path.is_file():
            self.load_from_disk()

    @property
    def config(self) -> EdgeConfig:
        """Return the current configuration snapshot."""
        return self._config

    def validate(self, overrides: dict[str, Any]) -> dict[str, Any]:
        """Validate overrides against defined types and ranges.

        Raises ValueError if any field fails validation.
        """
        validated: dict[str, Any] = {}
        for key, val in overrides.items():
            if not hasattr(self._config, key):
                logger.warning("Ignoring unknown config key: %s", key)
                continue

            # Field-specific validations
            if key == "capture_fps":
                ival = int(val)
                if not (1 <= ival <= 60):
                    raise ValueError(f"capture_fps must be between 1 and 60, got {ival}")
                validated[key] = ival
            elif key in ("frame_width", "frame_height"):
                ival = int(val)
                if ival <= 0:
                    raise ValueError(f"{key} must be positive, got {ival}")
                validated[key] = ival
            elif key in ("monitoring_start_time", "monitoring_end_time"):
                sval = str(val).strip()
                if not self.TIME_REGEX.match(sval):
                    raise ValueError(f"{key} must be in 'HH:MM' 24-hour format, got {sval!r}")
                validated[key] = sval
            elif key in ("session_interval_min", "session_duration_min"):
                fval = float(val)
                if fval <= 0:
                    raise ValueError(f"{key} must be positive, got {fval}")
                validated[key] = fval
            elif key in ("persistence_threshold_sec", "alert_cooldown_sec", "backoff_base_sec", "backoff_max_sec"):
                fval = float(val)
                if fval < 0:
                    raise ValueError(f"{key} must be non-negative, got {fval}")
                validated[key] = fval
            elif key == "rula_alert_threshold":
                ival = int(val)
                if not (1 <= ival <= 7):
                    raise ValueError(f"rula_alert_threshold must be between 1 and 7, got {ival}")
                validated[key] = ival
            elif key == "reba_alert_threshold":
                ival = int(val)
                if not (1 <= ival <= 15):
                    raise ValueError(f"reba_alert_threshold must be between 1 and 15, got {ival}")
                validated[key] = ival
            elif key == "server_url":
                sval = str(val).rstrip("/")
                if not (sval.startswith("http://") or sval.startswith("https://")):
                    raise ValueError(f"server_url must start with http:// or https://, got {sval!r}")
                validated[key] = sval
            elif key in ("local_db_path", "config_file_path"):
                validated[key] = Path(val)
            else:
                validated[key] = val

        return validated

    def update(self, overrides: dict[str, Any], save_to_disk: bool = False) -> None:
        """Apply a dict of overrides to the current config after validation."""
        valid = self.validate(overrides)
        for key, value in valid.items():
            setattr(self._config, key, value)
        logger.info("Updated config fields: %s", list(valid.keys()))

        if save_to_disk:
            self.save()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a config value by key."""
        return getattr(self._config, key, default)

    def set(self, key: str, value: Any, save_to_disk: bool = False) -> None:
        """Set a single config key value."""
        self.update({key: value}, save_to_disk=save_to_disk)

    def load_from_disk(self, config_path: Optional[Path | str] = None) -> None:
        """Load configuration from disk JSON file."""
        target_path = Path(config_path) if config_path is not None else self._config.config_file_path
        if not target_path.is_file():
            logger.debug("Config file does not exist at %s; using defaults.", target_path)
            return

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.update(data, save_to_disk=False)
            logger.info("Loaded config from %s", target_path)
        except Exception as exc:
            logger.error("Failed to load config from %s: %s", target_path, exc)
            raise

    def save(self, config_path: Optional[Path | str] = None) -> None:
        """Persist current configuration to disk as JSON."""
        target_path = Path(config_path) if config_path is not None else self._config.config_file_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = self._config.to_dict()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Saved config to %s", target_path)
        except Exception as exc:
            logger.error("Failed to save config to %s: %s", target_path, exc)
            raise
