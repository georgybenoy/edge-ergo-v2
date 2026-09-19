"""
Tests for edge_agent/ergonomics/rula.py, reba.py, and scoring.py.

Validates the Ergonomic Assessment Engine against standard textbook worked examples
from the foundational literature:
  1. McAtamney & Corlett (1993) - RULA
  2. Hignett & McAtamney (2000) - REBA

Test Coverage:
  - Table data structure isolation (PRD §23, §24)
  - Angle-to-score discrete mappings
  - Worked textbook postures:
      Postures A: Neutral Seated Workstation (Score 1-2, LOW risk)
      Postures B: Moderate Neck Flexion / VDU Slouch (Score 3-4, MODERATE risk)
      Postures C: High-Risk Overhead / Awkward Arm Elevation (Score 5-6, HIGH risk)
      Postures D: Severe Forward Bending & Full Reach (Score 7, VERY HIGH risk)
  - Action level mappings and official RiskLevel classification (PRD §25)
  - Dominant posture identification (e.g. 'NECK_FLEXION', 'SHOULDER_ELEVATION')
  - Missing angles and graceful degradation
"""

from __future__ import annotations

import pytest

from edge_agent.ergonomics.reba import (
    TABLE_A as REBA_TABLE_A,
    TABLE_B as REBA_TABLE_B,
    TABLE_C as REBA_TABLE_C,
    RebaActionLevel,
    RebaCalculator,
    score_reba_legs,
    score_reba_lower_arm,
    score_reba_neck,
    score_reba_trunk,
    score_reba_upper_arm,
    score_reba_wrist,
)
from edge_agent.ergonomics.rula import (
    TABLE_A as RULA_TABLE_A,
    TABLE_B as RULA_TABLE_B,
    TABLE_C as RULA_TABLE_C,
    RulaActionLevel,
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
from edge_agent.geometry.angle_calculator import PostureParameters


# ── 1. Table Data Integrity Tests ─────────────────────────────────────────────

class TestScoringTableIntegrity:
    """Verify that lookup tables match official dimensions and bounds."""

    def test_rula_table_a_dimensions(self) -> None:
        # Upper Arm (6) x Lower Arm (3) x Wrist (4) x Wrist Twist (2)
        assert len(RULA_TABLE_A) == 6
        for lower in RULA_TABLE_A:
            assert len(lower) == 3
            for wrist in lower:
                assert len(wrist) == 4
                for twist in wrist:
                    assert len(twist) == 2
                    for score in twist:
                        assert 1 <= score <= 9

    def test_rula_table_b_dimensions(self) -> None:
        # Neck (6) x Trunk (6) x Legs (2)
        assert len(RULA_TABLE_B) == 6
        for trunk in RULA_TABLE_B:
            assert len(trunk) == 6
            for legs in trunk:
                assert len(legs) == 2
                for score in legs:
                    assert 1 <= score <= 9

    def test_rula_table_c_dimensions(self) -> None:
        # Score A (8) x Score B (7)
        assert len(RULA_TABLE_C) == 8
        for row in RULA_TABLE_C:
            assert len(row) == 7
            for score in row:
                assert 1 <= score <= 7

    def test_reba_table_dimensions(self) -> None:
        # REBA Table A: Trunk (5) x Neck (3) x Legs (4)
        assert len(REBA_TABLE_A) == 5
        assert len(REBA_TABLE_A[0]) == 3
        assert len(REBA_TABLE_A[0][0]) == 4

        # REBA Table B: Upper Arm (6) x Lower Arm (2) x Wrist (3)
        assert len(REBA_TABLE_B) == 6
        assert len(REBA_TABLE_B[0]) == 2
        assert len(REBA_TABLE_B[0][0]) == 3

        # REBA Table C: Score A (12) x Score B (12)
        assert len(REBA_TABLE_C) == 12
        assert len(REBA_TABLE_C[0]) == 12


# ── 2. Angle to Score Mapping Tests ───────────────────────────────────────────

class TestAngleToScoreMapping:
    """Validate boundary conditions for individual joint score functions."""

    def test_rula_upper_arm_bins(self) -> None:
        assert score_upper_arm(0.0) == 1
        assert score_upper_arm(20.0) == 1
        assert score_upper_arm(21.0) == 2
        assert score_upper_arm(45.0) == 2
        assert score_upper_arm(46.0) == 3
        assert score_upper_arm(90.0) == 3
        assert score_upper_arm(91.0) == 4
        # Modifiers
        assert score_upper_arm(10.0, raised=True) == 2
        assert score_upper_arm(10.0, raised=True, abducted=True) == 3

    def test_rula_lower_arm_bins(self) -> None:
        assert score_lower_arm(59.0) == 2
        assert score_lower_arm(60.0) == 1
        assert score_lower_arm(90.0) == 1
        assert score_lower_arm(100.0) == 1
        assert score_lower_arm(101.0) == 2

    def test_rula_wrist_bins(self) -> None:
        assert score_wrist(2.0) == 1
        assert score_wrist(10.0) == 2
        assert score_wrist(20.0) == 3

    def test_rula_neck_bins(self) -> None:
        assert score_neck(5.0) == 1
        assert score_neck(15.0) == 2
        assert score_neck(25.0) == 3
        assert score_neck(-5.0) == 4  # Extension

    def test_rula_trunk_bins(self) -> None:
        assert score_trunk(0.0) == 1
        assert score_trunk(15.0) == 2
        assert score_trunk(35.0) == 3
        assert score_trunk(65.0) == 4


# ── 3. Textbook Worked Examples (Validated Assessment) ────────────────────────

class TestWorkedExamplesLiterature:
    """Validate complete RULA and REBA calculation against known literature cases."""

    def test_case_1_neutral_workstation_posture(self) -> None:
        """Textbook Case 1: Ideal ergonomic seated posture.

        - Trunk vertical (0°)
        - Neck vertical (0°)
        - Shoulder relaxed (10°)
        - Elbow at 90° typing angle
        - Wrist neutral (0°)
        - Knee at 90° supported sitting

        Expected:
          - RULA Score: 1-2 (Action Level 1 -> LOW risk)
          - REBA Score: 1-2 (Action Level 0-1 -> LOW risk)
          - Dominant posture: NEUTRAL
        """
        posture = PostureParameters(
            trunk_angle=0.0,
            neck_angle=0.0,
            shoulder_angle=10.0,
            elbow_angle=90.0,
            wrist_angle=0.0,
            knee_angle=90.0,
            hip_angle=90.0,
        )

        res = assess(posture)

        assert res.rula_score in (1, 2)
        assert res.reba_score in (1, 2)
        assert res.risk_level == RiskLevel.LOW
        assert res.dominant_posture == "NEUTRAL"

    def test_case_2_vdu_laptop_slouch(self) -> None:
        """Textbook Case 2: Worker slouching forward looking down at a laptop.

        - Neck bent forward: 30° (> 20° flexion -> Neck Score 3)
        - Trunk bent forward: 25° (20°-60° flexion -> Trunk Score 3)
        - Shoulder elevated: 30° (Upper Arm Score 2)
        - Elbow: 90° (Lower Arm Score 1)
        - Wrist: neutral (0°)

        Expected:
          - RULA: Action Level 2 (Score 3-4 -> MODERATE risk)
          - Dominant posture: NECK_FLEXION or TRUNK_FLEXION
        """
        posture = PostureParameters(
            trunk_angle=25.0,
            neck_angle=30.0,
            shoulder_angle=30.0,
            elbow_angle=90.0,
            wrist_angle=0.0,
            knee_angle=90.0,
        )

        res = assess(posture)

        assert res.rula_score in (3, 4)
        assert res.risk_level == RiskLevel.MODERATE
        assert res.dominant_posture in ("NECK_FLEXION", "TRUNK_FLEXION")

    def test_case_3_overhead_reaching(self) -> None:
        """Textbook Case 3: Awkward overhead reaching task.

        - Upper arm elevated: 105° (> 90° elevation -> Score 4)
        - Lower arm extended: 40° (< 60° -> Score 2)
        - Wrist deviated: 20° (> 15° -> Score 3)
        - Trunk upright: 0° (Score 1)
        - Neck: 15° (Score 2)

        Expected:
          - RULA Score: 5 or 6 (Action Level 3 -> HIGH risk)
          - Dominant posture: SHOULDER_ELEVATION
        """
        posture = PostureParameters(
            trunk_angle=0.0,
            neck_angle=15.0,
            shoulder_angle=105.0,
            elbow_angle=40.0,
            wrist_angle=20.0,
            knee_angle=90.0,
        )

        res = assess(posture)

        assert res.rula_score >= 5
        assert res.risk_level in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)
        assert res.dominant_posture == "SHOULDER_ELEVATION"

    def test_case_4_severe_stoop_reach(self) -> None:
        """Textbook Case 4: Severe stoop bending and reaching (Very High Risk).

        - Trunk bent forward: 65° (> 60° flexion -> Score 4)
        - Neck bent forward: 25° (> 20° flexion -> Score 3)
        - Upper arm reaching: 95° (> 90° -> Score 4)
        - Lower arm: 110° (> 100° -> Score 2)
        - Wrist: 25° (> 15° -> Score 3)

        Expected:
          - RULA Grand Score: 7 (Action Level 4 -> VERY_HIGH risk)
          - Unified risk: VERY_HIGH
        """
        posture = PostureParameters(
            trunk_angle=65.0,
            neck_angle=25.0,
            shoulder_angle=95.0,
            elbow_angle=110.0,
            wrist_angle=25.0,
            knee_angle=90.0,
        )

        res = assess(posture)

        assert res.rula_score == 7
        assert res.rula_action_level == 4
        assert res.risk_level == RiskLevel.VERY_HIGH


# ── 4. Action Level & Risk Classification Mapping ────────────────────────────

class TestRiskLevelClassification:
    """Verify mapping from RULA/REBA action levels to RiskLevel."""

    def test_map_risk_level_matrix(self) -> None:
        assert map_risk_level(1, 0) == RiskLevel.LOW
        assert map_risk_level(1, 1) == RiskLevel.LOW
        assert map_risk_level(2, 1) == RiskLevel.MODERATE
        assert map_risk_level(1, 2) == RiskLevel.MODERATE
        assert map_risk_level(3, 1) == RiskLevel.HIGH
        assert map_risk_level(2, 3) == RiskLevel.HIGH
        assert map_risk_level(4, 1) == RiskLevel.VERY_HIGH
        assert map_risk_level(1, 4) == RiskLevel.VERY_HIGH


# ── 5. Graceful Degradation on Missing Inputs ─────────────────────────────────

class TestGracefulDegradation:
    """Verify handling when some or all posture angles are missing."""

    def test_empty_posture_parameters(self) -> None:
        empty_posture = PostureParameters()
        res = assess(empty_posture)

        assert res.is_valid is False
        assert res.dominant_posture == "NO_PERSON_DETECTED"
        assert res.risk_level == RiskLevel.LOW

    def test_partial_upper_body_still_assesses(self) -> None:
        """Legs/wrists missing (common at desks) should still assess upper body."""
        partial = PostureParameters(
            neck_angle=25.0,
            trunk_angle=15.0,
            shoulder_angle=20.0,
            elbow_angle=80.0,
            wrist_angle=None,  # missing
            knee_angle=None,   # missing
        )
        res = assess(partial)

        assert res.is_valid is True
        assert 1 <= res.rula_score <= 7
        assert 1 <= res.reba_score <= 15
        assert res.dominant_posture == "NECK_FLEXION"

    def test_serialization(self) -> None:
        posture = PostureParameters(trunk_angle=10.0, neck_angle=5.0)
        res = assess(posture)
        d = res.to_dict()

        assert "rula_score" in d
        assert "reba_score" in d
        assert "risk_level" in d
        assert "dominant_posture" in d
        assert isinstance(d["rula_breakdown"], dict)
        assert isinstance(d["reba_breakdown"], dict)
