"""
REBA (Rapid Entire Body Assessment) Scoring Engine.

Implements the official REBA assessment methodology (Hignett & McAtamney, 2000).
Evaluates whole-body postures combining Group A (Trunk, Neck, Legs) and
Group B (Upper Arm, Lower Arm, Wrist) with load, coupling, and activity modifiers.

All scoring lookup tables are stored as static data structures per PRD §24.

Vision Derivations & Non-Vision Assumptions (PRD Requirement):
--------------------------------------------------------------
The following can be DERIVED from computer vision via PostureParameters:
  - Trunk flexion/extension angle
  - Neck flexion/extension angle
  - Upper arm flexion/extension angle
  - Lower arm flexion angle
  - Wrist flexion/extension angle
  - Knee angle / leg support posture

The following CANNOT be derived from single-camera video alone:
  - Load / Force: Camera cannot weigh objects.
    Assumption / Default: 0 (No load or < 5 kg intermittent, standard for VDU workers).
  - Coupling Score: Camera cannot measure grip friction/ergonomics.
    Assumption / Default: 0 (Good coupling; keyboards/mice have suitable form factor).
  - Activity Score:
    Assumption / Default: 1 (+1 for static seated posture maintained > 1 min).
All defaults can be customized via the RebaCalculator constructor.

Reference:
    Hignett, S., & McAtamney, L. (2000). Rapid Entire Body Assessment (REBA).
    Applied Ergonomics, 31(2), 201-205.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional

from edge_agent.geometry.angle_calculator import PostureParameters

logger = logging.getLogger(__name__)


# ── Action Levels / Risk Mapping ──────────────────────────────────────────────

class RebaActionLevel(IntEnum if False else int, Enum):
    """Official REBA Action Levels (Hignett & McAtamney 2000)."""
    ACTION_LEVEL_0 = 0  # Grand score 1: Negligible risk, no action necessary
    ACTION_LEVEL_1 = 1  # Grand score 2-3: Low risk, change may be necessary
    ACTION_LEVEL_2 = 2  # Grand score 4-7: Medium risk, further investigation needed
    ACTION_LEVEL_3 = 3  # Grand score 8-10: High risk, investigate and implement change soon
    ACTION_LEVEL_4 = 4  # Grand score 11-15: Very high risk, implement change NOW


# ── Official Lookup Tables (Stored as Data) ───────────────────────────────────

# Table A: Trunk (1-5) x Neck (1-3) x Legs (1-4)
# Indexing: TABLE_A[trunk - 1][neck - 1][legs - 1]
TABLE_A: list[list[list[int]]] = [
    # Trunk = 1
    [
        [1, 2, 3, 4],  # Neck = 1
        [2, 3, 4, 5],  # Neck = 2
        [2, 4, 5, 6],  # Neck = 3
    ],
    # Trunk = 2
    [
        [2, 3, 4, 5],  # Neck = 1
        [3, 4, 5, 6],  # Neck = 2
        [4, 5, 6, 7],  # Neck = 3
    ],
    # Trunk = 3
    [
        [2, 4, 5, 6],  # Neck = 1
        [4, 5, 6, 7],  # Neck = 2
        [5, 6, 7, 8],  # Neck = 3
    ],
    # Trunk = 4
    [
        [3, 5, 6, 7],  # Neck = 1
        [5, 6, 7, 8],  # Neck = 2
        [6, 7, 8, 9],  # Neck = 3
    ],
    # Trunk = 5
    [
        [4, 6, 7, 8],  # Neck = 1
        [6, 7, 8, 9],  # Neck = 2
        [7, 8, 9, 9],  # Neck = 3
    ],
]

# Table B: Upper Arm (1-6) x Lower Arm (1-2) x Wrist (1-3)
# Indexing: TABLE_B[upper_arm - 1][lower_arm - 1][wrist - 1]
TABLE_B: list[list[list[int]]] = [
    # Upper Arm = 1
    [
        [1, 2, 3],  # Lower Arm = 1
        [1, 2, 3],  # Lower Arm = 2
    ],
    # Upper Arm = 2
    [
        [1, 2, 3],  # Lower Arm = 1
        [2, 3, 4],  # Lower Arm = 2
    ],
    # Upper Arm = 3
    [
        [3, 4, 5],  # Lower Arm = 1
        [4, 5, 5],  # Lower Arm = 2
    ],
    # Upper Arm = 4
    [
        [4, 5, 5],  # Lower Arm = 1
        [5, 6, 7],  # Lower Arm = 2
    ],
    # Upper Arm = 5
    [
        [6, 7, 8],  # Lower Arm = 1
        [7, 8, 8],  # Lower Arm = 2
    ],
    # Upper Arm = 6
    [
        [7, 8, 8],  # Lower Arm = 1
        [8, 9, 9],  # Lower Arm = 2
    ],
]

# Table C: Score A total (1-12) x Score B total (1-12) -> Score C
# Indexing: TABLE_C[min(score_a, 12) - 1][min(score_b, 12) - 1]
TABLE_C: list[list[int]] = [
    # Score A = 1
    [1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7],
    # Score A = 2
    [1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8],
    # Score A = 3
    [2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8],
    # Score A = 4
    [3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9],
    # Score A = 5
    [4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9, 9],
    # Score A = 6
    [6, 6, 6, 7, 8, 8, 9, 9, 10, 10, 10, 10],
    # Score A = 7
    [7, 7, 7, 8, 9, 9, 9, 10, 10, 11, 11, 11],
    # Score A = 8
    [8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11],
    # Score A = 9
    [9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12],
    # Score A = 10
    [10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12],
    # Score A = 11
    [11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12],
    # Score A = 12
    [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12],
]


# ── REBA Breakdown Data Structure ─────────────────────────────────────────────

@dataclass
class RebaBreakdown:
    """Detailed score breakdown for a REBA evaluation."""
    trunk_score: int = 1
    neck_score: int = 1
    legs_score: int = 1
    table_a_score: int = 1
    load_score: int = 0
    score_a_total: int = 1

    upper_arm_score: int = 1
    lower_arm_score: int = 1
    wrist_score: int = 1
    table_b_score: int = 1
    coupling_score: int = 0
    score_b_total: int = 1

    table_c_score: int = 1
    activity_score: int = 0
    grand_score: int = 1
    action_level: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── REBA Angle Mapping Rules ──────────────────────────────────────────────────

def score_reba_trunk(trunk_angle: Optional[float], *, twisted: bool = False, side_bending: bool = False) -> int:
    """Calculate REBA Trunk Score (1-5).

    - 0° (upright): 1
    - 0° to 20° flexion or extension: 2
    - > 20° to 60° flexion or > 20° extension: 3
    - > 60° flexion: 4
    """
    if trunk_angle is None:
        return 1

    deg = abs(trunk_angle)
    if deg <= 5.0:
        base = 1
    elif deg <= 20.0:
        base = 2
    elif deg <= 60.0:
        base = 3
    else:
        base = 4

    modifier = (1 if twisted else 0) + (1 if side_bending else 0)
    return min(5, base + modifier)


def score_reba_neck(neck_angle: Optional[float], *, twisted: bool = False, side_bending: bool = False) -> int:
    """Calculate REBA Neck Score (1-3).

    - 0° to 20° flexion: 1
    - > 20° flexion or in extension: 2
    """
    if neck_angle is None:
        return 1

    deg = neck_angle
    base = 1 if 0.0 <= deg <= 20.0 else 2
    modifier = (1 if twisted else 0) + (1 if side_bending else 0)
    return min(3, base + modifier)


def score_reba_legs(knee_angle: Optional[float]) -> int:
    """Calculate REBA Legs Score (1-4).

    - Bilateral weight bearing, sitting or walking: 1
    - Unilateral weight bearing: 2
    - Add +1 for knee flexion between 30° and 60°
    - Add +2 for knee flexion > 60° (e.g. squatting)
    Note: For seated office workers, legs are well supported (feet flat), base score = 1.
    """
    # Default for seated desk workers: bilateral support with feet on floor = 1.
    # If standing with significant squat/bend:
    if knee_angle is not None:
        # Seated posture is typically ~90° knee angle with bilateral foot support.
        # Flexion from straight standing (180°):
        flexion = abs(180.0 - knee_angle)
        if flexion > 60.0 and knee_angle < 70.0:
            # Deep squat/unsupported
            return 3
    return 1


def score_reba_upper_arm(shoulder_angle: Optional[float], *, raised: bool = False, abducted: bool = False) -> int:
    """Calculate REBA Upper Arm Score (1-6).

    - 0° to 20° flexion/extension: 1
    - > 20° to 45° flexion or > 20° extension: 2
    - > 45° to 90° flexion: 3
    - > 90° flexion: 4
    """
    if shoulder_angle is None:
        return 1

    deg = abs(shoulder_angle)
    if deg <= 20.0:
        base = 1
    elif deg <= 45.0:
        base = 2
    elif deg <= 90.0:
        base = 3
    else:
        base = 4

    modifier = (1 if raised else 0) + (1 if abducted else 0)
    return min(6, base + modifier)


def score_reba_lower_arm(elbow_angle: Optional[float]) -> int:
    """Calculate REBA Lower Arm Score (1-2).

    - 60° to 100° flexion: 1
    - < 60° or > 100° flexion: 2
    """
    if elbow_angle is None:
        return 1

    deg = abs(elbow_angle)
    return 1 if 60.0 <= deg <= 100.0 else 2


def score_reba_wrist(wrist_angle: Optional[float], *, deviated: bool = False) -> int:
    """Calculate REBA Wrist Score (1-3).

    - 0° to 15° flexion/extension: 1
    - > 15° flexion/extension: 2
    """
    if wrist_angle is None:
        return 1

    deg = abs(wrist_angle)
    base = 1 if deg <= 15.0 else 2
    modifier = 1 if deviated else 0
    return min(3, base + modifier)


# ── REBA Calculator Class ─────────────────────────────────────────────────────

class RebaCalculator:
    """Evaluates REBA scores from PostureParameters.

    Parameters:
        load_score:     Load/force factor (0: < 5 kg, 1: 5-10 kg, 2: > 10 kg). Default: 0.
        coupling_score: Hand coupling factor (0: good, 1: fair, 2: poor). Default: 0.
        activity_score: Activity factor (default: 1 for static seated posture > 1 min).
    """

    def __init__(
        self,
        load_score: int = 0,
        coupling_score: int = 0,
        activity_score: int = 1,
    ) -> None:
        self.load_score = min(2, max(0, load_score))
        self.coupling_score = min(3, max(0, coupling_score))
        self.activity_score = min(3, max(0, activity_score))

    def calculate(self, posture: PostureParameters) -> RebaBreakdown:
        """Compute full REBA breakdown and grand score."""
        # 1. Group A: Trunk, Neck, Legs
        trunk = score_reba_trunk(posture.trunk_angle)
        neck = score_reba_neck(posture.neck_angle)
        legs = score_reba_legs(posture.knee_angle)

        table_a = TABLE_A[trunk - 1][neck - 1][legs - 1]
        score_a_total = min(12, table_a + self.load_score)

        # 2. Group B: Upper Arm, Lower Arm, Wrist
        upper_arm = score_reba_upper_arm(posture.shoulder_angle)
        lower_arm = score_reba_lower_arm(posture.elbow_angle)
        wrist = score_reba_wrist(posture.wrist_angle)

        table_b = TABLE_B[upper_arm - 1][lower_arm - 1][wrist - 1]
        score_b_total = min(12, table_b + self.coupling_score)

        # 3. Table C: Joint score
        row = min(score_a_total, 12) - 1
        col = min(score_b_total, 12) - 1
        table_c = TABLE_C[row][col]

        # 4. Final grand score with activity modifier
        grand_score = min(15, table_c + self.activity_score)

        # 5. Action level mapping
        if grand_score <= 1:
            action_level = 0
        elif grand_score <= 3:
            action_level = 1
        elif grand_score <= 7:
            action_level = 2
        elif grand_score <= 10:
            action_level = 3
        else:
            action_level = 4

        return RebaBreakdown(
            trunk_score=trunk,
            neck_score=neck,
            legs_score=legs,
            table_a_score=table_a,
            load_score=self.load_score,
            score_a_total=score_a_total,
            upper_arm_score=upper_arm,
            lower_arm_score=lower_arm,
            wrist_score=wrist,
            table_b_score=table_b,
            coupling_score=self.coupling_score,
            score_b_total=score_b_total,
            table_c_score=table_c,
            activity_score=self.activity_score,
            grand_score=grand_score,
            action_level=action_level,
        )
