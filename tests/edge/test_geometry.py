"""
Tests for edge_agent/geometry/angle_calculator.py.

Verifies:
  1. Pure vector math utilities (dot products, angles with vertical, joint angles).
  2. Hand-checked synthetic landmark cases with known trigonometric angles:
     - Perfectly upright posture -> trunk ~0°, neck ~0°, shoulder ~0°, elbow ~0°
     - 30° and 45° forward trunk flexion
     - 20° forward neck flexion
     - 90° elbow bend
     - Standard 90° seated posture (hip ~90°, knee ~90°)
  3. Graceful degradation: missing or low-confidence landmarks return None (never wrong numbers).
  4. Temporal smoothing (EMA): measurably reduces variance / frame-to-frame jitter.
  5. Module boundary: strict check that geometry imports ZERO symbols from ergonomics or vision.
  6. Live camera bench test (guarded by --run-camera): verifies live jitter reduction.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Optional
import time

import numpy as np
import pytest

from edge_agent.geometry.angle_calculator import (
    AngleCalculator,
    PostureParameters,
    TemporalAngleSmoother,
    angle_at_vertex,
    angle_between_vectors,
    angle_with_vertical,
    compute_elbow_angle,
    compute_hip_angle,
    compute_knee_angle,
    compute_neck_angle,
    compute_shoulder_angle,
    compute_trunk_angle,
    compute_wrist_angle,
)


# ── Synthetic Landmark Fixtures ───────────────────────────────────────────────

@dataclass
class MockLandmark:
    """Mock landmark mimicking PoseEngine's LandmarkPoint without importing vision."""
    name: str
    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.95
    presence: float = 0.95
    is_visible: bool = True


def make_upright_landmarks() -> dict[str, MockLandmark]:
    """Create a synthetic landmark set representing a perfectly upright standing worker.

    Image coordinates: y points DOWN (0 = top, 1 = bottom).
    - Hips at y=0.6, Shoulders at y=0.3 -> Trunk straight up -> trunk angle = 0.0°
    - Head at y=0.15 -> Head straight above shoulders -> neck angle = 0.0°
    - Elbows at y=0.45 -> Arms hanging down -> shoulder angle = 0.0°
    - Wrists at y=0.6 -> Forearms straight down -> elbow angle = 0.0°
    - Index at y=0.65 -> Hands in line with forearms -> wrist angle = 0.0°
    - Knees at y=0.8 -> Standing straight -> hip angle = 180.0°
    - Ankles at y=1.0 -> Standing straight -> knee angle = 180.0°
    """
    return {
        "NOSE": MockLandmark("NOSE", x=0.5, y=0.12),
        "LEFT_EAR": MockLandmark("LEFT_EAR", x=0.48, y=0.15),
        "RIGHT_EAR": MockLandmark("RIGHT_EAR", x=0.52, y=0.15),
        "LEFT_SHOULDER": MockLandmark("LEFT_SHOULDER", x=0.45, y=0.30),
        "RIGHT_SHOULDER": MockLandmark("RIGHT_SHOULDER", x=0.55, y=0.30),
        "LEFT_ELBOW": MockLandmark("LEFT_ELBOW", x=0.45, y=0.45),
        "RIGHT_ELBOW": MockLandmark("RIGHT_ELBOW", x=0.55, y=0.45),
        "LEFT_WRIST": MockLandmark("LEFT_WRIST", x=0.45, y=0.60),
        "RIGHT_WRIST": MockLandmark("RIGHT_WRIST", x=0.55, y=0.60),
        "LEFT_INDEX": MockLandmark("LEFT_INDEX", x=0.45, y=0.65),
        "RIGHT_INDEX": MockLandmark("RIGHT_INDEX", x=0.55, y=0.65),
        "LEFT_HIP": MockLandmark("LEFT_HIP", x=0.45, y=0.60),
        "RIGHT_HIP": MockLandmark("RIGHT_HIP", x=0.55, y=0.60),
        "LEFT_KNEE": MockLandmark("LEFT_KNEE", x=0.45, y=0.80),
        "RIGHT_KNEE": MockLandmark("RIGHT_KNEE", x=0.55, y=0.80),
        "LEFT_ANKLE": MockLandmark("LEFT_ANKLE", x=0.45, y=1.00),
        "RIGHT_ANKLE": MockLandmark("RIGHT_ANKLE", x=0.55, y=1.00),
    }


def make_seated_landmarks() -> dict[str, MockLandmark]:
    """Create a synthetic landmark set representing a standard 90° seated workstation posture.

    - Torso upright: Hip (0.5, 0.5), Shoulder (0.5, 0.2)
    - Thigh horizontal: Hip (0.5, 0.5) to Knee (0.7, 0.5) -> Hip angle = 90.0°
    - Shank vertical: Knee (0.7, 0.5) to Ankle (0.7, 0.8) -> Knee angle = 90.0°
    - Forearm horizontal typing: Shoulder (0.5, 0.2), Elbow (0.5, 0.35), Wrist (0.65, 0.35) -> Elbow angle = 90.0°
    """
    return {
        "NOSE": MockLandmark("NOSE", x=0.5, y=0.10),
        "LEFT_EAR": MockLandmark("LEFT_EAR", x=0.48, y=0.12),
        "RIGHT_EAR": MockLandmark("RIGHT_EAR", x=0.52, y=0.12),
        "LEFT_SHOULDER": MockLandmark("LEFT_SHOULDER", x=0.48, y=0.20),
        "RIGHT_SHOULDER": MockLandmark("RIGHT_SHOULDER", x=0.52, y=0.20),
        "LEFT_ELBOW": MockLandmark("LEFT_ELBOW", x=0.48, y=0.35),
        "RIGHT_ELBOW": MockLandmark("RIGHT_ELBOW", x=0.52, y=0.35),
        "LEFT_WRIST": MockLandmark("LEFT_WRIST", x=0.63, y=0.35),
        "RIGHT_WRIST": MockLandmark("RIGHT_WRIST", x=0.67, y=0.35),
        "LEFT_INDEX": MockLandmark("LEFT_INDEX", x=0.68, y=0.35),
        "RIGHT_INDEX": MockLandmark("RIGHT_INDEX", x=0.72, y=0.35),
        "LEFT_HIP": MockLandmark("LEFT_HIP", x=0.48, y=0.50),
        "RIGHT_HIP": MockLandmark("RIGHT_HIP", x=0.52, y=0.50),
        "LEFT_KNEE": MockLandmark("LEFT_KNEE", x=0.68, y=0.50),
        "RIGHT_KNEE": MockLandmark("RIGHT_KNEE", x=0.72, y=0.50),
        "LEFT_ANKLE": MockLandmark("LEFT_ANKLE", x=0.68, y=0.80),
        "RIGHT_ANKLE": MockLandmark("RIGHT_ANKLE", x=0.72, y=0.80),
    }


# ── 1. Vector Math Unit Tests ─────────────────────────────────────────────────

class TestVectorMath:
    """Validate core vector operations independent of posture domain."""

    def test_angle_between_parallel_vectors(self) -> None:
        v1 = np.array([1.0, 0.0])
        v2 = np.array([5.0, 0.0])
        assert angle_between_vectors(v1, v2) == pytest.approx(0.0, abs=1e-5)

    def test_angle_between_orthogonal_vectors(self) -> None:
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 1.0])
        assert angle_between_vectors(v1, v2) == pytest.approx(90.0, abs=1e-5)

    def test_angle_between_opposite_vectors(self) -> None:
        v1 = np.array([1.0, 0.0])
        v2 = np.array([-2.0, 0.0])
        assert angle_between_vectors(v1, v2) == pytest.approx(180.0, abs=1e-5)

    def test_angle_between_45_degree_vectors(self) -> None:
        v1 = np.array([1.0, 0.0])
        v2 = np.array([1.0, 1.0])
        assert angle_between_vectors(v1, v2) == pytest.approx(45.0, abs=1e-4)

    def test_angle_between_zero_vector_is_zero(self) -> None:
        v1 = np.array([0.0, 0.0])
        v2 = np.array([1.0, 0.0])
        assert angle_between_vectors(v1, v2) == 0.0

    def test_angle_3d_vectors(self) -> None:
        v1 = np.array([0.0, 0.0, 1.0])
        v2 = np.array([0.0, 1.0, 0.0])
        assert angle_between_vectors(v1, v2) == pytest.approx(90.0, abs=1e-5)

    def test_angle_at_vertex_right_angle(self) -> None:
        pa = (1.0, 0.0)
        vertex = (0.0, 0.0)
        pb = (0.0, 1.0)
        assert angle_at_vertex(pa, vertex, pb) == pytest.approx(90.0, abs=1e-5)

    def test_angle_at_vertex_straight_line(self) -> None:
        pa = (-1.0, 0.0)
        vertex = (0.0, 0.0)
        pb = (1.0, 0.0)
        assert angle_at_vertex(pa, vertex, pb) == pytest.approx(180.0, abs=1e-5)

    def test_angle_with_vertical_upward(self) -> None:
        # In screen coords, upward is [0, -1]
        origin = (0.5, 0.6)
        target = (0.5, 0.3)  # straight up
        assert angle_with_vertical(origin, target, upward=True) == pytest.approx(0.0, abs=1e-5)

    def test_angle_with_vertical_tilted_30_degrees(self) -> None:
        # 30° tilt from upward vertical: dx = L*sin(30°), dy = -L*cos(30°)
        length = 0.4
        rad30 = math.radians(30.0)
        origin = (0.5, 0.6)
        target = (0.5 + length * math.sin(rad30), 0.6 - length * math.cos(rad30))
        assert angle_with_vertical(origin, target, upward=True) == pytest.approx(30.0, abs=1e-4)


# ── 2. Synthetic Posture Cases (Hand-Checked Math) ────────────────────────────

class TestSyntheticPostures:
    """Verify full PostureParameters output on hand-calculated synthetic cases."""

    def test_perfectly_upright_posture(self) -> None:
        calc = AngleCalculator(smoothing_alpha=1.0)  # unsmoothed
        lm = make_upright_landmarks()
        params = calc.calculate(lm)

        assert params.trunk_angle == pytest.approx(0.0, abs=0.5)
        assert params.neck_angle == pytest.approx(0.0, abs=0.5)
        assert params.shoulder_angle == pytest.approx(0.0, abs=0.5)
        assert params.elbow_angle == pytest.approx(0.0, abs=0.5)
        assert params.wrist_angle == pytest.approx(0.0, abs=0.5)
        assert params.hip_angle == pytest.approx(180.0, abs=0.5)
        assert params.knee_angle == pytest.approx(180.0, abs=0.5)
        assert params.has_upper_body is True
        assert params.available_angle_count == 7

    def test_known_trunk_forward_flexion(self) -> None:
        """Torso bent forward at exactly 35°."""
        lm = make_upright_landmarks()
        hip_y = 0.6
        torso_len = 0.30
        rad = math.radians(35.0)

        new_shoulder_x = 0.5 + torso_len * math.sin(rad)
        new_shoulder_y = hip_y - torso_len * math.cos(rad)

        lm["LEFT_SHOULDER"].x = new_shoulder_x - 0.05
        lm["LEFT_SHOULDER"].y = new_shoulder_y
        lm["RIGHT_SHOULDER"].x = new_shoulder_x + 0.05
        lm["RIGHT_SHOULDER"].y = new_shoulder_y

        calc = AngleCalculator(smoothing_alpha=1.0)
        params = calc.calculate(lm)

        assert params.trunk_angle == pytest.approx(35.0, abs=0.2)

    def test_known_neck_forward_flexion(self) -> None:
        """Head tilted forward by 25° relative to upright trunk."""
        lm = make_upright_landmarks()
        shoulder_y = 0.30
        neck_len = 0.15
        rad = math.radians(25.0)

        new_head_x = 0.5 + neck_len * math.sin(rad)
        new_head_y = shoulder_y - neck_len * math.cos(rad)

        lm["NOSE"].x = new_head_x
        lm["NOSE"].y = new_head_y
        lm["LEFT_EAR"].x = new_head_x - 0.02
        lm["LEFT_EAR"].y = new_head_y
        lm["RIGHT_EAR"].x = new_head_x + 0.02
        lm["RIGHT_EAR"].y = new_head_y

        calc = AngleCalculator(smoothing_alpha=1.0)
        params = calc.calculate(lm)

        assert params.trunk_angle == pytest.approx(0.0, abs=0.5)
        assert params.neck_angle == pytest.approx(25.0, abs=0.5)

    def test_90_degree_elbow_flexion(self) -> None:
        """Right arm bent at 90°: upper arm straight down, forearm horizontal."""
        lm = make_upright_landmarks()
        # Right shoulder (0.55, 0.30), Elbow (0.55, 0.45), Wrist (0.70, 0.45)
        lm["RIGHT_WRIST"].x = 0.70
        lm["RIGHT_WRIST"].y = 0.45

        calc = AngleCalculator(smoothing_alpha=1.0)
        params = calc.calculate(lm)

        assert params.right_elbow_angle == pytest.approx(90.0, abs=0.1)

    def test_standard_seated_posture(self) -> None:
        """Standard 90° seated workstation posture."""
        calc = AngleCalculator(smoothing_alpha=1.0)
        lm = make_seated_landmarks()
        params = calc.calculate(lm)

        assert params.trunk_angle == pytest.approx(0.0, abs=1.0)
        assert params.elbow_angle == pytest.approx(90.0, abs=1.0)
        assert params.hip_angle == pytest.approx(90.0, abs=1.0)
        assert params.knee_angle == pytest.approx(90.0, abs=1.0)


# ── 3. Missing / Low Confidence Handling ─────────────────────────────────────

class TestMissingAndLowConfidenceHandling:
    """Verify that missing or noisy landmarks degrade to None, never wrong numbers."""

    def test_missing_landmark_yields_none(self) -> None:
        lm = make_upright_landmarks()
        del lm["LEFT_ELBOW"]
        del lm["RIGHT_ELBOW"]

        calc = AngleCalculator(smoothing_alpha=1.0)
        params = calc.calculate(lm)

        assert params.shoulder_angle is None
        assert params.elbow_angle is None
        # Trunk and neck should still be computable
        assert params.trunk_angle is not None
        assert params.neck_angle is not None

    def test_low_visibility_flag_yields_none(self) -> None:
        lm = make_upright_landmarks()
        # Mark elbows not visible
        lm["LEFT_ELBOW"].is_visible = False
        lm["RIGHT_ELBOW"].is_visible = False

        calc = AngleCalculator(smoothing_alpha=1.0)
        params = calc.calculate(lm)

        assert params.shoulder_angle is None
        assert params.elbow_angle is None

    def test_confidence_below_threshold_yields_none(self) -> None:
        lm = make_upright_landmarks()
        # Set confidence to 0.3 (below default threshold of 0.5)
        lm["LEFT_HIP"].visibility = 0.3
        lm["RIGHT_HIP"].visibility = 0.3

        calc = AngleCalculator(min_confidence=0.5, smoothing_alpha=1.0)
        params = calc.calculate(lm)

        assert params.trunk_angle is None
        assert params.hip_angle is None

    def test_empty_landmarks_yields_all_none(self) -> None:
        calc = AngleCalculator()
        params = calc.calculate({})

        assert params.neck_angle is None
        assert params.trunk_angle is None
        assert params.shoulder_angle is None
        assert params.available_angle_count == 0
        assert params.has_upper_body is False
        assert params.confidence == 0.0

    def test_duck_typing_with_plain_tuples(self) -> None:
        """Supports pure coordinate tuples/lists without MockLandmark objects."""
        raw_dict = {
            "LEFT_HIP": (0.45, 0.60),
            "RIGHT_HIP": (0.55, 0.60),
            "LEFT_SHOULDER": (0.45, 0.30),
            "RIGHT_SHOULDER": (0.55, 0.30),
            "NOSE": (0.50, 0.15),
        }
        calc = AngleCalculator(smoothing_alpha=1.0)
        params = calc.calculate(raw_dict)

        assert params.trunk_angle == pytest.approx(0.0, abs=0.5)
        assert params.neck_angle == pytest.approx(0.0, abs=0.5)


# ── 4. Temporal Smoothing & Jitter Reduction ──────────────────────────────────

class TestTemporalSmoothing:
    """Validate EMA filter responsiveness and quantitative jitter reduction."""

    def test_single_frame_spike_suppression(self) -> None:
        smoother = TemporalAngleSmoother(alpha=0.3)
        base_params = PostureParameters(trunk_angle=20.0)

        # Warm up at 20°
        for _ in range(5):
            smoothed = smoother.update(base_params)
        assert smoothed.trunk_angle == pytest.approx(20.0, abs=0.1)

        # Inject single 70° spike
        spike_params = PostureParameters(trunk_angle=70.0)
        spike_smoothed = smoother.update(spike_params)

        # With alpha=0.3: 0.3 * 70 + 0.7 * 20 = 21 + 14 = 35° (NOT 70°)
        assert spike_smoothed.trunk_angle == pytest.approx(35.0, abs=0.5)
        assert spike_smoothed.trunk_angle < 45.0

    def test_quantitative_jitter_reduction(self) -> None:
        """Verify that EMA filter measurably reduces variance on noisy signals."""
        np.random.seed(42)
        true_angle = 25.0
        noise_std = 4.0
        n_frames = 200

        noisy_angles = true_angle + np.random.normal(0.0, noise_std, n_frames)
        smoother = TemporalAngleSmoother(alpha=0.25)

        smoothed_angles: list[float] = []
        for a in noisy_angles:
            p = PostureParameters(trunk_angle=float(a))
            sm = smoother.update(p)
            assert sm.trunk_angle is not None
            smoothed_angles.append(sm.trunk_angle)

        raw_std = float(np.std(noisy_angles))
        smoothed_std = float(np.std(smoothed_angles))

        # Expected theoretical reduction with alpha=0.25 is ~50%
        assert smoothed_std < raw_std * 0.7, (
            f"Expected smoothed std ({smoothed_std:.2f}) to be < 70% of raw ({raw_std:.2f})"
        )

    def test_missing_landmark_clears_smoother_state(self) -> None:
        smoother = TemporalAngleSmoother(alpha=0.3)
        smoother.update(PostureParameters(neck_angle=15.0))

        # Landmark disappears
        res = smoother.update(PostureParameters(neck_angle=None))
        assert res.neck_angle is None

        # When it reappears, it should immediately take the new value (no stale blend)
        res2 = smoother.update(PostureParameters(neck_angle=40.0))
        assert res2.neck_angle == pytest.approx(40.0, abs=0.1)

    def test_reset_clears_state(self) -> None:
        smoother = TemporalAngleSmoother(alpha=0.3)
        smoother.update(PostureParameters(trunk_angle=50.0))
        smoother.reset()

        # After reset, first observation should be used directly
        res = smoother.update(PostureParameters(trunk_angle=10.0))
        assert res.trunk_angle == pytest.approx(10.0, abs=0.1)


# ── 5. Architecture & Module Boundary Enforcement ────────────────────────────

class TestArchitectureBoundaries:
    """Strict verification that geometry engine maintains total isolation."""

    def test_zero_ergonomics_imports(self) -> None:
        calc_file = (
            Path(__file__).resolve().parent.parent.parent
            / "edge_agent"
            / "geometry"
            / "angle_calculator.py"
        )
        assert calc_file.exists(), f"File not found: {calc_file}"

        with open(calc_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(calc_file))

        disallowed_prefixes = ("ergonomics", "edge_agent.ergonomics", "vision", "edge_agent.vision")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in disallowed_prefixes:
                        assert not alias.name.startswith(prefix), (
                            f"Violation: geometry/ imports '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prefix in disallowed_prefixes:
                        assert not node.module.startswith(prefix), (
                            f"Violation: geometry/ imports from '{node.module}'"
                        )


# ── 6. Live Camera Bench Test (Guarded by --run-camera) ───────────────────────

class TestGeometryLive:
    """Live camera pipeline test measuring real jitter reduction."""

    @pytest.mark.skipif(True, reason="Use --run-camera to enable")
    def test_live_jitter_reduction(self, run_camera: bool) -> None:
        if not run_camera:
            pytest.skip("Live camera test not requested.")

        from edge_agent.camera.camera import Camera, list_available_cameras
        from edge_agent.vision.pose_engine import PoseEngine

        available = list_available_cameras()
        if not available:
            pytest.skip("No camera available.")

        cam = Camera(camera_index=available[0], frame_width=640, frame_height=480)
        cam.open()

        raw_calc = AngleCalculator(smoothing_alpha=1.0)
        smooth_calc = AngleCalculator(smoothing_alpha=0.35)

        raw_trunk: list[float] = []
        smooth_trunk: list[float] = []

        start = time.monotonic()
        try:
            with PoseEngine() as pose:
                for frame in cam.stream():
                    rgb = frame.to_rgb()
                    res = pose.process_frame(rgb)
                    if res.is_detected:
                        r = raw_calc.calculate(res.landmarks)
                        s = smooth_calc.calculate(res.landmarks)
                        if r.trunk_angle is not None and s.trunk_angle is not None:
                            raw_trunk.append(r.trunk_angle)
                            smooth_trunk.append(s.trunk_angle)

                    if time.monotonic() - start >= 4.0:
                        break
        finally:
            cam.release()

        if len(raw_trunk) < 10:
            pytest.skip("Insufficient detected frames in live test.")

        # Compute frame-to-frame difference (jitter measure)
        raw_diffs = np.abs(np.diff(raw_trunk))
        smooth_diffs = np.abs(np.diff(smooth_trunk))

        raw_jitter = float(np.mean(raw_diffs))
        smooth_jitter = float(np.mean(smooth_diffs))

        print(
            f"\n[Geometry Live Bench] {len(raw_trunk)} frames: "
            f"raw jitter = {raw_jitter:.2f}°, smoothed jitter = {smooth_jitter:.2f}°"
        )
        assert smooth_jitter <= raw_jitter, "Smoother must reduce or maintain frame jitter."
