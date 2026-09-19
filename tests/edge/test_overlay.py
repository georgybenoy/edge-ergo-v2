"""
Tests for edge_agent/overlay/overlay.py, edge_agent/feedback/alert_engine.py,
and edge_agent/feedback/recommendations.py.

Validates:
  1. Specific actionable recommendations per detected condition (PRD §32).
  2. General non-medical wellness disclaimers for break and hydration nudges (PRD §34).
  3. Alert priority ordering and preemption (PRD §35):
     High-Risk Posture > Posture Warning > Movement Break > Hydration Reminder.
  4. Non-overlapping notification rule (PRD §35): exactly one card visible at a time.
  5. Auto-dismiss and manual dismiss mechanics.
  6. PySide6 WorkerOverlayWidget headless execution:
     - Status bar rendering (monitoring state, risk badge, last/next times, sync status).
     - Transient card display and dismissal.
"""

from __future__ import annotations

import os
import sys
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from edge_agent.feedback.alert_engine import (
    AlertEngine,
    AlertPriority,
    NotificationItem,
)
from edge_agent.feedback.recommendations import (
    POSTURE_RECOMMENDATIONS,
    get_break_recommendation,
    get_hydration_recommendation,
    get_movement_break_recommendation,
    get_posture_recommendation,
)
from edge_agent.overlay.overlay import WorkerOverlayWidget
from edge_agent.temporal.analyzer import AlertEvent


# ── PySide6 Headless Setup Fixture ────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a QApplication instance exists, configured for headless execution."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


# ── 1. Recommendations Unit Tests ─────────────────────────────────────────────

class TestRecommendations:

    def test_posture_recommendations_are_specific(self) -> None:
        """Every detected condition has a distinct, non-generic recommendation."""
        conditions = ["NECK_FLEXION", "TRUNK_FLEXION", "SHOULDER_ELEVATION", "WRIST_DEVIATION"]
        seen_tips = set()

        for cond in conditions:
            rec = get_posture_recommendation(cond)
            assert rec.condition == cond
            assert len(rec.headline) > 5
            assert len(rec.action_tip) > 10
            assert rec.action_tip not in seen_tips, "Recommendations must not be generic copies"
            seen_tips.add(rec.action_tip)

    def test_movement_break_contains_non_medical_disclaimer(self) -> None:
        """PRD §34: Movement breaks must be framed as general wellness, not medical advice."""
        rec = get_movement_break_recommendation()
        assert "not medical advice" in rec.disclaimer.lower()
        assert "wellness" in rec.disclaimer.lower()

    def test_hydration_reminder_contains_non_medical_disclaimer(self) -> None:
        """PRD §34: Hydration reminders must be framed as general wellness, not medical advice."""
        rec = get_hydration_recommendation()
        assert "not medical advice" in rec.disclaimer.lower()
        assert "wellness" in rec.disclaimer.lower()


# ── 2. Alert Priority & Preemption Tests ───────────────────────────────────────

class TestAlertPriorityAndEngine:

    def test_priority_hierarchy_values(self) -> None:
        """Lower integer value = strictly higher priority."""
        assert AlertPriority.HIGH_RISK_POSTURE < AlertPriority.POSTURE_WARNING
        assert AlertPriority.POSTURE_WARNING < AlertPriority.MOVEMENT_BREAK
        assert AlertPriority.MOVEMENT_BREAK < AlertPriority.HYDRATION_REMINDER

    def test_higher_priority_preempts_active_lower_priority(self) -> None:
        """PRD §35: High-Risk Posture immediately preempts a showing Hydration nudge."""
        engine = AlertEngine(card_duration_sec=10.0)

        # 1. Post hydration reminder (Priority 4)
        item_hydro = NotificationItem(
            priority=AlertPriority.HYDRATION_REMINDER,
            title="Hydration",
            headline="Drink water",
            action_tip="Sip water",
            condition="HYDRATION",
            created_at=100.0,
        )
        engine._dispatch(item_hydro)
        assert engine.active_notification is not None
        assert engine.active_notification.priority == AlertPriority.HYDRATION_REMINDER

        # 2. High-Risk posture event arrives at t=102s (Priority 1)
        alert_event = AlertEvent(
            condition="NECK_FLEXION",
            risk_level="VERY_HIGH",
            rula_score=7,
            reba_score=8,
            duration_sec=20.0,
            timestamp=102.0,
            message="Neck bent forward",
        )
        dispatched = engine.handle_temporal_alert(alert_event)

        # Must have preempted the hydration notification!
        assert engine.active_notification is not None
        assert engine.active_notification.priority == AlertPriority.HIGH_RISK_POSTURE
        assert engine.active_notification.condition == "NECK_FLEXION"
        # Preempted hydration was preserved in pending queue
        assert engine.queue_size == 1

    def test_lower_priority_does_not_preempt_higher_priority(self) -> None:
        """When high-risk warning is showing, a movement break waits in queue."""
        engine = AlertEngine(card_duration_sec=10.0)

        alert_event = AlertEvent(
            condition="TRUNK_FLEXION",
            risk_level="HIGH",
            rula_score=5,
            reba_score=5,
            duration_sec=20.0,
            timestamp=100.0,
            message="Hunched torso",
        )
        engine.handle_temporal_alert(alert_event)
        assert engine.active_notification is not None
        assert engine.active_notification.priority == AlertPriority.POSTURE_WARNING

        # Break reminder fires at t=102s (Priority 3)
        item_break = NotificationItem(
            priority=AlertPriority.MOVEMENT_BREAK,
            title="Break",
            headline="Stretch",
            action_tip="Take a walk",
            condition="BREAK",
            created_at=102.0,
        )
        engine._dispatch(item_break)

        # Active must still be the posture warning!
        assert engine.active_notification.priority == AlertPriority.POSTURE_WARNING
        assert engine.queue_size == 1

    def test_single_card_no_overlapping_popups(self) -> None:
        """PRD §35: Multiple notifications must never appear simultaneously."""
        engine = AlertEngine()
        # Active slot holds at most one notification
        assert engine.active_notification is None

        event1 = AlertEvent("NECK_FLEXION", "HIGH", 5, 5, 20.0, 10.0, "tip 1")
        event2 = AlertEvent("TRUNK_FLEXION", "HIGH", 5, 5, 20.0, 11.0, "tip 2")

        engine.handle_temporal_alert(event1)
        engine.handle_temporal_alert(event2)

        # Only one active
        assert engine.active_notification is not None
        assert engine.active_notification.condition == "NECK_FLEXION"

    def test_auto_dismiss_and_queue_promotion(self) -> None:
        """Expired cards dismiss and promote the next queued item."""
        engine = AlertEngine(card_duration_sec=5.0)

        item1 = NotificationItem(
            priority=AlertPriority.POSTURE_WARNING,
            title="Alert 1",
            headline="H1",
            action_tip="A1",
            condition="C1",
            created_at=10.0,
            duration_sec=5.0,
        )
        item2 = NotificationItem(
            priority=AlertPriority.MOVEMENT_BREAK,
            title="Alert 2",
            headline="H2",
            action_tip="A2",
            condition="C2",
            created_at=10.0,
            duration_sec=5.0,
        )

        engine._dispatch(item1)
        engine._dispatch(item2)

        # At t=12s: item1 still active
        assert engine.poll(12.0) == item1

        # At t=16s: item1 expired (created at 10, dur 5 -> expired at 15)
        promoted = engine.poll(16.0)
        assert promoted is not None
        assert promoted.title == "Alert 2"
        assert engine.queue_size == 0

    def test_manual_dismissal(self) -> None:
        engine = AlertEngine()
        item = NotificationItem(
            priority=AlertPriority.POSTURE_WARNING,
            title="Alert",
            headline="H",
            action_tip="A",
            condition="C",
            created_at=10.0,
        )
        engine._dispatch(item)
        assert engine.active_notification is not None

        dismissed = engine.dismiss_current()
        assert dismissed == item
        assert engine.active_notification is None


# ── 3. Worker Overlay PySide6 Headless Tests ──────────────────────────────────

class TestWorkerOverlayWidget:

    def test_overlay_creation_and_flags(self, qapp: QApplication) -> None:
        engine = AlertEngine()
        widget = WorkerOverlayWidget(alert_engine=engine)

        flags = widget.windowFlags()
        assert bool(flags & Qt.WindowType.FramelessWindowHint)
        assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        assert bool(flags & Qt.WindowType.Tool)

        widget.close()

    def test_update_status_bar(self, qapp: QApplication) -> None:
        widget = WorkerOverlayWidget()

        # Update to Active monitoring, HIGH risk
        widget.update_status(
            is_monitoring=True,
            risk_level="HIGH",
            last_time_str="14:00",
            next_time_str="14:30",
            sync_status="Synced ●",
        )
        assert "Monitoring" in widget.lbl_monitoring.text()
        assert widget.lbl_risk.text() == "HIGH"
        assert "14:00" in widget.lbl_timing.text()
        assert "14:30" in widget.lbl_timing.text()

        # Update to Idle, LOW risk
        widget.update_status(
            is_monitoring=False,
            risk_level="LOW",
            last_time_str="14:30",
            next_time_str="15:00",
            sync_status="Offline",
        )
        assert "Idle" in widget.lbl_monitoring.text()
        assert widget.lbl_risk.text() == "LOW"

        widget.close()

    def test_show_and_dismiss_notification_card(self, qapp: QApplication) -> None:
        widget = WorkerOverlayWidget()
        widget.show()
        assert widget.card_frame.isVisible() is False

        item = NotificationItem(
            priority=AlertPriority.HIGH_RISK_POSTURE,
            title="⚠️ Posture Nudge",
            headline="Maintain neutral neck",
            action_tip="Raise monitor",
            condition="NECK_FLEXION",
            created_at=time.monotonic(),
        )

        widget.show_notification(item)
        assert widget.card_frame.isVisible() is True
        assert widget.lbl_headline.text() == "Maintain neutral neck"
        assert widget.lbl_action.text() == "Raise monitor"

        # Worker clicks dismiss [X]
        widget.dismiss_notification()
        assert widget.card_frame.isVisible() is False

        widget.close()

    def test_toggle_collapse(self, qapp: QApplication) -> None:
        widget = WorkerOverlayWidget()
        widget.show()
        assert widget._is_collapsed is False

        # Collapse
        widget.toggle_collapse()
        assert widget._is_collapsed is True
        assert widget.lbl_timing.isVisible() is False

        # Expand again
        widget.toggle_collapse()
        assert widget._is_collapsed is False
        assert widget.lbl_timing.isVisible() is True

        widget.close()
