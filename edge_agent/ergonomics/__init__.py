"""
EdgeErgo — Ergonomics Assessment Module.

Provides:
  - assess(): Main entry point evaluating posture via RULA and REBA.
  - RiskLevel: Unified risk level classification (LOW, MODERATE, HIGH, VERY_HIGH).
  - AssessmentResult: Unified assessment output with breakdowns and dominant posture.
  - RulaCalculator, RulaBreakdown, RulaActionLevel.
  - RebaCalculator, RebaBreakdown, RebaActionLevel.
"""

from edge_agent.ergonomics.reba import (
    RebaActionLevel,
    RebaBreakdown,
    RebaCalculator,
    score_reba_legs,
    score_reba_lower_arm,
    score_reba_neck,
    score_reba_trunk,
    score_reba_upper_arm,
    score_reba_wrist,
)
from edge_agent.ergonomics.rula import (
    RulaActionLevel,
    RulaBreakdown,
    RulaCalculator,
    score_legs,
    score_lower_arm,
    score_neck,
    score_trunk,
    score_upper_arm,
    score_wrist,
)
from edge_agent.ergonomics.scoring import (
    AssessmentResult,
    RiskLevel,
    assess,
    identify_dominant_posture,
    map_risk_level,
)

__all__ = [
    # Main scoring orchestrator
    "assess",
    "AssessmentResult",
    "RiskLevel",
    "map_risk_level",
    "identify_dominant_posture",
    # RULA
    "RulaCalculator",
    "RulaBreakdown",
    "RulaActionLevel",
    "score_upper_arm",
    "score_lower_arm",
    "score_wrist",
    "score_neck",
    "score_trunk",
    "score_legs",
    # REBA
    "RebaCalculator",
    "RebaBreakdown",
    "RebaActionLevel",
    "score_reba_trunk",
    "score_reba_neck",
    "score_reba_legs",
    "score_reba_upper_arm",
    "score_reba_lower_arm",
    "score_reba_wrist",
]
