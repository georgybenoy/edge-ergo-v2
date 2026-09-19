"""
EdgeErgo — Aggregation Package (PRD §50).
"""

from central_server.aggregation.aggregator import (
    AggregatedMetrics,
    TelemetryAggregator,
    aggregate_telemetry,
    categorize_rula_risk,
)

__all__ = [
    "AggregatedMetrics",
    "TelemetryAggregator",
    "aggregate_telemetry",
    "categorize_rula_risk",
]
