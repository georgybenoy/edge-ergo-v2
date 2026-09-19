"""
Alert Prioritization & Notification Dispatcher (PRD §35).

Enforces single-notification presentation with strict priority ordering:
  1. High-Risk Posture (VERY_HIGH risk)
  2. Posture Warning (HIGH risk)
  3. Movement Break Reminder (Work duration elapsed)
  4. Hydration Reminder (Hydration interval elapsed)

Multiple notifications NEVER appear simultaneously. Higher-priority alerts
immediately preempt lower-priority ones.
"""

from __future__ import annotations

from enum import IntEnum
import logging
import time
from typing import Any, Optional
import uuid

from edge_agent.config.config_manager import EdgeConfig
from edge_agent.feedback.recommendations import (
    Recommendation,
    get_break_recommendation,
    get_hydration_recommendation,
    get_posture_recommendation,
)
from edge_agent.temporal.analyzer import AlertEvent

logger = logging.getLogger(__name__)


# ── Alert Priority Ordering (PRD §35) ─────────────────────────────────────────

class AlertPriority(IntEnum):
    """Notification priority hierarchy. Lower integer = higher priority."""
    HIGH_RISK_POSTURE = 1     # Highest priority (VERY_HIGH risk)
    POSTURE_WARNING = 2       # High risk posture
    MOVEMENT_BREAK = 3        # Movement break nudge
    HYDRATION_REMINDER = 4    # Lowest priority wellness reminder


# ── Notification Item ─────────────────────────────────────────────────────────

class NotificationItem:
    """A formatted notification card to display on the desktop overlay."""

    def __init__(
        self,
        priority: AlertPriority,
        title: str,
        headline: str,
        action_tip: str,
        condition: str,
        created_at: float,
        duration_sec: float = 6.0,
        disclaimer: str = "",
        risk_level: Optional[str] = None,
        rula_score: Optional[int] = None,
        reba_score: Optional[int] = None,
        notification_id: Optional[str] = None,
    ) -> None:
        self.id = notification_id or str(uuid.uuid4())
        self.priority = priority
        self.title = title
        self.headline = headline
        self.action_tip = action_tip
        self.condition = condition
        self.created_at = created_at
        self.duration_sec = duration_sec
        self.disclaimer = disclaimer
        self.risk_level = risk_level
        self.rula_score = rula_score
        self.reba_score = reba_score

    @property
    def expires_at(self) -> float:
        return self.created_at + self.duration_sec

    def is_expired(self, current_time: float) -> bool:
        return current_time >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": int(self.priority),
            "title": self.title,
            "headline": self.headline,
            "action_tip": self.action_tip,
            "condition": self.condition,
            "created_at": self.created_at,
            "duration_sec": self.duration_sec,
            "disclaimer": self.disclaimer,
            "risk_level": self.risk_level,
            "rula_score": self.rula_score,
            "reba_score": self.reba_score,
        }


# ── Alert Engine ──────────────────────────────────────────────────────────────

class AlertEngine:
    """Manages notification queuing, priority preemption, and wellness timers.

    Parameters:
        config:                 Optional EdgeConfig instance.
        break_interval_min:     Minutes between movement break nudges (default: 45.0).
        hydration_interval_min: Minutes between hydration reminders (default: 60.0).
        card_duration_sec:      Seconds each notification displays before auto-dismissing.
    """

    def __init__(
        self,
        config: Optional[EdgeConfig] = None,
        *,
        break_interval_min: Optional[float] = None,
        hydration_interval_min: float = 60.0,
        card_duration_sec: float = 6.0,
    ) -> None:
        if config is not None:
            self.break_interval_sec = (
                (break_interval_min or config.break_interval_min) * 60.0
            )
        else:
            self.break_interval_sec = (break_interval_min or 45.0) * 60.0

        self.hydration_interval_sec = hydration_interval_min * 60.0
        self.card_duration_sec = card_duration_sec

        # State
        self._active_notification: Optional[NotificationItem] = None
        self._pending_queue: list[NotificationItem] = []
        self._last_break_time: float = 0.0
        self._last_hydration_time: float = 0.0

    @property
    def active_notification(self) -> Optional[NotificationItem]:
        return self._active_notification

    @property
    def queue_size(self) -> int:
        return len(self._pending_queue)

    def initialize_timers(self, start_time: float) -> None:
        """Initialize reference timestamps for break and hydration tracking."""
        self._last_break_time = start_time
        self._last_hydration_time = start_time

    # ── Temporal Event Handling ───────────────────────────────────────

    def handle_temporal_alert(
        self,
        alert_event: AlertEvent,
    ) -> Optional[NotificationItem]:
        """Convert a persistence-based AlertEvent into a prioritized NotificationItem.

        Determines priority:
          - VERY_HIGH risk -> HIGH_RISK_POSTURE (Priority 1)
          - HIGH risk -> POSTURE_WARNING (Priority 2)
        """
        is_very_high = alert_event.risk_level == "VERY_HIGH" or alert_event.rula_score >= 7
        priority = AlertPriority.HIGH_RISK_POSTURE if is_very_high else AlertPriority.POSTURE_WARNING

        rec: Recommendation = get_posture_recommendation(alert_event.condition)

        item = NotificationItem(
            priority=priority,
            title=rec.title,
            headline=rec.headline,
            action_tip=rec.action_tip,
            condition=alert_event.condition,
            created_at=alert_event.timestamp,
            duration_sec=self.card_duration_sec,
            disclaimer=rec.disclaimer,
            risk_level=alert_event.risk_level,
            rula_score=alert_event.rula_score,
            reba_score=alert_event.reba_score,
        )

        return self._dispatch(item)

    # ── Wellness Reminders (Breaks & Hydration) ─────────────────────────

    def check_wellness_reminders(
        self,
        current_time: float,
    ) -> Optional[NotificationItem]:
        """Check if work duration warrants a movement break or hydration nudge."""
        if self._last_break_time <= 0.0:
            self._last_break_time = current_time
        if self._last_hydration_time <= 0.0:
            self._last_hydration_time = current_time

        # Check movement break first (Priority 3 > Priority 4)
        if current_time - self._last_break_time >= self.break_interval_sec:
            self._last_break_time = current_time
            rec = get_movement_break_recommendation()
            item = NotificationItem(
                priority=AlertPriority.MOVEMENT_BREAK,
                title=rec.title,
                headline=rec.headline,
                action_tip=rec.action_tip,
                condition=rec.condition,
                created_at=current_time,
                duration_sec=self.card_duration_sec,
                disclaimer=rec.disclaimer,
            )
            return self._dispatch(item)

        # Check hydration reminder (Priority 4)
        if current_time - self._last_hydration_time >= self.hydration_interval_sec:
            self._last_hydration_time = current_time
            rec = get_hydration_recommendation()
            item = NotificationItem(
                priority=AlertPriority.HYDRATION_REMINDER,
                title=rec.title,
                headline=rec.headline,
                action_tip=rec.action_tip,
                condition=rec.condition,
                created_at=current_time,
                duration_sec=self.card_duration_sec,
                disclaimer=rec.disclaimer,
            )
            return self._dispatch(item)

        return None

    # ── Priority Dispatch & Preemption Logic ───────────────────────────

    def _dispatch(self, item: NotificationItem) -> NotificationItem:
        """Route notification respecting strict priority and no-overlap constraints."""
        if self._active_notification is None:
            # Slot is open
            self._active_notification = item
            return item

        # Check for preemption: strictly lower numeric priority value means higher urgency
        if item.priority < self._active_notification.priority:
            logger.info(
                "Preempting active alert '%s' (priority %d) with higher priority '%s' (priority %d)",
                self._active_notification.title,
                self._active_notification.priority,
                item.title,
                item.priority,
            )
            # Demote currently active alert to pending queue if not expired
            if not self._active_notification.is_expired(item.created_at):
                self._pending_queue.append(self._active_notification)
            self._active_notification = item
            return item

        # Equal or lower priority: avoid spamming duplicates into queue
        if not any(p.condition == item.condition for p in self._pending_queue):
            self._pending_queue.append(item)
            # Sort queue by priority ascending (highest priority first)
            self._pending_queue.sort(key=lambda x: int(x.priority))

        return self._active_notification

    # ── Polling & Auto-Dismiss ─────────────────────────────────────────

    def poll(self, current_time: float) -> Optional[NotificationItem]:
        """Check expiration of active notification and pop next from queue."""
        if self._active_notification is not None:
            if self._active_notification.is_expired(current_time):
                logger.debug("Active notification '%s' auto-dismissed", self._active_notification.title)
                self._active_notification = None

        if self._active_notification is None and self._pending_queue:
            # Pop highest priority pending notification
            self._pending_queue.sort(key=lambda x: int(x.priority))
            next_item = self._pending_queue.pop(0)
            # Refresh creation timestamp so it gets full display duration
            next_item.created_at = current_time
            self._active_notification = next_item

        return self._active_notification

    def dismiss_current(self) -> Optional[NotificationItem]:
        """Manually close active notification card."""
        dismissed = self._active_notification
        self._active_notification = None
        return dismissed
