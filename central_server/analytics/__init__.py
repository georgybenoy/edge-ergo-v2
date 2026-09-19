"""
EdgeErgo — Analytics Package (PRD §51, §54, §55).
"""

from central_server.analytics.analytics import (
    AnalyticsEngine,
    get_combined_correlations,
    get_time_based_trends,
    get_workstation_summaries,
)

__all__ = [
    "AnalyticsEngine",
    "get_combined_correlations",
    "get_time_based_trends",
    "get_workstation_summaries",
]
