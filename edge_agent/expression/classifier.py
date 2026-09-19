"""
Broad Facial Expression Classifier.

Maps geometric and blendshape facial features to BROAD categories only:
  - Neutral
  - Positive expression
  - Negative expression
  - Reduced-expression state
  - Eye-closure-related event
  - Uncertain / Neutral (fallback on low confidence)

================================================================================
ETHICAL AI & NON-GOALS DISCLAIMER (PRD §6, §27 — MANDATORY)
--------------------------------------------------------------------------------
This classifier assigns BROAD descriptive visual categories based strictly on
low-level facial landmark geometry (e.g. mouth curvature, eye aspect ratio).

It DOES NOT:
  - Infer, assess, or diagnose stress, depression, anxiety, or burnout
  - Detect or evaluate mood, emotion, engagement, honesty, or productivity
  - Predict or diagnose any psychological, mental health, or medical condition
  - Perform facial recognition or identity profiling

All outputs are non-clinical, coarse visual descriptors designed solely for
high-level ergonomic posture and blink-rate context. It must NEVER be used for
emotional monitoring or worker disciplinary assessment.

================================================================================
PRIVACY GUARANTEE (PRD §28)
--------------------------------------------------------------------------------
This module receives only scalar Feature numbers (e.g. EAR = 0.28).
It has NO access to raw camera frames, face images, or face embeddings.
Zero raw biometric data is ever stored, written to disk, or transmitted.
================================================================================
"""

from __future__ import annotations

import collections
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Deque, Optional

import numpy as np

from edge_agent.vision.face_engine import FaceFeatures, FaceResult

logger = logging.getLogger(__name__)


# ── Broad Expression Categories (PRD §27) ────────────────────────────────────

class ExpressionCategory(str, Enum):
    """Broad expression categories strictly defined per PRD §27.

    These are coarse visual descriptors, NOT emotional or psychological states.
    """
    NEUTRAL = "Neutral"
    POSITIVE = "Positive expression"
    NEGATIVE = "Negative expression"
    REDUCED = "Reduced-expression state"
    EYE_CLOSURE = "Eye-closure-related event"
    UNCERTAIN = "Uncertain/Neutral"


# ── Classification Result ─────────────────────────────────────────────────────

@dataclass
class ExpressionResult:
    """Output of broad facial expression classification."""
    category: ExpressionCategory
    confidence: float
    features: Optional[FaceFeatures] = None
    timestamp: float = 0.0
    status: str = "OK"
    is_valid: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "confidence": round(self.confidence, 3),
            "status": self.status,
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
        }


# ── Classifier Configuration & Implementation ─────────────────────────────────

class ExpressionClassifier:
    """Lightweight classifier mapping FaceFeatures to broad categories.

    Applies confidence filtering so low-confidence or ambiguous classifications
    fall back to 'Uncertain/Neutral' rather than a forced guess.

    Parameters:
        ear_closure_threshold: EAR below which an eye-closure event is triggered (default 0.19).
        smile_threshold:       Smile strength threshold for positive expression (default 0.35).
        frown_threshold:       Frown strength threshold for negative expression (default 0.25).
        reduced_var_threshold: Variance threshold over history buffer for reduced-expression (default 0.0005).
        min_confidence:        Confidence threshold below which result falls back to Uncertain/Neutral (default 0.5).
        history_len:           Number of frames to observe for reduced-expression variance (default 30).
    """

    def __init__(
        self,
        ear_closure_threshold: float = 0.19,
        smile_threshold: float = 0.35,
        frown_threshold: float = 0.25,
        reduced_var_threshold: float = 0.0005,
        min_confidence: float = 0.5,
        history_len: int = 30,
    ) -> None:
        self.ear_closure_threshold = ear_closure_threshold
        self.smile_threshold = smile_threshold
        self.frown_threshold = frown_threshold
        self.reduced_var_threshold = reduced_var_threshold
        self.min_confidence = min_confidence
        self.history_len = history_len

        # Sliding window of recent mouth curvature values to detect flat/reduced expression
        self._curvature_history: Deque[float] = collections.deque(maxlen=history_len)

    def reset(self) -> None:
        """Clear temporal history."""
        self._curvature_history.clear()

    def classify(
        self,
        face_result: FaceResult,
        *,
        timestamp: float = 0.0,
    ) -> ExpressionResult:
        """Classify a FaceResult into a broad expression category.

        Handles edge cases:
          - No face detected -> Neutral / Invalid
          - Multiple faces detected -> Uncertain / Invalid (single-worker constraint)
          - Low confidence -> Uncertain/Neutral
        """
        # Case 1: No face in frame or None result
        if face_result is None or not getattr(face_result, "is_detected", False):
            self._curvature_history.clear()
            status = getattr(face_result, "status", "NO_FACE") if face_result else "NO_FACE"
            is_mult = getattr(face_result, "is_multiple_faces", False) if face_result else False
            return ExpressionResult(
                category=ExpressionCategory.UNCERTAIN if is_mult else ExpressionCategory.NEUTRAL,
                confidence=0.0,
                features=None,
                timestamp=timestamp,
                status=status,
                is_valid=False,
            )

        features = face_result.features
        if features is None:
            return ExpressionResult(
                category=ExpressionCategory.NEUTRAL,
                confidence=0.0,
                timestamp=timestamp,
                status="NO_FEATURES",
                is_valid=False,
            )

        # Case 2: Confidence filtering — fallback to Uncertain/Neutral
        if features.confidence < self.min_confidence:
            return ExpressionResult(
                category=ExpressionCategory.UNCERTAIN,
                confidence=features.confidence,
                features=features,
                timestamp=timestamp,
                status="LOW_CONFIDENCE",
                is_valid=True,
            )

        # Track history for reduced expression detection
        self._curvature_history.append(features.mouth_curvature)

        # 1. Eye-closure-related event takes highest visual precedence
        if features.eye_aspect_ratio < self.ear_closure_threshold or features.eye_closure_score > 0.60:
            closure_conf = max(0.6, features.eye_closure_score)
            return ExpressionResult(
                category=ExpressionCategory.EYE_CLOSURE,
                confidence=round(closure_conf, 3),
                features=features,
                timestamp=timestamp,
                status="OK",
                is_valid=True,
            )

        # 2. Positive expression (smile / upturned mouth corners)
        if features.smile_score >= self.smile_threshold or features.mouth_curvature > 0.04:
            pos_conf = max(features.smile_score, min(1.0, features.mouth_curvature * 10.0))
            return ExpressionResult(
                category=ExpressionCategory.POSITIVE,
                confidence=round(pos_conf, 3),
                features=features,
                timestamp=timestamp,
                status="OK",
                is_valid=True,
            )

        # 3. Negative expression (frown / downturned mouth corners / brow furrow)
        if features.frown_score >= self.frown_threshold or features.mouth_curvature < -0.04:
            neg_conf = max(features.frown_score, min(1.0, abs(features.mouth_curvature) * 10.0))
            return ExpressionResult(
                category=ExpressionCategory.NEGATIVE,
                confidence=round(neg_conf, 3),
                features=features,
                timestamp=timestamp,
                status="OK",
                is_valid=True,
            )

        # 4. Reduced-expression state (very low variance over window)
        if len(self._curvature_history) >= self.history_len // 2:
            var = float(np.var(self._curvature_history))
            if var < self.reduced_var_threshold and abs(features.mouth_curvature) < 0.02:
                return ExpressionResult(
                    category=ExpressionCategory.REDUCED,
                    confidence=0.75,
                    features=features,
                    timestamp=timestamp,
                    status="OK",
                    is_valid=True,
                )

        # 5. Default: Neutral baseline
        return ExpressionResult(
            category=ExpressionCategory.NEUTRAL,
            confidence=0.85,
            features=features,
            timestamp=timestamp,
            status="OK",
            is_valid=True,
        )
