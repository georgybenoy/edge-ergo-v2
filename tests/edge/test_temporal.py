"""
Tests for edge_agent/temporal/analyzer.py and edge_agent/feedback/scheduler.py.

Validates:
  1. MonitoringScheduler:
     - Operational window checks (e.g. 09:00-17:00).
     - Analysis interval (how often session starts) vs. duration (how long it runs).
     - Config-driven instantiation.
  2. Temporal persistence:
     - Single noisy bad frame does NOT trigger an alert.
     - Sustained bad posture >= persistence_threshold_sec triggers an AlertEvent.
     - Posture recovery resets the condition streak.
  3. Alert cooldown:
     - Once an alert fires, repeat alerts for that condition are suppressed during cooldown.
     - Re-fires only after cooldown expires if bad posture persists.
  4. Session management:
     - Aggregates avg/max RULA/REBA, high-risk %, posture distribution, and alerts.
  5. Pipeline Conductor (TemporalEngine):
     - End-to-end orchestration across mock pipeline.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import numpy as np
import pytest

from edge_agent.config.config_manager import EdgeConfig
from edge_agent.ergonomics.rula import RulaBreakdown
from edge_agent.ergonomics.reba import RebaBreakdown
from edge_agent.ergonomics.scoring import AssessmentResult, RiskLevel
from edge_agent.expression.classifier import ExpressionCategory, ExpressionResult
from edge_agent.feedback.scheduler import MonitoringScheduler
from edge_agent.geometry.angle_calculator import PostureParameters
from edge_agent.temporal.analyzer import (
    AlertEvent,
    FrameAnalysisResult,
    SessionStats,
    TemporalAnalyzer,
    TemporalEngine,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_assessment(
    risk_level: RiskLevel = RiskLevel.LOW,
    dominant_posture: str = "NEUTRAL",
    rula: int = 1,
    reba: int = 1,
    timestamp: float = 0.0,
    is_valid: bool = True,
) -> AssessmentResult:
    return AssessmentResult(
        rula_score=rula,
        reba_score=reba,
        risk_level=risk_level,
        dominant_posture=dominant_posture,
        rula_action_level=1 if risk_level == RiskLevel.LOW else 3,
        reba_action_level=1 if risk_level == RiskLevel.LOW else 3,
        rula_breakdown=RulaBreakdown(grand_score=rula),
        reba_breakdown=RebaBreakdown(grand_score=reba),
        posture_parameters=PostureParameters(timestamp=timestamp),
        timestamp=timestamp,
        is_valid=is_valid,
    )


# ── 1. Monitoring Scheduler Tests ─────────────────────────────────────────────

class TestMonitoringScheduler:

    def test_within_and_outside_operating_hours(self) -> None:
        scheduler = MonitoringScheduler(start_time="09:00", end_time="17:00")

        # 08:30 -> Before window
        dt_early = datetime.datetime(2026, 9, 19, 8, 30, 0)
        assert scheduler.is_within_monitoring_hours(dt_early) is False
        assert scheduler.should_start_session(dt_early) is False

        # 10:15 -> Inside window
        dt_inside = datetime.datetime(2026, 9, 19, 10, 15, 0)
        assert scheduler.is_within_monitoring_hours(dt_inside) is True
        assert scheduler.should_start_session(dt_inside) is True

        # 17:30 -> After window
        dt_late = datetime.datetime(2026, 9, 19, 17, 30, 0)
        assert scheduler.is_within_monitoring_hours(dt_late) is False
        assert scheduler.should_start_session(dt_late) is False

    def test_session_cadence_interval_and_duration(self) -> None:
        """Verify distinction between analysis interval (30 min) and duration (5 min)."""
        scheduler = MonitoringScheduler(
            start_time="09:00",
            end_time="17:00",
            interval_min=30.0,
            duration_min=5.0,
        )

        t0 = datetime.datetime(2026, 9, 19, 9, 0, 0)
        assert scheduler.should_start_session(t0) is True

        sid = scheduler.start_session(t0)
        assert scheduler.is_active is True
        assert scheduler.current_session_id == sid

        # During session (at t = 2 min): session is active, cannot start another
        t_mid = t0 + datetime.timedelta(minutes=2)
        assert scheduler.is_active is True
        assert scheduler.should_start_session(t_mid) is False
        assert scheduler.should_end_session(t_mid) is False
        assert scheduler.time_remaining_in_session(t_mid) == pytest.approx(180.0, abs=1.0)

        # End of session (at t = 5 min): session duration elapsed
        t_end = t0 + datetime.timedelta(minutes=5)
        assert scheduler.should_end_session(t_end) is True
        scheduler.end_session(t_end)
        assert scheduler.is_active is False

        # Between sessions (at t = 15 min): neither active nor time for next session
        t_between = t0 + datetime.timedelta(minutes=15)
        assert scheduler.is_active is False
        assert scheduler.should_start_session(t_between) is False
        assert scheduler.time_until_next_session(t_between) == pytest.approx(900.0, abs=1.0)

        # Next session start (at t = 30 min): interval has elapsed!
        t_next = t0 + datetime.timedelta(minutes=30)
        assert scheduler.should_start_session(t_next) is True

    def test_instantiation_from_edge_config(self) -> None:
        cfg = EdgeConfig(
            monitoring_start_time="08:00",
            monitoring_end_time="18:00",
            session_interval_min=20.0,
            session_duration_min=3.0,
        )
        scheduler = MonitoringScheduler(config=cfg)
        assert scheduler.start_time_str == "08:00"
        assert scheduler.end_time_str == "18:00"
        assert scheduler.interval_min == 20.0
        assert scheduler.duration_min == 3.0


# ── 2. Temporal Persistence Tests ─────────────────────────────────────────────

class TestTemporalPersistence:

    def test_single_bad_frame_does_not_alert(self) -> None:
        """A single noisy frame with high risk must NOT trigger an alert."""
        analyzer = TemporalAnalyzer(persistence_threshold_sec=20.0, alert_cooldown_sec=120.0)
        analyzer.start_session("test_sess", timestamp=0.0)

        # Frame 0: Good posture
        a0 = _make_assessment(RiskLevel.LOW, "NEUTRAL", rula=1, timestamp=0.0)
        assert analyzer.process_frame(a0, timestamp=0.0) is None

        # Frame 1: Single bad posture spike
        a1 = _make_assessment(RiskLevel.HIGH, "NECK_FLEXION", rula=6, timestamp=1.0)
        assert analyzer.process_frame(a1, timestamp=1.0) is None

        # Frame 2: Immediately returns to good posture
        a2 = _make_assessment(RiskLevel.LOW, "NEUTRAL", rula=1, timestamp=2.0)
        assert analyzer.process_frame(a2, timestamp=2.0) is None

    def test_sustained_bad_posture_triggers_alert(self) -> None:
        """Sustained bad posture >= persistence threshold must fire an AlertEvent."""
        threshold = 15.0
        analyzer = TemporalAnalyzer(persistence_threshold_sec=threshold, alert_cooldown_sec=120.0)
        analyzer.start_session("test_sess", timestamp=0.0)

        fired_alert: AlertEvent | None = None

        # Feed 16 seconds of continuous NECK_FLEXION at 1 FPS
        for t in range(0, 17):
            assess = _make_assessment(
                RiskLevel.HIGH,
                "NECK_FLEXION",
                rula=6,
                reba=6,
                timestamp=float(t),
            )
            alert = analyzer.process_frame(assess, timestamp=float(t))
            if alert is not None:
                fired_alert = alert

        assert fired_alert is not None
        assert fired_alert.condition == "NECK_FLEXION"
        assert fired_alert.risk_level == "HIGH"
        assert fired_alert.rula_score == 6
        assert fired_alert.duration_sec >= threshold
        assert "Neck bent forward" in fired_alert.message

    def test_posture_recovery_resets_streak(self) -> None:
        """If worker corrects posture before threshold, timer resets."""
        threshold = 20.0
        analyzer = TemporalAnalyzer(persistence_threshold_sec=threshold, tolerance_gap_sec=2.0)
        analyzer.start_session("test_sess", timestamp=0.0)

        # Bad posture for 10s (below 20s threshold)
        for t in range(0, 11):
            bad = _make_assessment(RiskLevel.HIGH, "TRUNK_FLEXION", rula=5, timestamp=float(t))
            assert analyzer.process_frame(bad, timestamp=float(t)) is None

        # Worker sits back up for 5s
        for t in range(11, 16):
            good = _make_assessment(RiskLevel.LOW, "NEUTRAL", rula=1, timestamp=float(t))
            assert analyzer.process_frame(good, timestamp=float(t)) is None

        # Slouches again for 10s -> total cumulative is 20s, but not continuous
        for t in range(16, 27):
            bad2 = _make_assessment(RiskLevel.HIGH, "TRUNK_FLEXION", rula=5, timestamp=float(t))
            alert = analyzer.process_frame(bad2, timestamp=float(t))
            assert alert is None, "Streak was broken; should not alert at t=26"


# ── 3. Alert Cooldown Tests ───────────────────────────────────────────────────

class TestAlertCooldown:

    def test_cooldown_suppresses_repeat_alerts(self) -> None:
        """After alert fires, repeat alerts are suppressed during the cooldown window."""
        persistence = 10.0
        cooldown = 60.0
        analyzer = TemporalAnalyzer(
            persistence_threshold_sec=persistence,
            alert_cooldown_sec=cooldown,
        )
        analyzer.start_session("sess", timestamp=0.0)

        alerts_received: list[AlertEvent] = []

        # Run for 100 seconds with continuous NECK_FLEXION
        for t in range(0, 101):
            assess = _make_assessment(
                RiskLevel.HIGH,
                "NECK_FLEXION",
                rula=6,
                timestamp=float(t),
            )
            alert = analyzer.process_frame(assess, timestamp=float(t))
            if alert is not None:
                alerts_received.append(alert)

        # Expected:
        # Alert 1 at t=10s
        # During t=11s to t=69s: suppressed by 60s cooldown
        # Alert 2 at t=70s (10s + 60s cooldown)
        # During t=71s to t=100s: suppressed
        assert len(alerts_received) == 2
        assert alerts_received[0].timestamp == pytest.approx(10.0)
        assert alerts_received[1].timestamp == pytest.approx(70.0)


# ── 4. Session Aggregation Tests ──────────────────────────────────────────────

class TestSessionAggregation:

    def test_session_metrics_and_distributions(self) -> None:
        analyzer = TemporalAnalyzer(persistence_threshold_sec=10.0)
        analyzer.start_session("session_123", timestamp=100.0)

        # 4 frames:
        # 1. RULA=2, REBA=2, LOW, NEUTRAL, Expression=Neutral
        # 2. RULA=4, REBA=4, MODERATE, TRUNK_FLEXION, Expression=Neutral
        # 3. RULA=6, REBA=6, HIGH, NECK_FLEXION, Expression=Negative
        # 4. RULA=6, REBA=8, HIGH, NECK_FLEXION, Expression=Reduced
        data = [
            (RiskLevel.LOW, "NEUTRAL", 2, 2, ExpressionCategory.NEUTRAL),
            (RiskLevel.MODERATE, "TRUNK_FLEXION", 4, 4, ExpressionCategory.NEUTRAL),
            (RiskLevel.HIGH, "NECK_FLEXION", 6, 6, ExpressionCategory.NEGATIVE),
            (RiskLevel.HIGH, "NECK_FLEXION", 6, 8, ExpressionCategory.REDUCED),
        ]

        for i, (risk, post, rula, reba, expr) in enumerate(data):
            t = 100.0 + i * 10.0
            assess = _make_assessment(risk, post, rula=rula, reba=reba, timestamp=t)
            expr_res = ExpressionResult(category=expr, confidence=0.9, timestamp=t)
            analyzer.process_frame(assess, expr_res, timestamp=t)

        stats = analyzer.end_session(timestamp=140.0)

        assert stats is not None
        assert stats.session_id == "session_123"
        assert stats.analyzed_frames == 4
        assert stats.avg_rula == pytest.approx((2 + 4 + 6 + 6) / 4.0)  # 4.5
        assert stats.max_rula == 6
        assert stats.avg_reba == pytest.approx((2 + 4 + 6 + 8) / 4.0)  # 5.0
        assert stats.max_reba == 8
        assert stats.dominant_posture == "NECK_FLEXION"
        # 2 out of 4 frames were HIGH/VERY_HIGH -> 50%
        assert stats.high_risk_percentage == pytest.approx(50.0)

        # Serialization
        d = stats.to_dict()
        assert d["session_id"] == "session_123"
        assert d["avg_rula"] == 4.5
        assert "posture_distribution" in d
        assert "expression_distribution" in d


# ── 5. Pipeline Conductor Integration Tests ───────────────────────────────────

class TestTemporalEngineConductor:

    def test_conductor_full_pipeline_flow(self) -> None:
        mock_pose_engine = MagicMock()
        mock_pose_res = MagicMock()
        mock_pose_res.is_detected = True
        mock_pose_res.landmarks = {"NOSE": (0.5, 0.2)}
        mock_pose_engine.process_frame.return_value = mock_pose_res

        mock_face_engine = MagicMock()
        mock_face_engine.is_initialised = False  # skip face for this test

        engine = TemporalEngine(
            pose_engine=mock_pose_engine,
            face_engine=mock_face_engine,
        )
        engine.temporal_analyzer.start_session("cond_sess", timestamp=0.0)

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result: FrameAnalysisResult = engine.process_raw_frame(dummy_frame, timestamp=1.0)

        assert result.is_session_active is True
        assert result.session_id == "cond_sess"
        assert result.assessment is not None
        assert result.pose_result is not None
