"""
Temporal Posture Analyzer & Session Manager.

Tracks posture persistence over time and manages analysis sessions.
Key responsibilities (PRD §26, §36):
  1. Persistence tracking: single noisy bad-posture frames do NOT trigger alerts;
     a condition must persist continuously for >= persistence_threshold_sec (e.g. 20s).
  2. Alert cooldown: after an alert fires for a condition, a cooldown window
     (e.g. 120s) suppresses immediate duplicate alerts for that condition.
  3. Session management: aggregates per-frame ergonomic & facial metrics across
     an analysis session into SessionStats (avg/max RULA/REBA, dominant posture,
     high-risk percentage) ready for local storage and telemetry sync.
  4. Pipeline orchestration: conducts the end-to-end processing chain across
     vision, geometry, ergonomics, and expression.
"""

from __future__ import annotations

import collections
from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Optional, Sequence

import numpy as np

from edge_agent.config.config_manager import EdgeConfig
from edge_agent.ergonomics.scoring import AssessmentResult, RiskLevel, assess
from edge_agent.expression.classifier import ExpressionClassifier, ExpressionResult
from edge_agent.geometry.angle_calculator import AngleCalculator, PostureParameters
from edge_agent.vision.face_engine import FaceEngine, FaceResult
from edge_agent.vision.pose_engine import PoseEngine, PoseResult

logger = logging.getLogger(__name__)


# ── Alert Event Data Structure ────────────────────────────────────────────────

@dataclass
class AlertEvent:
    """An ergonomic alert generated when poor posture persists beyond threshold.

    Attributes:
        condition:    Posture driving the alert (e.g. 'NECK_FLEXION', 'TRUNK_FLEXION').
        risk_level:   Risk level at trigger time ('HIGH' or 'VERY_HIGH').
        rula_score:   RULA Grand Score at trigger time.
        reba_score:   REBA Grand Score at trigger time.
        duration_sec: Continuous duration in seconds the posture persisted.
        timestamp:    Time when the alert triggered.
        message:      Ergonomic recommendation / nudge for the worker.
    """
    condition: str
    risk_level: str
    rula_score: int
    reba_score: int
    duration_sec: float
    timestamp: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Session Aggregated Statistics ─────────────────────────────────────────────

@dataclass
class SessionStats:
    """Aggregated statistics for a completed monitoring session.

    Ready for persistence to Local Storage (Phase 9) and Telemetry Windows (Phase 10).
    """
    session_id: str
    start_time: float
    end_time: float
    duration_sec: float
    total_frames: int
    analyzed_frames: int
    avg_rula: float
    max_rula: int
    avg_reba: float
    max_reba: int
    dominant_posture: str
    high_risk_percentage: float
    risk_distribution: dict[str, int] = field(default_factory=dict)
    posture_distribution: dict[str, int] = field(default_factory=dict)
    expression_distribution: dict[str, int] = field(default_factory=dict)
    alerts_triggered: list[AlertEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["alerts_triggered"] = [a.to_dict() for a in self.alerts_triggered]
        return d


# ── Frame Processing Result ───────────────────────────────────────────────────

@dataclass
class FrameAnalysisResult:
    """Consolidated output from processing a single video frame."""
    timestamp: float
    is_session_active: bool
    session_id: Optional[str] = None
    assessment: Optional[AssessmentResult] = None
    expression: Optional[ExpressionResult] = None
    pose_result: Optional[PoseResult] = None
    face_result: Optional[FaceResult] = None
    triggered_alert: Optional[AlertEvent] = None


# ── Human-Readable Alert Nudges ───────────────────────────────────────────────

ALERT_MESSAGES: dict[str, str] = {
    "NECK_FLEXION": "Neck bent forward. Try raising your monitor so the top line is at eye level.",
    "NECK_EXTENSION": "Neck tilted backward. Adjust monitor height to reduce neck strain.",
    "TRUNK_FLEXION": "Forward torso hunch detected. Sit back and let the chair backrest support your spine.",
    "TRUNK_EXTENSION": "Torso leaning excessively backward. Adjust your seat angle.",
    "SHOULDER_ELEVATION": "Shoulders elevated or arm reaching. Relax your shoulders and bring keyboard closer.",
    "ELBOW_EXTENSION": "Reaching too far forward. Keep elbows close to your torso (around 90°).",
    "WRIST_DEVIATION": "Awkward wrist bend. Keep wrists straight in a neutral resting position.",
    "HIGH_RISK_POSTURE": "Sustained high-risk posture detected. Consider taking a brief micro-break to stretch.",
}


# ── Temporal Analyzer ─────────────────────────────────────────────────────────

class TemporalAnalyzer:
    """Monitors posture persistence, triggers cooldown-gated alerts, and aggregates sessions.

    Parameters:
        persistence_threshold_sec: Continuous duration of bad posture required before
                                   triggering an alert (default: 20.0s).
        alert_cooldown_sec:        Cooldown after an alert before the same condition
                                   can alert again (default: 120.0s).
        tolerance_gap_sec:         Allowed interruption in seconds before a continuous
                                   posture streak is considered broken (default: 2.0s).
    """

    def __init__(
        self,
        config: Optional[EdgeConfig] = None,
        *,
        persistence_threshold_sec: Optional[float] = None,
        alert_cooldown_sec: Optional[float] = None,
        tolerance_gap_sec: float = 2.0,
    ) -> None:
        if config is not None:
            self.persistence_threshold_sec = (
                persistence_threshold_sec
                if persistence_threshold_sec is not None
                else config.persistence_threshold_sec
            )
            self.alert_cooldown_sec = (
                alert_cooldown_sec
                if alert_cooldown_sec is not None
                else config.alert_cooldown_sec
            )
        else:
            self.persistence_threshold_sec = (
                persistence_threshold_sec if persistence_threshold_sec is not None else 20.0
            )
            self.alert_cooldown_sec = (
                alert_cooldown_sec if alert_cooldown_sec is not None else 120.0
            )

        self.tolerance_gap_sec = tolerance_gap_sec

        # Condition tracking: condition_name -> {"start_time": float, "last_seen": float}
        self._condition_trackers: dict[str, dict[str, float]] = {}

        # Cooldown tracking: condition_name -> last_alert_time (float)
        self._last_alert_times: dict[str, float] = {}

        # Session tracking state
        self._current_session_id: Optional[str] = None
        self._session_start_time: float = 0.0
        self._session_assessments: list[AssessmentResult] = []
        self._session_expressions: list[ExpressionResult] = []
        self._session_alerts: list[AlertEvent] = []
        self._total_session_frames: int = 0

    # ── Session Lifecycle ─────────────────────────────────────────────

    @property
    def is_in_session(self) -> bool:
        return self._current_session_id is not None

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    def start_session(self, session_id: str, timestamp: float) -> None:
        """Start aggregating a new analysis session."""
        self._current_session_id = session_id
        self._session_start_time = timestamp
        self._session_assessments.clear()
        self._session_expressions.clear()
        self._session_alerts.clear()
        self._total_session_frames = 0
        self._condition_trackers.clear()
        logger.info("TemporalAnalyzer started session %s at t=%.2f", session_id, timestamp)

    def end_session(self, timestamp: float) -> Optional[SessionStats]:
        """Conclude the active session and compute aggregated stats."""
        if self._current_session_id is None:
            return None

        sid = self._current_session_id
        start_t = self._session_start_time
        duration = max(0.0, timestamp - start_t)
        total_frames = self._total_session_frames
        valid_assessments = [a for a in self._session_assessments if a.is_valid]
        analyzed_frames = len(valid_assessments)

        if analyzed_frames > 0:
            avg_rula = float(np.mean([a.rula_score for a in valid_assessments]))
            max_rula = max(a.rula_score for a in valid_assessments)
            avg_reba = float(np.mean([a.reba_score for a in valid_assessments]))
            max_reba = max(a.reba_score for a in valid_assessments)

            # High risk percentage (HIGH or VERY_HIGH)
            high_risk_count = sum(
                1 for a in valid_assessments
                if a.risk_level in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)
            )
            high_risk_pct = round((high_risk_count / analyzed_frames) * 100.0, 1)

            # Posture and risk distributions
            posture_counts: dict[str, int] = collections.Counter(
                a.dominant_posture for a in valid_assessments
            )
            risk_counts: dict[str, int] = collections.Counter(
                a.risk_level.value for a in valid_assessments
            )

            # Overall dominant posture: most common among high/moderate risk, or most frequent
            non_neutral = [
                a.dominant_posture for a in valid_assessments
                if a.dominant_posture not in ("NEUTRAL", "NO_PERSON_DETECTED")
            ]
            if non_neutral:
                dominant_posture = collections.Counter(non_neutral).most_common(1)[0][0]
            else:
                dominant_posture = "NEUTRAL"
        else:
            avg_rula = 1.0
            max_rula = 1
            avg_reba = 1.0
            max_reba = 1
            high_risk_pct = 0.0
            posture_counts = {}
            risk_counts = {}
            dominant_posture = "NO_PERSON_DETECTED"

        # Expression distribution
        valid_exprs = [e for e in self._session_expressions if e.is_valid]
        expression_counts: dict[str, int] = collections.Counter(
            e.category.value for e in valid_exprs
        )

        stats = SessionStats(
            session_id=sid,
            start_time=start_t,
            end_time=timestamp,
            duration_sec=round(duration, 2),
            total_frames=total_frames,
            analyzed_frames=analyzed_frames,
            avg_rula=round(avg_rula, 2),
            max_rula=max_rula,
            avg_reba=round(avg_reba, 2),
            max_reba=max_reba,
            dominant_posture=dominant_posture,
            high_risk_percentage=high_risk_pct,
            risk_distribution=dict(risk_counts),
            posture_distribution=dict(posture_counts),
            expression_distribution=dict(expression_counts),
            alerts_triggered=list(self._session_alerts),
        )

        self._current_session_id = None
        self._condition_trackers.clear()
        logger.info("TemporalAnalyzer concluded session %s: %d frames, high_risk=%.1f%%", sid, analyzed_frames, high_risk_pct)
        return stats

    # ── Frame Processing & Persistence Tracking ───────────────────────

    def process_frame(
        self,
        assessment: AssessmentResult,
        expression: Optional[ExpressionResult] = None,
        *,
        timestamp: float = 0.0,
    ) -> Optional[AlertEvent]:
        """Process an assessment and check if any posture condition should alert.

        A single bad frame does NOT alert.
        A condition must persist for >= persistence_threshold_sec, and cooldown must have expired.

        Returns:
            AlertEvent if an alert was triggered on this frame, else None.
        """
        self._total_session_frames += 1

        if assessment.is_valid:
            self._session_assessments.append(assessment)
        if expression is not None and expression.is_valid:
            self._session_expressions.append(expression)

        if not assessment.is_valid:
            # Person absent or frame invalid — clear active condition streaks
            self._clear_stale_conditions(timestamp, max_gap=0.0)
            return None

        # Determine active bad conditions for this frame
        active_conditions: list[str] = []
        is_bad_posture = assessment.risk_level in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)

        if is_bad_posture:
            cond = assessment.dominant_posture
            if cond not in ("NEUTRAL", "NO_PERSON_DETECTED"):
                active_conditions.append(cond)
            else:
                active_conditions.append("HIGH_RISK_POSTURE")

        # Update condition persistence timers
        triggered_alert: Optional[AlertEvent] = None

        for cond in active_conditions:
            if cond not in self._condition_trackers:
                # Start tracking new streak
                self._condition_trackers[cond] = {
                    "start_time": timestamp,
                    "last_seen": timestamp,
                }
            else:
                self._condition_trackers[cond]["last_seen"] = timestamp
                duration = timestamp - self._condition_trackers[cond]["start_time"]

                # Check if persistence threshold met
                if duration >= self.persistence_threshold_sec:
                    # Check alert cooldown
                    last_alert = self._last_alert_times.get(cond, -1e9)
                    if timestamp - last_alert >= self.alert_cooldown_sec:
                        msg = ALERT_MESSAGES.get(cond, ALERT_MESSAGES["HIGH_RISK_POSTURE"])
                        alert = AlertEvent(
                            condition=cond,
                            risk_level=assessment.risk_level.value,
                            rula_score=assessment.rula_score,
                            reba_score=assessment.reba_score,
                            duration_sec=round(duration, 1),
                            timestamp=timestamp,
                            message=msg,
                        )
                        self._last_alert_times[cond] = timestamp
                        self._session_alerts.append(alert)
                        triggered_alert = alert
                        logger.warning(
                            "ALERT: %s persisted for %.1fs (RULA=%d, REBA=%d)",
                            cond, duration, assessment.rula_score, assessment.reba_score
                        )
                        break  # Fire one alert per frame

        # Clear conditions that were not active in this frame
        self._clear_stale_conditions(timestamp, max_gap=self.tolerance_gap_sec)

        return triggered_alert

    def _clear_stale_conditions(self, current_time: float, max_gap: float) -> None:
        """Remove condition trackers where posture improved or worker adjusted."""
        to_delete: list[str] = []
        for cond, tracker in self._condition_trackers.items():
            if current_time - tracker["last_seen"] > max_gap:
                to_delete.append(cond)
        for cond in to_delete:
            del self._condition_trackers[cond]


# ── Pipeline Conductor (Orchestrator) ─────────────────────────────────────────

class TemporalEngine:
    """Conductor orchestrating vision, geometry, ergonomics, and temporal analysis.

    Wires together:
      Camera frame -> PoseEngine -> AngleCalculator -> Ergonomic assess ->
      FaceEngine -> ExpressionClassifier -> TemporalAnalyzer -> AlertEvent
    """

    def __init__(
        self,
        config: Optional[EdgeConfig] = None,
        pose_engine: Optional[PoseEngine] = None,
        angle_calculator: Optional[AngleCalculator] = None,
        face_engine: Optional[FaceEngine] = None,
        expression_classifier: Optional[ExpressionClassifier] = None,
        temporal_analyzer: Optional[TemporalAnalyzer] = None,
    ) -> None:
        self.config = config or EdgeConfig()
        self.pose_engine = pose_engine
        self.angle_calculator = angle_calculator or AngleCalculator()
        self.face_engine = face_engine
        self.expression_classifier = expression_classifier or ExpressionClassifier()
        self.temporal_analyzer = temporal_analyzer or TemporalAnalyzer(self.config)

    def process_raw_frame(
        self,
        rgb_frame: np.ndarray,
        *,
        timestamp: float = 0.0,
    ) -> FrameAnalysisResult:
        """Execute full end-to-end processing chain for one video frame."""
        # 1. Pose estimation
        pose_res = self.pose_engine.process_frame(rgb_frame) if self.pose_engine else None

        # 2. Geometry angles
        if pose_res is not None and pose_res.is_detected:
            posture = self.angle_calculator.calculate(pose_res.landmarks, timestamp=timestamp)
        else:
            posture = PostureParameters(timestamp=timestamp)

        # 3. Ergonomic scoring
        assessment = assess(posture)
        assessment.timestamp = timestamp

        # 4. Facial expression analysis (if face engine available)
        face_res = None
        exp_res = None
        if self.face_engine is not None and self.face_engine.is_initialised:
            face_res = self.face_engine.process_frame(rgb_frame, timestamp=timestamp)
            exp_res = self.expression_classifier.classify(face_res, timestamp=timestamp)

        # 5. Temporal persistence and alert checking
        triggered_alert = self.temporal_analyzer.process_frame(
            assessment=assessment,
            expression=exp_res,
            timestamp=timestamp,
        )

        return FrameAnalysisResult(
            timestamp=timestamp,
            is_session_active=self.temporal_analyzer.is_in_session,
            session_id=self.temporal_analyzer.current_session_id,
            assessment=assessment,
            expression=exp_res,
            pose_result=pose_res,
            face_result=face_res,
            triggered_alert=triggered_alert,
        )
