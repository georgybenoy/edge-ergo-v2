"""
RULA (Rapid Upper Limb Assessment) Scoring Engine.

Implements the official RULA assessment methodology (McAtamney & Corlett, 1993).
Maps continuous joint angles from PostureParameters to discrete ergonomic
scores using official lookup tables (Table A, Table B, Table C).

All lookup tables are defined as static data constants, strictly decoupled
from computer-vision and geometry code per PRD §23.

Reference:
    McAtamney, L., & Corlett, E. N. (1993). RULA: a survey method for the
    investigation of work-related upper limb disorders. Applied Ergonomics,
    24(2), 91-99.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional

from edge_agent.geometry.angle_calculator import PostureParameters

logger = logging.getLogger(__name__)


# ── Action Levels / Risk Mapping ──────────────────────────────────────────────

class RulaActionLevel(IntEnum if False else int, Enum):  # simple IntEnum compatible
    """Official RULA Action Levels (McAtamney & Corlett 1993)."""
    ACTION_LEVEL_1 = 1  # Grand score 1-2: Acceptable posture
    ACTION_LEVEL_2 = 2  # Grand score 3-4: Further investigation needed
    ACTION_LEVEL_3 = 3  # Grand score 5-6: Investigation and changes required soon
    ACTION_LEVEL_4 = 4  # Grand score 7+:  Changes required immediately


# ── Official Lookup Tables (Stored as Data) ───────────────────────────────────

# Table A: Upper Arm (1-6) x Lower Arm (1-3) x Wrist (1-4) x Wrist Twist (1-2)
# Indexing: TABLE_A[upper_arm - 1][lower_arm - 1][wrist - 1][twist - 1]
TABLE_A: list[list[list[list[int]]]] = [
    # Upper Arm = 1
    [
        [[1, 2], [2, 2], [2, 3], [3, 3]],  # Lower Arm = 1
        [[2, 2], [2, 2], [3, 3], [3, 3]],  # Lower Arm = 2
        [[2, 3], [3, 3], [3, 3], [4, 4]],  # Lower Arm = 3
    ],
    # Upper Arm = 2
    [
        [[2, 3], [3, 3], [3, 4], [4, 4]],  # Lower Arm = 1
        [[3, 3], [3, 3], [3, 4], [4, 4]],  # Lower Arm = 2
        [[3, 4], [4, 4], [4, 4], [5, 5]],  # Lower Arm = 3
    ],
    # Upper Arm = 3
    [
        [[3, 3], [4, 4], [4, 4], [5, 5]],  # Lower Arm = 1
        [[3, 4], [4, 4], [4, 4], [5, 5]],  # Lower Arm = 2
        [[4, 4], [4, 4], [4, 5], [5, 5]],  # Lower Arm = 3
    ],
    # Upper Arm = 4
    [
        [[4, 4], [4, 5], [5, 5], [5, 6]],  # Lower Arm = 1
        [[4, 4], [4, 5], [5, 5], [6, 6]],  # Lower Arm = 2
        [[4, 4], [4, 5], [5, 5], [6, 6]],  # Lower Arm = 3
    ],
    # Upper Arm = 5
    [
        [[5, 5], [5, 6], [6, 7], [7, 7]],  # Lower Arm = 1
        [[5, 6], [6, 6], [6, 7], [7, 7]],  # Lower Arm = 2
        [[5, 6], [6, 7], [7, 7], [7, 8]],  # Lower Arm = 3
    ],
    # Upper Arm = 6
    [
        [[7, 7], [7, 7], [7, 8], [8, 8]],  # Lower Arm = 1
        [[8, 8], [8, 8], [8, 8], [8, 9]],  # Lower Arm = 2
        [[8, 8], [8, 8], [8, 8], [8, 9]],  # Lower Arm = 3
    ],
]

# Table B: Neck (1-6) x Trunk (1-6) x Legs (1-2)
# Indexing: TABLE_B[neck - 1][trunk - 1][legs - 1]
TABLE_B: list[list[list[int]]] = [
    # Neck = 1
    [
        [1, 3], [2, 3], [3, 4], [5, 5], [6, 6], [7, 7]
    ],
    # Neck = 2
    [
        [2, 3], [2, 3], [4, 5], [5, 5], [6, 7], [7, 7]
    ],
    # Neck = 3
    [
        [3, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 7]
    ],
    # Neck = 4
    [
        [5, 5], [5, 6], [6, 7], [7, 7], [7, 7], [8, 8]
    ],
    # Neck = 5
    [
        [7, 7], [7, 7], [7, 8], [8, 8], [8, 8], [8, 8]
    ],
    # Neck = 6
    [
        [8, 8], [8, 8], [8, 8], [8, 9], [9, 9], [9, 9]
    ],
]

# Table C: Grand Score lookup from Score A total (1-8+) and Score B total (1-7+)
# Indexing: TABLE_C[min(score_a, 8) - 1][min(score_b, 7) - 1]
TABLE_C: list[list[int]] = [
    # Score A = 1
    [1, 2, 3, 3, 4, 5, 5],
    # Score A = 2
    [2, 2, 3, 4, 4, 5, 5],
    # Score A = 3
    [3, 3, 3, 4, 4, 5, 6],
    # Score A = 4
    [3, 3, 3, 4, 5, 6, 6],
    # Score A = 5
    [4, 4, 4, 5, 6, 7, 7],
    # Score A = 6
    [4, 4, 5, 6, 6, 7, 7],
    # Score A = 7
    [5, 5, 6, 6, 7, 7, 7],
    # Score A = 8+
    [5, 5, 6, 7, 7, 7, 7],
]


# ── RULA Breakdown Data Structure ─────────────────────────────────────────────

@dataclass
class RulaBreakdown:
    """Detailed score breakdown for a RULA evaluation."""
    upper_arm_score: int = 1
    lower_arm_score: int = 1
    wrist_score: int = 1
    wrist_twist_score: int = 1
    table_a_score: int = 1
    muscle_a_score: int = 0
    force_a_score: int = 0
    score_a_total: int = 1

    neck_score: int = 1
    trunk_score: int = 1
    legs_score: int = 1
    table_b_score: int = 1
    muscle_b_score: int = 0
    force_b_score: int = 0
    score_b_total: int = 1

    grand_score: int = 1
    action_level: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── RULA Angle Mapping Rules ──────────────────────────────────────────────────

def score_upper_arm(shoulder_angle: Optional[float], *, raised: bool = False, abducted: bool = False) -> int:
    """Calculate RULA Upper Arm Score (1-6).

    Angles (elevation from downward torso):
      - 0° to 20° flexion/extension: 1
      - > 20° to 45° flexion: 2
      - > 45° to 90° flexion: 3
      - > 90° flexion: 4
      - > 20° extension: 2
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


def score_lower_arm(elbow_angle: Optional[float], *, across_midline: bool = False) -> int:
    """Calculate RULA Lower Arm Score (1-3).

    In RULA, 60° to 100° elbow flexion is the neutral working zone:
      - 60° to 100° flexion: 1
      - < 60° or > 100° flexion: 2
    """
    if elbow_angle is None:
        return 1

    deg = abs(elbow_angle)
    base = 1 if 60.0 <= deg <= 100.0 else 2
    modifier = 1 if across_midline else 0
    return min(3, base + modifier)


def score_wrist(wrist_angle: Optional[float], *, deviated: bool = False) -> int:
    """Calculate RULA Wrist Score (1-4).

    Deviation from straight forearm line:
      - 0° to 4° (neutral): 1
      - > 4° to 15°: 2
      - > 15°: 3
    """
    if wrist_angle is None:
        return 1

    deg = abs(wrist_angle)
    if deg <= 4.0:
        base = 1
    elif deg <= 15.0:
        base = 2
    else:
        base = 3

    modifier = 1 if deviated else 0
    return min(4, base + modifier)


def score_neck(neck_angle: Optional[float], *, twisted: bool = False, side_bending: bool = False) -> int:
    """Calculate RULA Neck Score (1-6).

    Neck flexion from torso axis:
      - 0° to 10° flexion: 1
      - > 10° to 20° flexion: 2
      - > 20° flexion: 3
      - In extension: 4
    """
    if neck_angle is None:
        return 1

    deg = neck_angle
    if deg < 0.0:
        # Neck extension (tilted backward)
        base = 4
    elif deg <= 10.0:
        base = 1
    elif deg <= 20.0:
        base = 2
    else:
        base = 3

    modifier = (1 if twisted else 0) + (1 if side_bending else 0)
    return min(6, base + modifier)


def score_trunk(trunk_angle: Optional[float], *, twisted: bool = False, side_bending: bool = False) -> int:
    """Calculate RULA Trunk Score (1-6).

    Trunk inclination from vertical:
      - 0° (upright): 1
      - 0° to 20° flexion: 2
      - > 20° to 60° flexion: 3
      - > 60° flexion: 4
      - In extension: 2
    """
    if trunk_angle is None:
        return 1

    deg = trunk_angle
    if deg < 0.0:
        base = 2
    elif deg <= 5.0:
        base = 1
    elif deg <= 20.0:
        base = 2
    elif deg <= 60.0:
        base = 3
    else:
        base = 4

    modifier = (1 if twisted else 0) + (1 if side_bending else 0)
    return min(6, base + modifier)


def score_legs(knee_angle: Optional[float]) -> int:
    """Calculate RULA Legs Score (1-2).

    1: Legs and feet supported and balanced (e.g. seated with feet on floor).
    2: Unbalanced or unsupported.
    """
    # For seated desk workers with feet flat, knee ~90° implies supported sitting (1).
    if knee_angle is not None and (knee_angle < 45.0 or knee_angle > 140.0):
        return 2
    return 1


# ── RULA Calculator Class ─────────────────────────────────────────────────────

class RulaCalculator:
    """Evaluates RULA scores from PostureParameters.

    Parameters:
        static_posture:  If True, adds +1 muscle use score for static seated work.
                         Default True for workstation monitoring.
        load_score:      Load/force score (default 0 for VDU computer workers).
        wrist_twist:     Wrist twist score (1=mid-range, 2=near end; default 1).
    """

    def __init__(
        self,
        static_posture: bool = True,
        load_score: int = 0,
        wrist_twist: int = 1,
    ) -> None:
        self.static_posture = static_posture
        self.load_score = load_score
        self.wrist_twist = min(2, max(1, wrist_twist))

    def calculate(self, posture: PostureParameters) -> RulaBreakdown:
        """Compute full RULA breakdown and grand score."""
        # 1. Group A: Upper limb
        upper_arm = score_upper_arm(posture.shoulder_angle)
        lower_arm = score_lower_arm(posture.elbow_angle)
        wrist = score_wrist(posture.wrist_angle)
        twist = self.wrist_twist

        table_a = TABLE_A[upper_arm - 1][lower_arm - 1][wrist - 1][twist - 1]
        muscle_a = 1 if self.static_posture else 0
        force_a = self.load_score
        score_a_total = min(8, table_a + muscle_a + force_a)

        # 2. Group B: Neck, Trunk, Legs
        neck = score_neck(posture.neck_angle)
        trunk = score_trunk(posture.trunk_angle)
        legs = score_legs(posture.knee_angle)

        table_b = TABLE_B[neck - 1][trunk - 1][legs - 1]
        muscle_b = 1 if self.static_posture else 0
        force_b = self.load_score
        score_b_total = min(7, table_b + muscle_b + force_b)

        # 3. Table C: Grand score
        row = min(score_a_total, 8) - 1
        col = min(score_b_total, 7) - 1
        grand_score = TABLE_C[row][col]

        # 4. Action level mapping
        if grand_score <= 2:
            action_level = 1
        elif grand_score <= 4:
            action_level = 2
        elif grand_score <= 6:
            action_level = 3
        else:
            action_level = 4

        return RulaBreakdown(
            upper_arm_score=upper_arm,
            lower_arm_score=lower_arm,
            wrist_score=wrist,
            wrist_twist_score=twist,
            table_a_score=table_a,
            muscle_a_score=muscle_a,
            force_a_score=force_a,
            score_a_total=score_a_total,
            neck_score=neck,
            trunk_score=trunk,
            legs_score=legs,
            table_b_score=table_b,
            muscle_b_score=muscle_b,
            force_b_score=force_b,
            score_b_total=score_b_total,
            grand_score=grand_score,
            action_level=action_level,
        )
