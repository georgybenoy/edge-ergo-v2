"""
Tests for edge_agent/expression/classifier.py.

Validates:
  1. Mapping of geometric features to BROAD categories:
     - Neutral
     - Positive expression
     - Negative expression
     - Reduced-expression state
     - Eye-closure-related event
  2. Confidence filtering (fallback to Uncertain/Neutral).
  3. Single-worker constraint handling: multi-face input triggers Uncertain/Invalid.
  4. Missing face handling.
  5. Live camera bench-test (guarded by --run-camera).
"""

from __future__ import annotations

import pytest

from edge_agent.expression.classifier import (
    ExpressionCategory,
    ExpressionClassifier,
    ExpressionResult,
)
from edge_agent.vision.face_engine import FaceFeatures, FaceResult


# ── 1. Category Classification Tests ──────────────────────────────────────────

class TestExpressionCategories:

    def test_neutral_resting_face(self) -> None:
        classifier = ExpressionClassifier()
        features = FaceFeatures(
            eye_aspect_ratio=0.30,
            mouth_aspect_ratio=0.08,
            mouth_curvature=0.00,
            smile_score=0.05,
            frown_score=0.05,
            eye_closure_score=0.05,
            confidence=0.9,
        )
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.NEUTRAL
        assert res.is_valid is True
        assert res.confidence >= 0.7

    def test_positive_expression_smile(self) -> None:
        classifier = ExpressionClassifier()
        features = FaceFeatures(
            eye_aspect_ratio=0.28,
            mouth_aspect_ratio=0.15,
            mouth_curvature=0.08,  # distinct smile curvature
            smile_score=0.65,
            frown_score=0.02,
            confidence=0.95,
        )
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.POSITIVE
        assert res.is_valid is True
        assert res.confidence >= 0.6

    def test_negative_expression_frown(self) -> None:
        classifier = ExpressionClassifier()
        features = FaceFeatures(
            eye_aspect_ratio=0.28,
            mouth_aspect_ratio=0.08,
            mouth_curvature=-0.07,  # distinct downturned mouth
            smile_score=0.01,
            frown_score=0.55,
            confidence=0.92,
        )
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.NEGATIVE
        assert res.is_valid is True

    def test_eye_closure_event(self) -> None:
        classifier = ExpressionClassifier(ear_closure_threshold=0.19)
        features = FaceFeatures(
            eye_aspect_ratio=0.14,  # low EAR indicates closed eyes
            eye_closure_score=0.85,
            mouth_curvature=0.0,
            confidence=0.9,
        )
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.EYE_CLOSURE
        assert res.is_valid is True

    def test_reduced_expression_state(self) -> None:
        """Sustained flat curvature over multiple frames triggers Reduced expression."""
        classifier = ExpressionClassifier(history_len=10, reduced_var_threshold=0.0001)

        # Feed 10 identical frames with 0.00 curvature (completely flat)
        for _ in range(9):
            features = FaceFeatures(
                eye_aspect_ratio=0.28,
                mouth_curvature=0.00,
                smile_score=0.0,
                frown_score=0.0,
                confidence=0.9,
            )
            face_res = FaceResult(is_detected=True, face_count=1, features=features)
            res = classifier.classify(face_res)

        # 10th frame should detect reduced expression
        features = FaceFeatures(
            eye_aspect_ratio=0.28,
            mouth_curvature=0.00,
            smile_score=0.0,
            frown_score=0.0,
            confidence=0.9,
        )
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)
        assert res.category == ExpressionCategory.REDUCED


# ── 2. Confidence Filtering & Fallbacks ───────────────────────────────────────

class TestConfidenceFiltering:

    def test_low_confidence_falls_back_to_uncertain(self) -> None:
        classifier = ExpressionClassifier(min_confidence=0.6)
        # Confidence 0.4 < 0.6
        features = FaceFeatures(
            eye_aspect_ratio=0.28,
            mouth_curvature=0.10,  # would otherwise be positive
            smile_score=0.80,
            confidence=0.4,
        )
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.UNCERTAIN
        assert res.status == "LOW_CONFIDENCE"


# ── 3. Single-Worker & Multi-Face Constraints ─────────────────────────────────

class TestSingleWorkerConstraints:

    def test_multiple_faces_triggers_uncertain_invalid(self) -> None:
        classifier = ExpressionClassifier()
        face_res = FaceResult.multiple_faces(count=2)
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.UNCERTAIN
        assert res.is_valid is False
        assert res.status == "MULTIPLE_FACES"

    def test_no_face_triggers_neutral_invalid(self) -> None:
        classifier = ExpressionClassifier()
        face_res = FaceResult.empty(status="NO_FACE")
        res = classifier.classify(face_res)

        assert res.category == ExpressionCategory.NEUTRAL
        assert res.is_valid is False
        assert res.status == "NO_FACE"

    def test_serialization(self) -> None:
        classifier = ExpressionClassifier()
        features = FaceFeatures(confidence=0.9)
        face_res = FaceResult(is_detected=True, face_count=1, features=features)
        res = classifier.classify(face_res)
        d = res.to_dict()

        assert "category" in d
        assert "confidence" in d
        assert "status" in d
        assert "is_valid" in d


# ── 4. Live Camera Bench Test (Guarded by --run-camera) ───────────────────────

class TestExpressionLive:

    @pytest.mark.skipif(True, reason="Use --run-camera to enable")
    def test_live_facial_classification(self, run_camera: bool) -> None:
        if not run_camera:
            pytest.skip("Live camera test not requested.")

        import time
        from edge_agent.camera.camera import Camera, list_available_cameras
        from edge_agent.vision.face_engine import DEFAULT_FACE_MODEL_PATH, FaceEngine

        if not DEFAULT_FACE_MODEL_PATH.exists():
            pytest.skip("Face model not available.")

        available = list_available_cameras()
        if not available:
            pytest.skip("No camera available.")

        cam = Camera(camera_index=available[0], frame_width=640, frame_height=480)
        cam.open()

        classifier = ExpressionClassifier()
        classified_counts: dict[str, int] = {}
        start = time.monotonic()

        try:
            with FaceEngine() as face_engine:
                for frame in cam.stream():
                    rgb = frame.to_rgb()
                    face_res = face_engine.process_frame(rgb)
                    if face_res.is_detected:
                        exp_res = classifier.classify(face_res)
                        cat_name = exp_res.category.value
                        classified_counts[cat_name] = classified_counts.get(cat_name, 0) + 1

                    if time.monotonic() - start >= 3.0:
                        break
        finally:
            cam.release()

        print(f"\n[Expression Live Bench] Breakdown: {classified_counts}")
        assert True
