"""
Thread-safe local assessment state provider for real-time HUD and worker feedback.

Maintains the live ergonomic state of the current workstation:
  - RULA score (1-7), REBA score (1-15), unified RiskLevel (LOW, MODERATE, HIGH, VERY_HIGH)
  - Joint angles and anatomical breakdown
  - Pose detection status and assessment validity
  - Freshness tracking and staleness detection
  - Safe fallback to local SQLite database when in-memory assessment is not yet available
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
import logging
import threading
import time
from typing import Any, Mapping, Optional, Sequence

from edge_agent.ergonomics.scoring import RiskLevel, map_risk_level
from edge_agent.storage.local_db import LocalDatabase

logger = logging.getLogger(__name__)


def derive_overall_risk(
    rula_score: Optional[int],
    reba_score: Optional[int],
    rula_action_level: Optional[int] = None,
    reba_action_level: Optional[int] = None,
) -> Optional[str]:
    """Derive unified RiskLevel from RULA and REBA scores or action levels.

    Uses official ergonomic action levels and conservative maximum-severity mapping:
      - RULA Action Level (1-4):
          Score 1-2 -> Action Level 1 (LOW)
          Score 3-4 -> Action Level 2 (MODERATE)
          Score 5-6 -> Action Level 3 (HIGH)
          Score 7+  -> Action Level 4 (VERY_HIGH)
      - REBA Action Level (0-4):
          Score 1   -> Action Level 0 (LOW)
          Score 2-3 -> Action Level 1 (LOW)
          Score 4-7 -> Action Level 2 (MODERATE)
          Score 8-10 -> Action Level 3 (HIGH)
          Score 11+ -> Action Level 4 (VERY_HIGH)

    Returns:
        "LOW", "MODERATE", "HIGH", "VERY_HIGH", or None if neither score is valid.
    """
    if rula_score is None and reba_score is None:
        return None

    # Derive RULA action level if not explicitly provided
    if rula_action_level is None and rula_score is not None:
        if rula_score >= 7:
            rula_action = 4
        elif rula_score >= 5:
            rula_action = 3
        elif rula_score >= 3:
            rula_action = 2
        else:
            rula_action = 1
    else:
        rula_action = rula_action_level

    # Derive REBA action level if not explicitly provided
    if reba_action_level is None and reba_score is not None:
        if reba_score >= 11:
            reba_action = 4
        elif reba_score >= 8:
            reba_action = 3
        elif reba_score >= 4:
            reba_action = 2
        elif reba_score >= 2:
            reba_action = 1
        else:
            reba_action = 0
    else:
        reba_action = reba_action_level

    if rula_action is not None and reba_action is not None:
        return map_risk_level(rula_action, reba_action).value
    elif rula_action is not None:
        return map_risk_level(rula_action, 0).value
    elif reba_action is not None:
        return map_risk_level(1, reba_action).value

    return None


@dataclass
class CurrentAssessmentState:
    """Snapshot of the current workstation's ergonomic assessment."""

    device_id: str = "NODE-LOCAL"
    device_name: str = "Workstation"
    timestamp: float = 0.0
    rula_score: Optional[int] = None
    reba_score: Optional[int] = None
    risk_level: Optional[str] = None
    rula_action_level: Optional[int] = None
    reba_action_level: Optional[int] = None
    dominant_posture: str = "NEUTRAL"
    joint_angles: dict[str, Optional[float]] = field(default_factory=dict)
    pose_detected: bool = False
    assessment_valid: bool = False
    status: str = "Initializing camera..."
    last_error: Optional[str] = None
    last_valid_timestamp: float = 0.0
    sync_status: str = "Synced ●"
    is_fallback: bool = False
    is_monitoring: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class AssessmentStateProvider:
    """Thread-safe state provider holding the latest local workstation assessment."""

    def __init__(
        self,
        local_db: Optional[LocalDatabase] = None,
        freshness_threshold_sec: float = 5.0,
    ) -> None:
        self._lock = threading.Lock()
        self._state = CurrentAssessmentState()
        self._local_db = local_db
        self.freshness_threshold_sec = freshness_threshold_sec

    def set_device_info(self, device_id: str, device_name: str) -> None:
        with self._lock:
            self._state.device_id = device_id
            self._state.device_name = device_name

    def update_status(self, status: str, last_error: Optional[str] = None) -> None:
        with self._lock:
            self._state.status = status
            if last_error is not None:
                self._state.last_error = last_error

    def update_no_pose(
        self,
        status: str = "No person detected",
        timestamp: float = 0.0,
        sync_status: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._state.pose_detected = False
            self._state.assessment_valid = False
            self._state.status = status
            if timestamp > 0:
                self._state.timestamp = timestamp
            if sync_status:
                self._state.sync_status = sync_status

    def update_assessment(
        self,
        rula_score: int,
        reba_score: int,
        risk_level: str,
        rula_action_level: Optional[int] = None,
        reba_action_level: Optional[int] = None,
        dominant_posture: str = "NEUTRAL",
        joint_angles: Optional[dict[str, Optional[float]]] = None,
        timestamp: float = 0.0,
        status: str = "Monitoring",
        sync_status: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._state.rula_score = int(rula_score)
            self._state.reba_score = int(reba_score)
            self._state.risk_level = risk_level
            self._state.rula_action_level = rula_action_level
            self._state.reba_action_level = reba_action_level
            self._state.dominant_posture = dominant_posture
            if joint_angles:
                self._state.joint_angles = joint_angles
            ts = timestamp if timestamp > 0 else time.time()
            self._state.timestamp = ts
            self._state.last_valid_timestamp = ts
            self._state.pose_detected = True
            self._state.assessment_valid = True
            self._state.status = status
            self._state.is_fallback = False
            self._state.last_error = None
            if sync_status:
                self._state.sync_status = sync_status
            logger.debug(
                "AssessmentState updated: RULA=%d REBA=%d Risk=%s Posture=%s",
                rula_score, reba_score, risk_level, dominant_posture,
            )

    def update_sync_status(self, sync_status: str) -> None:
        with self._lock:
            self._state.sync_status = sync_status

    def is_stale(self, cur_time: float) -> bool:
        with self._lock:
            if not self._state.assessment_valid or self._state.last_valid_timestamp <= 0:
                return False
            return (cur_time - self._state.last_valid_timestamp) > self.freshness_threshold_sec

    def get_state(self) -> CurrentAssessmentState:
        with self._lock:
            return dataclasses.replace(self._state)

    def fallback_to_local_db(self, device_id: str) -> bool:
        """Fallback to local SQLite database if in-memory state has no valid assessment yet."""
        if not self._local_db:
            return False

        with self._lock:
            if self._state.last_valid_timestamp > 0:
                # Already have live in-memory assessment; do not override with older DB record
                return False

        try:
            with self._local_db.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT a.rula_score, a.reba_score, a.risk_level, a.dominant_posture, a.timestamp
                    FROM assessment a
                    JOIN session s ON a.session_id = s.session_id
                    WHERE s.device_id = ?
                    ORDER BY a.timestamp DESC
                    LIMIT 1
                    """,
                    (device_id,),
                ).fetchone()

                if not row:
                    return False

                rula = row["rula_score"]
                reba = row["reba_score"]
                risk = row["risk_level"]
                dom = row["dominant_posture"]
                ts_str = row["timestamp"]

            with self._lock:
                if self._state.last_valid_timestamp > 0:
                    return False
                self._state.rula_score = int(rula) if rula is not None else None
                self._state.reba_score = int(reba) if reba is not None else None
                self._state.risk_level = risk
                self._state.dominant_posture = dom or "NEUTRAL"
                self._state.assessment_valid = True
                self._state.pose_detected = True
                self._state.is_fallback = True
                self._state.status = "Monitoring (Cached)"
                logger.info("Loaded previous assessment from local database as initial fallback: RULA=%s REBA=%s", rula, reba)
                return True
        except Exception as e:
            logger.debug("Database fallback query exception: %s", e)
            return False
