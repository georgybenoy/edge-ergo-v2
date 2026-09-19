"""
EdgeErgo — Temporal Engine.

Provides:
  - TemporalAnalyzer: Posture persistence tracking and alert cooldown.
  - TemporalEngine: Pipeline conductor orchestrating vision -> geometry -> ergonomics -> temporal.
  - AlertEvent: Triggered ergonomic warning event.
  - SessionStats: Aggregated session metrics for storage and telemetry.
  - FrameAnalysisResult: Single-frame pipeline output.
"""

from edge_agent.temporal.analyzer import (
    ALERT_MESSAGES,
    AlertEvent,
    FrameAnalysisResult,
    SessionStats,
    TemporalAnalyzer,
    TemporalEngine,
)

__all__ = [
    "TemporalAnalyzer",
    "TemporalEngine",
    "AlertEvent",
    "SessionStats",
    "FrameAnalysisResult",
    "ALERT_MESSAGES",
]
