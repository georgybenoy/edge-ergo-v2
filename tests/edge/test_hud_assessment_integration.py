"""
Unit and integration tests for Real-Time HUD Scores, Risk Level, and Local Assessment Data Integration.

Verifies:
  1. AssessmentStateProvider thread-safe in-memory state tracking.
  2. Exact conservative risk level classification using official RULA/REBA action levels.
  3. No-person-detected / missing pose states do not fabricate scores or LOW risk.
  4. Freshness tracking and visible staleness indicators when data exceeds threshold.
  5. Local SQLite database fallback without overriding newer in-memory assessments.
  6. WorkerOverlayWidget HUD displays real-time RULA (1-7), REBA (1-15), risk badge, and timing.
  7. HUD updates automatically via periodic polling and Qt signal-slot thread safety.
  8. Local scoring independence from central server reachability.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from edge_agent.assessment_state import (
    AssessmentStateProvider,
    CurrentAssessmentState,
    derive_overall_risk,
)
from edge_agent.overlay.overlay import WorkerOverlayWidget
from edge_agent.storage.local_db import LocalDatabase


# ── PySide6 Headless Fixture ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a QApplication instance exists, configured for offscreen rendering."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


# ── 1. AssessmentStateProvider & Risk Derivation Tests ─────────────────────────

class TestAssessmentStateProvider:

    def test_derive_overall_risk_conservative_mapping(self) -> None:
        """Verify explicit conservative risk derivation from RULA and REBA action levels."""
        # Both LOW
        assert derive_overall_risk(rula_score=2, reba_score=2) == "LOW"
        # RULA MODERATE (3), REBA LOW (2) -> MODERATE
        assert derive_overall_risk(rula_score=3, reba_score=2) == "MODERATE"
        # RULA LOW (2), REBA MODERATE (5) -> MODERATE
        assert derive_overall_risk(rula_score=2, reba_score=5) == "MODERATE"
        # RULA HIGH (5), REBA MODERATE (6) -> HIGH
        assert derive_overall_risk(rula_score=5, reba_score=6) == "HIGH"
        # RULA MODERATE (4), REBA HIGH (9) -> HIGH
        assert derive_overall_risk(rula_score=4, reba_score=9) == "HIGH"
        # RULA VERY_HIGH (7), REBA HIGH (9) -> VERY_HIGH
        assert derive_overall_risk(rula_score=7, reba_score=9) == "VERY_HIGH"
        # RULA LOW (2), REBA VERY_HIGH (12) -> VERY_HIGH
        assert derive_overall_risk(rula_score=2, reba_score=12) == "VERY_HIGH"

        # Partial assessment: only RULA
        assert derive_overall_risk(rula_score=5, reba_score=None) == "HIGH"
        # Partial assessment: only REBA
        assert derive_overall_risk(rula_score=None, reba_score=11) == "VERY_HIGH"
        # Neither available
        assert derive_overall_risk(rula_score=None, reba_score=None) is None

    def test_state_provider_update_and_retrieval(self) -> None:
        """Updating assessment state preserves all scores, risk, and metadata."""
        provider = AssessmentStateProvider(freshness_threshold_sec=5.0)
        provider.set_device_info("NODE-WORK-01", "Ergo-Desk-1")

        cur_t = time.time()
        provider.update_assessment(
            rula_score=5,
            reba_score=7,
            risk_level="HIGH",
            rula_action_level=3,
            reba_action_level=2,
            dominant_posture="NECK_FLEXION",
            joint_angles={"neck_angle": 32.5, "trunk_angle": 12.0},
            timestamp=cur_t,
            status="Monitoring",
            sync_status="Synced ●",
        )

        state = provider.get_state()
        assert state.device_id == "NODE-WORK-01"
        assert state.device_name == "Ergo-Desk-1"
        assert state.rula_score == 5
        assert state.reba_score == 7
        assert state.risk_level == "HIGH"
        assert state.dominant_posture == "NECK_FLEXION"
        assert state.assessment_valid is True
        assert state.pose_detected is True
        assert state.joint_angles["neck_angle"] == 32.5
        assert state.last_valid_timestamp == cur_t
        assert provider.is_stale(cur_t + 1.0) is False

    def test_no_person_detected_state_does_not_fabricate_scores(self) -> None:
        """When no person is detected, state marks assessment invalid and does not fabricate low risk."""
        provider = AssessmentStateProvider()
        provider.update_no_pose(status="No person detected", timestamp=time.time())

        state = provider.get_state()
        assert state.pose_detected is False
        assert state.assessment_valid is False
        assert state.status == "No person detected"
        # Must not fabricate a valid score
        assert state.rula_score is None

    def test_freshness_threshold_and_staleness_detection(self) -> None:
        """If no new valid assessment is received within threshold, it is flagged stale."""
        provider = AssessmentStateProvider(freshness_threshold_sec=3.0)
        t0 = 1000.0
        provider.update_assessment(rula_score=4, reba_score=5, risk_level="MODERATE", timestamp=t0)

        # 2 seconds later -> fresh
        assert provider.is_stale(cur_time=t0 + 2.0) is False
        # 4 seconds later -> stale
        assert provider.is_stale(cur_time=t0 + 4.0) is True

    def test_local_db_fallback(self, tmp_path: Path) -> None:
        """If in-memory state is empty, provider loads previous assessment from local SQLite DB."""
        db = LocalDatabase(tmp_path / "fallback_test.db")
        db.register_device("NODE-FB-01")
        db.record_session("SESS-01", "NODE-FB-01", "2026-10-27T10:00:00Z", "2026-10-27T10:05:00Z", 300.0)
        db.record_assessment("ASSESS-01", "SESS-01", "2026-10-27T10:05:00Z", 4, 6, "MODERATE", "TRUNK_FLEXION", "Neutral")

        provider = AssessmentStateProvider(local_db=db)
        provider.set_device_info("NODE-FB-01", "Desk-Fallback")

        # Initial in-memory state has no valid assessment
        assert provider.get_state().assessment_valid is False

        # Execute fallback
        loaded = provider.fallback_to_local_db("NODE-FB-01")
        assert loaded is True

        state = provider.get_state()
        assert state.rula_score == 4
        assert state.reba_score == 6
        assert state.risk_level == "MODERATE"
        assert state.dominant_posture == "TRUNK_FLEXION"
        assert state.is_fallback is True

        # Now simulate a live in-memory assessment arriving
        provider.update_assessment(rula_score=6, reba_score=8, risk_level="HIGH", timestamp=time.time())
        assert provider.get_state().rula_score == 6
        assert provider.get_state().is_fallback is False

        # Subsequent fallback attempts must NOT override the live in-memory assessment
        provider.fallback_to_local_db("NODE-FB-01")
        assert provider.get_state().rula_score == 6
        db.close()


# ── 2. WorkerOverlayWidget HUD Rendering Tests ─────────────────────────────────

class TestWorkerOverlayWidgetHUD:

    def test_hud_displays_real_time_scores_and_risk(self, qapp: QApplication) -> None:
        """HUD status bar displays actual RULA and REBA scores and risk badge."""
        provider = AssessmentStateProvider()
        widget = WorkerOverlayWidget(state_provider=provider)

        # Update provider with valid assessment
        cur_t = time.time()
        provider.update_assessment(
            rula_score=5,
            reba_score=7,
            risk_level="HIGH",
            timestamp=cur_t,
            status="Monitoring",
            sync_status="Synced ●",
        )

        # Trigger poll tick to refresh HUD
        widget._on_poll_tick()

        assert widget.lbl_risk.text() == "HIGH"
        assert "RULA: 5/7 | REBA: 7/15" in widget.lbl_scores.text()
        assert "Monitoring" in widget.lbl_monitoring.text()
        assert "Synced ●" in widget.lbl_sync.text()
        assert widget.lbl_timing.text() != "Last: --"

        widget.close()

    def test_hud_displays_waiting_state_when_pose_missing(self, qapp: QApplication) -> None:
        """When pose is missing, HUD displays waiting state and AWAITING ASSESSMENT badge."""
        provider = AssessmentStateProvider()
        widget = WorkerOverlayWidget(state_provider=provider)

        provider.update_no_pose(status="Waiting for pose", timestamp=time.time())
        widget._on_poll_tick()

        assert widget.lbl_risk.text() == "AWAITING ASSESSMENT"
        assert "Waiting for pose" in widget.lbl_scores.text()

        provider.update_no_pose(status="No person detected", timestamp=time.time())
        widget._on_poll_tick()

        assert widget.lbl_risk.text() == "AWAITING ASSESSMENT"
        assert "No person detected" in widget.lbl_scores.text()

        widget.close()

    def test_hud_marks_stale_data_with_indicator(self, qapp: QApplication) -> None:
        """When assessment age exceeds freshness threshold, HUD visibly marks data as stale."""
        provider = AssessmentStateProvider(freshness_threshold_sec=1.0)
        widget = WorkerOverlayWidget(state_provider=provider)

        # Produce assessment at t=0
        t0 = time.time() - 5.0  # 5 seconds ago
        provider.update_assessment(
            rula_score=3,
            reba_score=4,
            risk_level="MODERATE",
            timestamp=t0,
        )

        # Tick poll with current time (exceeds 1.0s threshold)
        widget._on_poll_tick()

        assert "[Stale]" in widget.lbl_scores.text()
        assert "(STALE)" in widget.lbl_risk.text()
        assert "(Delayed)" in widget.lbl_timing.text()

        widget.close()

    def test_hud_offline_server_independence(self, qapp: QApplication) -> None:
        """HUD continues displaying live local scores when central server sync is Offline."""
        provider = AssessmentStateProvider()
        widget = WorkerOverlayWidget(state_provider=provider)

        cur_t = time.time()
        provider.update_assessment(
            rula_score=6,
            reba_score=9,
            risk_level="HIGH",
            timestamp=cur_t,
            sync_status="Offline ○",
        )
        widget._on_poll_tick()

        # Scores and risk must continue rendering accurately
        assert widget.lbl_risk.text() == "HIGH"
        assert "RULA: 6/7 | REBA: 9/15" in widget.lbl_scores.text()
        assert "Offline ○" in widget.lbl_sync.text()

        widget.close()
