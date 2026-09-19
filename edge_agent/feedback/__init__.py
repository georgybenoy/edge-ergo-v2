"""
EdgeErgo — Feedback & Scheduling Module.

Provides:
  - MonitoringScheduler: Controls monitoring operational window, interval, and duration.
  - AlertEngine: Prioritized notification manager preventing overlapping popups.
  - AlertPriority: Priority hierarchy (High-Risk > Posture Warning > Break > Hydration).
  - NotificationItem: Formatted notification card item.
  - Recommendation utilities: Actionable posture guidance and non-medical wellness nudges.
"""

from edge_agent.feedback.alert_engine import (
    AlertEngine,
    AlertPriority,
    NotificationItem,
)
from edge_agent.feedback.recommendations import (
    POSTURE_RECOMMENDATIONS,
    Recommendation,
    get_break_recommendation,
    get_hydration_recommendation,
    get_posture_recommendation,
)
from edge_agent.feedback.scheduler import MonitoringScheduler

__all__ = [
    "MonitoringScheduler",
    "AlertEngine",
    "AlertPriority",
    "NotificationItem",
    "Recommendation",
    "POSTURE_RECOMMENDATIONS",
    "get_posture_recommendation",
    "get_movement_break_recommendation",
    "get_hydration_recommendation",
]
