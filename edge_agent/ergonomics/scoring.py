"""
Ergonomic Assessment Orchestrator.

Combines RULA and REBA assessment engines into a unified assessment result.
Maps standard Action Levels to unified RiskLevel (LOW, MODERATE, HIGH, VERY HIGH)
per PRD §25 and identifies the dominant driving posture.

Reference:
    PRD §22: Ergonomic Assessment Engine
    PRD §25: Risk Classification (derived directly from official action levels)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

from edge_agent.ergonomics.reba import RebaBreakdown, RebaCalculator
from edge_agent.ergonomics.rula import RulaBreakdown, RulaCalculator
from edge_agent.geometry.angle_calculator import PostureParameters

logger = logging.getLogger(__name__)


# ── Unified Risk Level (PRD §25) ──────────────────────────────────────────────

class RiskLevel(str, Enum):
    """Unified Ergonomic Risk Classification.

    Strictly derived from official RULA/REBA Action Level mappings:
      - LOW:        RULA Action Level 1 (Score 1-2) or REBA Action Level 0-1 (Score 1-3).
                    Acceptable posture, no immediate action needed.
      - MODERATE:   RULA Action Level 2 (Score 3-4) or REBA Action Level 2 (Score 4-7).
                    Further investigation needed; changes may be required.
      - HIGH:       RULA Action Level 3 (Score 5-6) or REBA Action Level 3 (Score 8-10).
                    Prompt investigation and changes required soon.
      - VERY_HIGH:  RULA Action Level 4 (Score 7+) or REBA Action Level 4 (Score 11+).
                    Immediate changes required to prevent musculoskeletal injury.
    """
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


# ── Assessment Result Data Structure ──────────────────────────────────────────

@dataclass
class AssessmentResult:
    """Unified assessment output from evaluating a single posture frame.

    Attributes:
        rula_score:        RULA Grand Score [1, 7].
        reba_score:        REBA Grand Score [1, 15].
        risk_level:        Unified RiskLevel (LOW / MODERATE / HIGH / VERY HIGH).
        dominant_posture:  Name of the joint/angle primarily driving the risk score.
        rula_action_level: Official RULA Action Level (1 to 4).
        reba_action_level: Official REBA Action Level (0 to 4).
        rula_breakdown:    Detailed RULA segment scores.
        reba_breakdown:    Detailed REBA segment scores.
        posture_parameters: Raw/smoothed angles used for evaluation.
        timestamp:         Frame timestamp in seconds.
        is_valid:          False if posture parameters were unavailable/empty.
    """

    rula_score: int
    reba_score: int
    risk_level: RiskLevel
    dominant_posture: str
    rula_action_level: int
    reba_action_level: int
    rula_breakdown: RulaBreakdown
    reba_breakdown: RebaBreakdown
    posture_parameters: PostureParameters
    timestamp: float = 0.0
    is_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert assessment result to a dictionary for telemetry/reporting."""
        return {
            "rula_score": self.rula_score,
            "reba_score": self.reba_score,
            "risk_level": self.risk_level.value,
            "dominant_posture": self.dominant_posture,
            "rula_action_level": self.rula_action_level,
            "reba_action_level": self.reba_action_level,
            "rula_breakdown": self.rula_breakdown.to_dict(),
            "reba_breakdown": self.reba_breakdown.to_dict(),
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
        }


# ── Risk Level Mapping ────────────────────────────────────────────────────────

def map_risk_level(rula_action_level: int, reba_action_level: int) -> RiskLevel:
    """Derive unified RiskLevel from official RULA and REBA action levels.

    Combines both standards using maximum severity logic:
      - Action Level 4 on either standard -> VERY_HIGH
      - Action Level 3 on either standard -> HIGH
      - Action Level 2 on either standard -> MODERATE
      - Action Level 0 or 1 on both -> LOW
    """
    max_action = max(rula_action_level, reba_action_level)
    if max_action >= 4:
        return RiskLevel.VERY_HIGH
    if max_action == 3:
        return RiskLevel.HIGH
    if max_action == 2:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


# ── Dominant Posture Identifier ───────────────────────────────────────────────

def identify_dominant_posture(
    posture: PostureParameters,
    rula: RulaBreakdown,
    reba: RebaBreakdown,
) -> str:
    """Identify which body segment / joint angle is driving the ergonomic risk score.

    Calculates penalty relative to neutral (score - 1) for each anatomical joint.
    Returns a descriptive string (e.g. 'NECK_FLEXION', 'TRUNK_FLEXION', 'NEUTRAL').
    """
    # Compare joint penalties (score - 1 indicates severity above baseline)
    penalties: dict[str, int] = {
        "NECK": max(rula.neck_score - 1, reba.neck_score - 1),
        "TRUNK": max(rula.trunk_score - 1, reba.trunk_score - 1),
        "SHOULDER": max(rula.upper_arm_score - 1, reba.upper_arm_score - 1),
        "ELBOW": max(rula.lower_arm_score - 1, reba.lower_arm_score - 1),
        "WRIST": max(rula.wrist_score - 1, reba.wrist_score - 1),
        "LEGS": max(rula.legs_score - 1, reba.legs_score - 1),
    }

    max_penalty = max(penalties.values())
    if max_penalty <= 0:
        return "NEUTRAL"

    # Prioritize axial spine / neck when penalties are tied (highest clinical priority)
    priority_order = ("NECK", "TRUNK", "SHOULDER", "WRIST", "ELBOW", "LEGS")
    culprit = "NEUTRAL"
    for joint in priority_order:
        if penalties[joint] == max_penalty:
            culprit = joint
            break

    # Construct descriptive posture descriptor based on joint and angle value
    if culprit == "NECK":
        angle = posture.neck_angle or 0.0
        return "NECK_EXTENSION" if angle < 0.0 else "NECK_FLEXION"
    elif culprit == "TRUNK":
        angle = posture.trunk_angle or 0.0
        return "TRUNK_EXTENSION" if angle < 0.0 else "TRUNK_FLEXION"
    elif culprit == "SHOULDER":
        angle = posture.shoulder_angle or 0.0
        return "SHOULDER_ELEVATION" if angle > 45.0 else "ARM_ELEVATION"
    elif culprit == "ELBOW":
        angle = posture.elbow_angle or 0.0
        return "ELBOW_EXTENSION" if angle < 60.0 else "ELBOW_FLEXION"
    elif culprit == "WRIST":
        return "WRIST_DEVIATION"
    elif culprit == "LEGS":
        return "AWKWARD_LEG_POSTURE"

    return "NEUTRAL"


# ── Unified Scoring Entry Point ───────────────────────────────────────────────

def assess(
    posture_parameters: PostureParameters,
    *,
    rula_calculator: Optional[RulaCalculator] = None,
    reba_calculator: Optional[RebaCalculator] = None,
) -> AssessmentResult:
    """Assess ergonomic risk using both RULA and REBA standards.

    Args:
        posture_parameters: Output from the Geometry Engine.
        rula_calculator:    Optional custom RulaCalculator instance.
        reba_calculator:    Optional custom RebaCalculator instance.

    Returns:
        AssessmentResult containing scores, official action levels,
        unified RiskLevel, dominant posture driver, and full breakdowns.
    """
    rula_calc = rula_calculator or RulaCalculator()
    reba_calc = reba_calculator or RebaCalculator()

    # If no angles are available (e.g. no person detected), return clean default
    if posture_parameters.available_angle_count == 0:
        rula_res = rula_calc.calculate(posture_parameters)
        reba_res = reba_calc.calculate(posture_parameters)
        return AssessmentResult(
            rula_score=rula_res.grand_score,
            reba_score=reba_res.grand_score,
            risk_level=RiskLevel.LOW,
            dominant_posture="NO_PERSON_DETECTED",
            rula_action_level=1,
            reba_action_level=0,
            rula_breakdown=rula_res,
            reba_breakdown=reba_res,
            posture_parameters=posture_parameters,
            timestamp=posture_parameters.timestamp,
            is_valid=False,
        )

    rula_breakdown = rula_calc.calculate(posture_parameters)
    reba_breakdown = reba_calc.calculate(posture_parameters)

    risk_level = map_risk_level(
        rula_breakdown.action_level,
        reba_breakdown.action_level,
    )

    dominant = identify_dominant_posture(
        posture_parameters,
        rula_breakdown,
        reba_breakdown,
    )

    return AssessmentResult(
        rula_score=rula_breakdown.grand_score,
        reba_score=reba_breakdown.grand_score,
        risk_level=risk_level,
        dominant_posture=dominant,
        rula_action_level=rula_breakdown.action_level,
        reba_action_level=reba_breakdown.action_level,
        rula_breakdown=rula_breakdown,
        reba_breakdown=reba_breakdown,
        posture_parameters=posture_parameters,
        timestamp=posture_parameters.timestamp,
        is_valid=True,
    )
