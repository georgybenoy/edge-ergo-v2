"""
Monitoring Schedule & Session Cadence Manager.

Manages when the Edge Agent captures video and runs ergonomic/facial analysis,
distinguishing between:
  - Monitoring window: configured operating hours (e.g. 09:00 to 17:00)
  - Analysis interval: how often an analysis session starts (e.g. every 30 min)
  - Analysis duration: how long an active session captures & analyzes (e.g. 5 min)

All timing parameters are read from configuration (EdgeConfig) rather than
hardcoded constants, per PRD §15 and §16.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional
import uuid

from edge_agent.config.config_manager import EdgeConfig

logger = logging.getLogger(__name__)


def _parse_time_str(time_str: str) -> datetime.time:
    """Parse 'HH:MM' string into datetime.time."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format '{time_str}', expected 'HH:MM'")
    hour, minute = int(parts[0]), int(parts[1])
    return datetime.time(hour=hour, minute=minute)


class MonitoringScheduler:
    """Orchestrates monitoring session intervals and operational hours.

    Parameters can be passed directly or sourced from an EdgeConfig instance.

    Args:
        config:        Optional EdgeConfig instance.
        start_time:    Operating window start ('HH:MM', default: '09:00').
        end_time:      Operating window end ('HH:MM', default: '17:00').
        interval_min:  Time in minutes between starts of successive sessions (default: 30.0).
        duration_min:  Active session duration in minutes (default: 5.0).
    """

    def __init__(
        self,
        config: Optional[EdgeConfig] = None,
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval_min: Optional[float] = None,
        duration_min: Optional[float] = None,
    ) -> None:
        if config is not None:
            self._start_str = start_time if start_time is not None else config.monitoring_start_time
            self._end_str = end_time if end_time is not None else config.monitoring_end_time
            self._interval_min = interval_min if interval_min is not None else config.session_interval_min
            self._duration_min = duration_min if duration_min is not None else config.session_duration_min
        else:
            self._start_str = start_time or "09:00"
            self._end_str = end_time or "17:00"
            self._interval_min = interval_min if interval_min is not None else 30.0
            self._duration_min = duration_min if duration_min is not None else 5.0

        self._start_time = _parse_time_str(self._start_str)
        self._end_time = _parse_time_str(self._end_str)

        # State
        self._current_session_id: Optional[str] = None
        self._session_start_dt: Optional[datetime.datetime] = None
        self._last_session_start_dt: Optional[datetime.datetime] = None

    # ── Properties ────────────────────────────────────────────────────

    @property
    def start_time_str(self) -> str:
        return self._start_str

    @property
    def end_time_str(self) -> str:
        return self._end_str

    @property
    def interval_min(self) -> float:
        return self._interval_min

    @property
    def duration_min(self) -> float:
        return self._duration_min

    @property
    def is_active(self) -> bool:
        """True if an analysis session is currently running."""
        return self._current_session_id is not None

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    # ── Operational Window ────────────────────────────────────────────

    def is_within_monitoring_hours(self, current_dt: datetime.datetime) -> bool:
        """Check if current time falls within configured monitoring hours."""
        t = current_dt.time()
        if self._start_time <= self._end_time:
            return self._start_time <= t <= self._end_time
        # Wrapping across midnight (e.g. 22:00 to 06:00)
        return t >= self._start_time or t <= self._end_time

    # ── Session Lifecycle Decisions ───────────────────────────────────

    def should_start_session(self, current_dt: datetime.datetime) -> bool:
        """Return True if a new monitoring session should be triggered now.

        Conditions:
          1. Current time must be within monitoring hours.
          2. No session is currently active.
          3. Either no session has ever run, OR interval_min has elapsed
             since the start of the previous session.
        """
        if not self.is_within_monitoring_hours(current_dt):
            return False

        if self.is_active:
            return False

        if self._last_session_start_dt is None:
            return True

        elapsed_sec = (current_dt - self._last_session_start_dt).total_seconds()
        return elapsed_sec >= self._interval_min * 60.0

    def should_end_session(self, current_dt: datetime.datetime) -> bool:
        """Return True if the current active session has completed its duration."""
        if not self.is_active or self._session_start_dt is None:
            return False

        elapsed_sec = (current_dt - self._session_start_dt).total_seconds()
        return elapsed_sec >= self._duration_min * 60.0

    def start_session(
        self,
        current_dt: datetime.datetime,
        session_id: Optional[str] = None,
    ) -> str:
        """Start a new monitoring session and return its unique ID."""
        sid = session_id or str(uuid.uuid4())
        self._current_session_id = sid
        self._session_start_dt = current_dt
        self._last_session_start_dt = current_dt
        logger.info("Started analysis session %s at %s", sid, current_dt.isoformat())
        return sid

    def end_session(self, current_dt: datetime.datetime) -> Optional[str]:
        """Conclude the active monitoring session."""
        sid = self._current_session_id
        if sid is not None:
            logger.info("Ended analysis session %s at %s", sid, current_dt.isoformat())
        self._current_session_id = None
        self._session_start_dt = None
        return sid

    # ── Timing Helpers ────────────────────────────────────────────────

    def time_remaining_in_session(self, current_dt: datetime.datetime) -> float:
        """Seconds remaining in current session, or 0.0 if not active."""
        if not self.is_active or self._session_start_dt is None:
            return 0.0
        elapsed = (current_dt - self._session_start_dt).total_seconds()
        return max(0.0, (self._duration_min * 60.0) - elapsed)

    def time_until_next_session(self, current_dt: datetime.datetime) -> float:
        """Seconds until next scheduled session start."""
        if self._last_session_start_dt is None:
            return 0.0 if self.is_within_monitoring_hours(current_dt) else 3600.0
        elapsed = (current_dt - self._last_session_start_dt).total_seconds()
        remaining = (self._interval_min * 60.0) - elapsed
        return max(0.0, remaining)
