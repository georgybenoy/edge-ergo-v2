"""
Tests for edge_agent/vision/face_engine.py.

Validates:
  1. FaceEngine lifecycle (initialise, close, context manager).
  2. Landmark-based feature calculation (EAR, mouth curvature, brow furrow).
  3. Single-worker constraint: multiple faces are flagged/ignored per PRD §27.
  4. Missing face handling: empty/blank frames return clean non-crashing result.
  5. HARD PRIVACY CONSTRAINT (PRD §28):
     - Zero raw face images, crops, or embeddings written to disk.
     - Code audit ensuring no disk write or network calls exist in the module.
  6. Ethical AI disclaimer presence in docstrings.
  7. Real model integration test.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from edge_agent.vision.face_engine import (
    DEFAULT_FACE_MODEL_PATH,
    FaceEngine,
    FaceFeatures,
    FaceResult,
    compute_brow_furrow,
    compute_eye_aspect_ratio,
    compute_mouth_metrics,
)


# ── Mock Landmark Helper ──────────────────────────────────────────────────────

@dataclass
class Point2D:
    x: float
    y: float
    z: float = 0.0


def _make_dummy_rgb(w: int = 640, h: int = 480) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


# ── 1. Geometric Feature Calculations ─────────────────────────────────────────

class TestGeometricFeatures:
    """Verify EAR, MAR, and mouth curvature formulas."""

    def test_eye_aspect_ratio_open_vs_closed(self) -> None:
        # Open eye: horizontal distance = 0.10, vertical opening = 0.035
        outer = Point2D(x=0.40, y=0.30)
        inner = Point2D(x=0.50, y=0.30)
        top1 = Point2D(x=0.43, y=0.28)
        top2 = Point2D(x=0.47, y=0.28)
        bot1 = Point2D(x=0.43, y=0.32)
        bot2 = Point2D(x=0.47, y=0.32)

        open_ear = compute_eye_aspect_ratio(outer, inner, top1, top2, bot1, bot2)
        # v1 = 0.04, v2 = 0.04, h = 0.10 -> (0.04 + 0.04)/(2 * 0.10) = 0.40
        assert open_ear == pytest.approx(0.40, abs=1e-4)

        # Closed eye: vertical opening very small (e.g. 0.005)
        bot1_closed = Point2D(x=0.43, y=0.285)
        bot2_closed = Point2D(x=0.47, y=0.285)
        closed_ear = compute_eye_aspect_ratio(outer, inner, top1, top2, bot1_closed, bot2_closed)
        assert closed_ear < 0.10
        assert closed_ear < open_ear

    def test_mouth_curvature_smile_vs_frown(self) -> None:
        # 468 dummy landmarks
        landmarks = [Point2D(0.5, 0.5) for _ in range(478)]

        # Center of lips: y=0.60
        landmarks[0] = Point2D(0.50, 0.59)   # MOUTH_UPPER_LIP
        landmarks[17] = Point2D(0.50, 0.61)  # MOUTH_LOWER_LIP

        # Case A: Smile — mouth corners are higher (lower y in screen coords)
        landmarks[61] = Point2D(0.42, 0.57)   # MOUTH_CORNER_LEFT (elevated)
        landmarks[291] = Point2D(0.58, 0.57)  # MOUTH_CORNER_RIGHT (elevated)

        mar_smile, curv_smile = compute_mouth_metrics(landmarks)
        assert curv_smile > 0.0, "Smile should produce positive mouth curvature"

        # Case B: Frown — mouth corners are lower (higher y in screen coords)
        landmarks[61] = Point2D(0.42, 0.64)   # MOUTH_CORNER_LEFT (downturned)
        landmarks[291] = Point2D(0.58, 0.64)  # MOUTH_CORNER_RIGHT (downturned)

        mar_frown, curv_frown = compute_mouth_metrics(landmarks)
        assert curv_frown < 0.0, "Frown should produce negative mouth curvature"

    def test_brow_furrow(self) -> None:
        landmarks = [Point2D(0.5, 0.5) for _ in range(478)]
        # Outer eyes width = 0.20
        landmarks[33] = Point2D(0.40, 0.30)
        landmarks[362] = Point2D(0.60, 0.30)

        # Wide brows distance = 0.10
        landmarks[107] = Point2D(0.45, 0.25)
        landmarks[336] = Point2D(0.55, 0.25)
        furrow_normal = compute_brow_furrow(landmarks)
        assert furrow_normal == pytest.approx(0.50, abs=1e-3)

        # Furrowed brows distance = 0.04
        landmarks[107] = Point2D(0.48, 0.25)
        landmarks[336] = Point2D(0.52, 0.25)
        furrow_tight = compute_brow_furrow(landmarks)
        assert furrow_tight < furrow_normal


# ── 2. FaceEngine Lifecycle & Single-Worker Tests (Mocked) ───────────────────

class TestFaceEngineMocked:

    @patch("edge_agent.vision.face_engine.FaceLandmarker")
    def test_initialise_and_close(self, mock_fl_cls: MagicMock) -> None:
        mock_landmarker = MagicMock()
        mock_fl_cls.create_from_options.return_value = mock_landmarker

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "fake_face.task"

        engine = FaceEngine(model_path=mock_path)
        engine.initialise()
        assert engine.is_initialised
        engine.close()
        assert not engine.is_initialised
        mock_landmarker.close.assert_called_once()

    @patch("edge_agent.vision.face_engine.FaceLandmarker")
    def test_no_face_detected_returns_clean_result(self, mock_fl_cls: MagicMock) -> None:
        mock_landmarker = MagicMock()
        # Mock empty detection
        mock_res = MagicMock()
        mock_res.face_landmarks = []
        mock_res.face_blendshapes = []
        mock_landmarker.detect.return_value = mock_res
        mock_fl_cls.create_from_options.return_value = mock_landmarker

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        engine = FaceEngine(model_path=mock_path)
        engine.initialise()
        res = engine.process_frame(_make_dummy_rgb())

        assert res.is_detected is False
        assert res.face_count == 0
        assert res.status == "NO_FACE"
        assert res.features is None
        engine.close()

    @patch("edge_agent.vision.face_engine.FaceLandmarker")
    def test_multiple_faces_triggers_privacy_guard(self, mock_fl_cls: MagicMock) -> None:
        """PRD §27 Single-worker constraint: multiple faces must be ignored/flagged."""
        mock_landmarker = MagicMock()
        mock_res = MagicMock()
        # Simulate 2 people in frame
        mock_res.face_landmarks = [[Point2D(0.5, 0.5) for _ in range(478)], [Point2D(0.8, 0.5) for _ in range(478)]]
        mock_res.face_blendshapes = []
        mock_landmarker.detect.return_value = mock_res
        mock_fl_cls.create_from_options.return_value = mock_landmarker

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        engine = FaceEngine(model_path=mock_path)
        engine.initialise()
        res = engine.process_frame(_make_dummy_rgb())

        assert res.is_detected is False
        assert res.is_multiple_faces is True
        assert res.face_count == 2
        assert res.status == "MULTIPLE_FACES"
        engine.close()


# ── 3. Hard Privacy & Ethical AI Constraints (PRD §6, §27, §28) ───────────────

class TestPrivacyAndEthicalConstraints:

    def test_privacy_no_disk_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PRD §28: No raw frames, crops, or landmarks may ever be written to disk."""
        monkeypatch.chdir(tmp_path)
        before_files = set(tmp_path.rglob("*"))

        mock_landmarker = MagicMock()
        mock_res = MagicMock()
        mock_res.face_landmarks = []
        mock_landmarker.detect.return_value = mock_res

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        with patch("edge_agent.vision.face_engine.FaceLandmarker") as mock_fl:
            mock_fl.create_from_options.return_value = mock_landmarker
            engine = FaceEngine(model_path=mock_path)
            engine.initialise()
            engine.process_frame(_make_dummy_rgb())
            engine.close()

        after_files = set(tmp_path.rglob("*"))
        assert after_files == before_files, "FaceEngine must never write to disk"

    def test_code_audit_no_forbidden_disk_or_network_calls(self) -> None:
        """Audit face_engine.py and classifier.py source code for dangerous calls."""
        vision_dir = Path(__file__).resolve().parent.parent.parent / "edge_agent"
        target_files = [
            vision_dir / "vision" / "face_engine.py",
            vision_dir / "expression" / "classifier.py",
        ]

        forbidden_calls = ("imwrite", "imencode", "socket", "urllib", "requests", "httpx")

        for fpath in target_files:
            assert fpath.exists()
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            for bad_call in forbidden_calls:
                assert f".{bad_call}(" not in content, (
                    f"Forbidden call .{bad_call}() found in {fpath.name}"
                )

    def test_ethical_ai_non_goals_disclaimer_present(self) -> None:
        """PRD §6, §27: Code must explicitly disclaim medical/psychological diagnoses."""
        vision_dir = Path(__file__).resolve().parent.parent.parent / "edge_agent"
        target_files = [
            vision_dir / "vision" / "face_engine.py",
            vision_dir / "expression" / "classifier.py",
        ]

        disclaimer_keywords = ("stress", "depression", "anxiety", "burnout", "medical")

        for fpath in target_files:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().lower()

            for kw in disclaimer_keywords:
                assert kw in content, f"Disclaimer keyword '{kw}' missing from {fpath.name}"


# ── 4. Integration Test with Real Model ───────────────────────────────────────

class TestFaceEngineIntegration:
    """Verifies that the actual .task file loads and processes a blank frame."""

    def test_real_model_loads_and_runs(self) -> None:
        if not DEFAULT_FACE_MODEL_PATH.exists():
            pytest.skip("Face landmarker model not downloaded.")

        with FaceEngine() as engine:
            assert engine.is_initialised
            res = engine.process_frame(_make_dummy_rgb())
            assert isinstance(res, FaceResult)
            # Blank frame should report no face
            assert res.face_count == 0
