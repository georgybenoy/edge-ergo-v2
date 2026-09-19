"""
Tests for vision/pose_engine.py.

Split into:
  1. Unit tests with mocked MediaPipe (always runnable, no model/camera needed).
  2. Integration test with real model (requires the .task file).
  3. Live camera + pose test (guarded by --run-camera).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from edge_agent.vision.pose_engine import (
    ALL_ERGONOMIC_INDICES,
    DEFAULT_POSE_MODEL_PATH,
    ERGONOMIC_LANDMARKS,
    LandmarkPoint,
    PoseEngine,
    PoseResult,
    draw_skeleton,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_rgb_frame(w: int = 640, h: int = 480) -> np.ndarray:
    """Create a dummy RGB frame."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_mock_landmark(
    x: float = 0.5,
    y: float = 0.5,
    z: float = 0.0,
    visibility: float = 0.9,
    presence: float = 0.9,
) -> MagicMock:
    """Create a mock NormalizedLandmark / Landmark."""
    lm = MagicMock()
    lm.x = x
    lm.y = y
    lm.z = z
    lm.visibility = visibility
    lm.presence = presence
    return lm


def _make_mock_result(
    num_landmarks: int = 33,
    visibility: float = 0.9,
    presence: float = 0.9,
    empty: bool = False,
) -> MagicMock:
    """Create a mock PoseLandmarkerResult."""
    result = MagicMock()

    if empty:
        result.pose_landmarks = []
        result.pose_world_landmarks = []
        return result

    norm_landmarks = [
        _make_mock_landmark(
            x=0.3 + i * 0.01,
            y=0.2 + i * 0.01,
            z=0.0,
            visibility=visibility,
            presence=presence,
        )
        for i in range(num_landmarks)
    ]
    world_landmarks = [
        _make_mock_landmark(
            x=0.1 * i,
            y=-0.1 * i,
            z=0.0,
            visibility=visibility,
            presence=presence,
        )
        for i in range(num_landmarks)
    ]

    result.pose_landmarks = [norm_landmarks]
    result.pose_world_landmarks = [world_landmarks]
    return result


# ── LandmarkPoint unit tests ─────────────────────────────────────────────────

class TestLandmarkPoint:

    def test_creation(self) -> None:
        pt = LandmarkPoint(
            name="LEFT_SHOULDER", index=11,
            x=0.5, y=0.4, z=0.0,
            visibility=0.95, presence=0.98,
            is_visible=True,
        )
        assert pt.name == "LEFT_SHOULDER"
        assert pt.is_visible is True
        assert pt.visibility == pytest.approx(0.95)

    def test_low_confidence_is_not_visible(self) -> None:
        pt = LandmarkPoint(
            name="LEFT_ANKLE", index=27,
            x=0.5, y=0.9, z=0.0,
            visibility=0.2, presence=0.3,
            is_visible=False,
        )
        assert pt.is_visible is False


# ── PoseResult unit tests ────────────────────────────────────────────────────

class TestPoseResult:

    def test_empty_result(self) -> None:
        r = PoseResult()
        assert r.is_detected is False
        assert r.visible_percentage == 0.0
        assert r.ergonomic_visible_percentage == 0.0

    def test_get_landmark(self) -> None:
        from mediapipe.tasks.python.vision import PoseLandmark

        pt = LandmarkPoint(
            name="NOSE", index=0, x=0.5, y=0.3, z=0.0,
            visibility=0.9, presence=0.9, is_visible=True,
        )
        r = PoseResult(
            is_detected=True,
            landmarks={"NOSE": pt},
            visible_count=1,
            total_count=1,
        )
        assert r.get(PoseLandmark.NOSE) is pt
        assert r.get(PoseLandmark.LEFT_EAR) is None

    def test_get_visible_filters(self) -> None:
        from mediapipe.tasks.python.vision import PoseLandmark

        pt_vis = LandmarkPoint(
            name="NOSE", index=0, x=0.5, y=0.3, z=0.0,
            visibility=0.9, presence=0.9, is_visible=True,
        )
        pt_invis = LandmarkPoint(
            name="LEFT_ANKLE", index=27, x=0.5, y=0.9, z=0.0,
            visibility=0.2, presence=0.3, is_visible=False,
        )
        r = PoseResult(
            is_detected=True,
            landmarks={"NOSE": pt_vis, "LEFT_ANKLE": pt_invis},
        )
        assert r.get_visible(PoseLandmark.NOSE) is pt_vis
        assert r.get_visible(PoseLandmark.LEFT_ANKLE) is None

    def test_visible_percentage(self) -> None:
        r = PoseResult(is_detected=True, visible_count=20, total_count=33)
        assert r.visible_percentage == pytest.approx(60.606, abs=0.01)


# ── PoseEngine unit tests (mocked) ───────────────────────────────────────────

class TestPoseEngineMocked:

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    @patch("edge_agent.vision.pose_engine.DEFAULT_POSE_MODEL_PATH")
    def test_initialise_and_close(self, mock_path: MagicMock, mock_pl_cls: MagicMock) -> None:
        mock_path.exists.return_value = True
        mock_path.__str__ = lambda _: "fake_model.task"
        mock_path.name = "fake_model.task"

        mock_landmarker = MagicMock()
        mock_pl_cls.create_from_options.return_value = mock_landmarker

        engine = PoseEngine(model_path=mock_path)
        engine.initialise()
        assert engine.is_initialised

        engine.close()
        assert not engine.is_initialised
        mock_landmarker.close.assert_called_once()

    def test_process_frame_before_init_raises(self) -> None:
        engine = PoseEngine()
        with pytest.raises(RuntimeError, match="not initialised"):
            engine.process_frame(_make_rgb_frame())

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    @patch("edge_agent.vision.pose_engine.DEFAULT_POSE_MODEL_PATH")
    def test_process_frame_no_person(self, mock_path: MagicMock, mock_pl_cls: MagicMock) -> None:
        mock_path.exists.return_value = True
        mock_path.name = "fake.task"

        mock_landmarker = MagicMock()
        mock_landmarker.detect.return_value = _make_mock_result(empty=True)
        mock_pl_cls.create_from_options.return_value = mock_landmarker

        engine = PoseEngine(model_path=mock_path)
        engine.initialise()
        result = engine.process_frame(_make_rgb_frame())

        assert result.is_detected is False
        assert result.visible_count == 0
        engine.close()

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    @patch("edge_agent.vision.pose_engine.DEFAULT_POSE_MODEL_PATH")
    def test_process_frame_full_detection(self, mock_path: MagicMock, mock_pl_cls: MagicMock) -> None:
        mock_path.exists.return_value = True
        mock_path.name = "fake.task"

        mock_landmarker = MagicMock()
        mock_landmarker.detect.return_value = _make_mock_result(visibility=0.95)
        mock_pl_cls.create_from_options.return_value = mock_landmarker

        engine = PoseEngine(model_path=mock_path)
        engine.initialise()
        result = engine.process_frame(_make_rgb_frame())

        assert result.is_detected is True
        assert result.visible_count == 33
        assert result.is_partial is False
        assert len(result.ergonomic_landmarks) > 0
        assert result.ergonomic_visible_percentage == pytest.approx(100.0)
        engine.close()

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    @patch("edge_agent.vision.pose_engine.DEFAULT_POSE_MODEL_PATH")
    def test_process_frame_low_confidence(self, mock_path: MagicMock, mock_pl_cls: MagicMock) -> None:
        """Low-confidence landmarks should have is_visible=False."""
        mock_path.exists.return_value = True
        mock_path.name = "fake.task"

        mock_landmarker = MagicMock()
        mock_landmarker.detect.return_value = _make_mock_result(visibility=0.2)
        mock_pl_cls.create_from_options.return_value = mock_landmarker

        engine = PoseEngine(model_path=mock_path, visibility_threshold=0.5)
        engine.initialise()
        result = engine.process_frame(_make_rgb_frame())

        assert result.is_detected is True
        assert result.visible_count == 0  # all below threshold
        assert result.is_partial is True
        # Key: low confidence ≠ bad posture
        for pt in result.landmarks.values():
            assert pt.is_visible is False
        engine.close()

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    @patch("edge_agent.vision.pose_engine.DEFAULT_POSE_MODEL_PATH")
    def test_process_invalid_frame(self, mock_path: MagicMock, mock_pl_cls: MagicMock) -> None:
        mock_path.exists.return_value = True
        mock_path.name = "fake.task"

        mock_landmarker = MagicMock()
        mock_pl_cls.create_from_options.return_value = mock_landmarker

        engine = PoseEngine(model_path=mock_path)
        engine.initialise()

        result = engine.process_frame(np.array([]))  # empty/invalid
        assert result.is_detected is False
        engine.close()

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    @patch("edge_agent.vision.pose_engine.DEFAULT_POSE_MODEL_PATH")
    def test_context_manager(self, mock_path: MagicMock, mock_pl_cls: MagicMock) -> None:
        mock_path.exists.return_value = True
        mock_path.name = "fake.task"
        mock_pl_cls.create_from_options.return_value = MagicMock()

        with PoseEngine(model_path=mock_path) as engine:
            assert engine.is_initialised
        assert not engine.is_initialised

    def test_model_not_found_raises(self) -> None:
        engine = PoseEngine(model_path="/nonexistent/model.task")
        with pytest.raises(FileNotFoundError, match="Pose model not found"):
            engine.initialise()

    @patch("edge_agent.vision.pose_engine.PoseLandmarker")
    def test_in_memory_only_no_disk_writes(
        self, mock_pl_cls: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that running pose estimation creates zero files on disk."""
        monkeypatch.chdir(tmp_path)
        before_files = set(tmp_path.rglob("*"))

        mock_landmarker = MagicMock()
        mock_landmarker.detect.return_value = _make_mock_result()
        mock_pl_cls.create_from_options.return_value = mock_landmarker

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "fake.task"

        engine = PoseEngine(model_path=mock_path)
        engine.initialise()
        frame = _make_rgb_frame()
        res = engine.process_frame(frame)
        assert res.is_detected is True
        engine.close()

        after_files = set(tmp_path.rglob("*"))
        assert after_files == before_files, "PoseEngine must never write frames or data to disk"


# ── Ergonomic landmark coverage ──────────────────────────────────────────────

class TestErgonomicLandmarks:
    """Verify that all PRD-required landmark groups are defined."""

    def test_all_groups_present(self) -> None:
        required = {"head", "shoulders", "elbows", "wrists", "hips", "knees", "ankles"}
        assert set(ERGONOMIC_LANDMARKS.keys()) == required

    def test_all_indices_valid(self) -> None:
        for idx in ALL_ERGONOMIC_INDICES:
            assert 0 <= idx <= 32, f"Invalid landmark index: {idx}"


# ── Skeleton visualisation ────────────────────────────────────────────────────

class TestDrawSkeleton:

    def test_no_detection_returns_frame(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = PoseResult(is_detected=False)
        out = draw_skeleton(frame, result)
        assert out is frame  # should return same (unmodified) frame

    def test_draws_on_detected_frame(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = {
            "NOSE": LandmarkPoint(
                name="NOSE", index=0, x=0.5, y=0.3, z=0.0,
                visibility=0.9, presence=0.9, is_visible=True,
            ),
            "LEFT_SHOULDER": LandmarkPoint(
                name="LEFT_SHOULDER", index=11, x=0.4, y=0.5, z=0.0,
                visibility=0.9, presence=0.9, is_visible=True,
            ),
        }
        result = PoseResult(is_detected=True, landmarks=landmarks, visible_count=2)
        out = draw_skeleton(frame, result)
        # Should have drawn something — at least one non-black pixel.
        assert out.sum() > 0


# ── Integration test (requires real model file) ──────────────────────────────

class TestPoseEngineIntegration:
    """Tests that load the actual .task model and run inference."""

    @pytest.fixture
    def model_available(self) -> bool:
        return DEFAULT_POSE_MODEL_PATH.exists()

    def test_real_model_initialises(self, model_available: bool) -> None:
        if not model_available:
            pytest.skip("Pose model not downloaded.")
        engine = PoseEngine()
        engine.initialise()
        assert engine.is_initialised
        engine.close()

    def test_real_model_empty_frame(self, model_available: bool) -> None:
        """A blank frame should produce 'no detection', not crash."""
        if not model_available:
            pytest.skip("Pose model not downloaded.")
        with PoseEngine() as engine:
            result = engine.process_frame(_make_rgb_frame())
            assert isinstance(result, PoseResult)


# ── Live camera + pose estimation bench-test ──────────────────────────────────

class TestPoseLive:
    """Live camera + pose estimation — only run with ``--run-camera``."""

    @pytest.mark.skipif(True, reason="Use --run-camera to enable")
    def test_live_pose_skeleton(self, run_camera: bool) -> None:
        """Open camera, run pose landmarker, draw skeleton on preview window."""
        if not run_camera:
            pytest.skip("Live camera test not requested.")

        if not DEFAULT_POSE_MODEL_PATH.exists():
            pytest.skip("Pose model file not available.")

        from edge_agent.camera.camera import Camera, list_available_cameras
        import cv2 as cv

        available = list_available_cameras()
        if not available:
            pytest.skip("No camera available on this machine.")

        cam = Camera(camera_index=available[0], frame_width=640, frame_height=480)
        cam.open()

        count = 0
        detected = 0
        start = time.monotonic()
        duration_sec = 3.0

        try:
            with PoseEngine() as engine:
                for frame in cam.stream():
                    rgb = frame.to_rgb()
                    result = engine.process_frame(rgb)
                    if result.is_detected:
                        detected += 1

                    vis_frame = frame.image.copy()
                    draw_skeleton(vis_frame, result, draw_labels=True)
                    cv.imshow("EdgeErgo Pose & Skeleton Test (Press 'q' to quit)", vis_frame)
                    if cv.waitKey(1) & 0xFF == ord("q"):
                        break

                    count += 1
                    if time.monotonic() - start >= duration_sec:
                        break
        finally:
            cam.release()
            cv.destroyAllWindows()

        elapsed = time.monotonic() - start
        fps = count / elapsed if elapsed > 0 else 0
        print(f"\n[Pose Bench] {count} frames ({detected} detected) in {elapsed:.2f}s = {fps:.1f} FPS")
        assert count > 0
