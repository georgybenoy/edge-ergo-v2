"""
Facial Analysis Engine (MediaPipe Face Landmarker).

Extracts geometric facial landmarks and derives normalized features:
  - Eye Aspect Ratio (EAR) for blink / eye-closure detection
  - Mouth Curvature / Smile Ratio for expression classification
  - Brow position / furrow metrics
  - Multi-face detection for single-worker isolation

================================================================================
ETHICAL AI & NON-GOALS DISCLAIMER (PRD §6, §27)
--------------------------------------------------------------------------------
This system performs strictly BROAD geometric landmark extraction.
It does NOT infer, diagnose, or monitor:
  - Stress, depression, anxiety, or mental health disorders
  - Worker attention, engagement, or emotional state
  - Fatigue, burnout, or cognitive impairment
  - Any medical, clinical, or psychological condition
This software is intended solely for ergonomic workstation monitoring and must
NEVER be deployed for emotional surveillance, discipline, or productivity scoring.

================================================================================
PRIVACY INVARIANT (PRD §28 — NON-NEGOTIABLE)
--------------------------------------------------------------------------------
Face images, face crops, facial landmark coordinates, facial landmark images,
face embeddings, and biometric identity markers are NEVER written to disk,
never logged, and never transmitted across the network.
All processing is strictly in-memory. Only anonymous aggregated telemetry
(percentages over time) may ever leave the local Edge Agent.
================================================================================
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    FaceLandmarkerResult,
    RunningMode,
)

from edge_agent.vision.preprocessing import (
    MEDIAPIPE_PREPROCESSING,
    preprocess,
    validate_frame,
)

logger = logging.getLogger(__name__)

# ── Model Path ────────────────────────────────────────────────────────────────

_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_FACE_MODEL_PATH = _DEFAULT_MODEL_DIR / "face_landmarker.task"


# ── Canonical Landmark Indices (468/478 Face Mesh) ────────────────────────────

# Left Eye indices for Eye Aspect Ratio (EAR)
LEFT_EYE_OUTER = 33
LEFT_EYE_INNER = 133
LEFT_EYE_TOP_1 = 160
LEFT_EYE_TOP_2 = 158
LEFT_EYE_BOTTOM_1 = 144
LEFT_EYE_BOTTOM_2 = 153

# Right Eye indices for EAR
RIGHT_EYE_OUTER = 362
RIGHT_EYE_INNER = 263
RIGHT_EYE_TOP_1 = 385
RIGHT_EYE_TOP_2 = 387
RIGHT_EYE_BOTTOM_1 = 380
RIGHT_EYE_BOTTOM_2 = 373

# Mouth indices
MOUTH_CORNER_LEFT = 61
MOUTH_CORNER_RIGHT = 291
MOUTH_UPPER_LIP = 0
MOUTH_LOWER_LIP = 17
MOUTH_INNER_UPPER = 13
MOUTH_INNER_LOWER = 14

# Eyebrow indices
LEFT_INNER_BROW = 107
RIGHT_INNER_BROW = 336
NOSE_BRIDGE = 168


# ── Extracted Feature Data Structures ─────────────────────────────────────────

@dataclass
class FaceFeatures:
    """Normalized geometric and blendshape facial features for one face.

    All metrics are scale-invariant ratios or normalized scores in [0.0, 1.0].
    No raw pixels or identity information are retained.
    """
    eye_aspect_ratio: float = 0.0       # Average EAR across both eyes (open ~0.25-0.35, closed <0.18)
    left_ear: float = 0.0
    right_ear: float = 0.0
    mouth_aspect_ratio: float = 0.0     # Mouth opening ratio (height / width)
    mouth_curvature: float = 0.0        # Corner height vs lip center (+ = upturned/smile, - = downturned)
    brow_furrow: float = 0.0            # Inner eyebrow distance ratio
    smile_score: float = 0.0            # Blendshape or derived smile strength [0.0, 1.0]
    frown_score: float = 0.0            # Blendshape or derived frown strength [0.0, 1.0]
    eye_closure_score: float = 0.0      # Probability / degree of eye closure [0.0, 1.0]
    confidence: float = 0.0             # Face detection confidence

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class FaceResult:
    """Result of facial detection for a single video frame.

    Handles single-worker and multi-face edge cases per PRD §27.
    """
    is_detected: bool = False
    face_count: int = 0
    is_multiple_faces: bool = False
    status: str = "NO_FACE"             # 'OK', 'NO_FACE', 'MULTIPLE_FACES', 'INVALID_FRAME'
    features: Optional[FaceFeatures] = None
    confidence: float = 0.0
    timestamp: float = 0.0

    @classmethod
    def empty(cls, status: str = "NO_FACE", timestamp: float = 0.0) -> FaceResult:
        return cls(is_detected=False, face_count=0, status=status, timestamp=timestamp)

    @classmethod
    def multiple_faces(cls, count: int, timestamp: float = 0.0) -> FaceResult:
        return cls(
            is_detected=False,
            face_count=count,
            is_multiple_faces=True,
            status="MULTIPLE_FACES",
            timestamp=timestamp,
        )


# ── Feature Extraction Functions ──────────────────────────────────────────────

def _dist_2d(p1: Any, p2: Any) -> float:
    """Euclidean distance between two landmarks (using x, y)."""
    dx = float(p1.x) - float(p2.x)
    dy = float(p1.y) - float(p2.y)
    return float(np.sqrt(dx * dx + dy * dy))


def compute_eye_aspect_ratio(
    outer: Any,
    inner: Any,
    top1: Any,
    top2: Any,
    bot1: Any,
    bot2: Any,
) -> float:
    """Compute Eye Aspect Ratio (EAR) based on Soukupová & Čech (2016).

    EAR = (||top1 - bot1|| + ||top2 - bot2||) / (2 * ||outer - inner||)
    """
    v1 = _dist_2d(top1, bot1)
    v2 = _dist_2d(top2, bot2)
    h = _dist_2d(outer, inner)
    if h < 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


def compute_mouth_metrics(landmarks: Sequence[Any]) -> tuple[float, float]:
    """Compute Mouth Aspect Ratio (MAR) and mouth corner curvature.

    Returns:
        (mouth_aspect_ratio, mouth_curvature)
        mouth_curvature > 0: corners higher than mouth center (smile cue)
        mouth_curvature < 0: corners lower than mouth center (frown cue)
    """
    left_corner = landmarks[MOUTH_CORNER_LEFT]
    right_corner = landmarks[MOUTH_CORNER_RIGHT]
    upper_lip = landmarks[MOUTH_UPPER_LIP]
    lower_lip = landmarks[MOUTH_LOWER_LIP]

    width = _dist_2d(left_corner, right_corner)
    height = _dist_2d(upper_lip, lower_lip)
    mar = height / width if width > 1e-6 else 0.0

    # In screen coordinates, y points DOWN: smaller y = higher on face.
    # Mouth center y:
    center_y = (upper_lip.y + lower_lip.y) / 2.0
    corners_avg_y = (left_corner.y + right_corner.y) / 2.0

    # If corners are higher than center (corners_avg_y < center_y), curvature is positive.
    curvature = (center_y - corners_avg_y) / (width + 1e-6)
    return mar, float(curvature)


def compute_brow_furrow(landmarks: Sequence[Any]) -> float:
    """Compute inner eyebrow distance relative to inter-pupillary / face width."""
    left_brow = landmarks[LEFT_INNER_BROW]
    right_brow = landmarks[RIGHT_INNER_BROW]
    left_eye_outer = landmarks[LEFT_EYE_OUTER]
    right_eye_outer = landmarks[RIGHT_EYE_OUTER]

    brow_dist = _dist_2d(left_brow, right_brow)
    eye_dist = _dist_2d(left_eye_outer, right_eye_outer)
    if eye_dist < 1e-6:
        return 0.0
    return float(brow_dist / eye_dist)


# ── Face Engine Class ─────────────────────────────────────────────────────────

class FaceEngine:
    """Facial feature extractor wrapping MediaPipe FaceLandmarker.

    Guarantees:
      - Raw images/crops are processed in-memory and NEVER persisted to disk.
      - Discards frames after computing scalar features.
      - Enforces the single-worker constraint: multiple faces are flagged as an anomaly.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path, Any]] = None,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        max_faces: int = 2,  # allow 2 so we can detect single-worker violations
    ) -> None:
        if model_path is None:
            self._model_path = DEFAULT_FACE_MODEL_PATH
        elif isinstance(model_path, (str, Path)):
            self._model_path = Path(model_path)
        else:
            self._model_path = model_path

        self._min_detection_confidence = min_detection_confidence
        self._min_presence_confidence = min_presence_confidence
        self._max_faces = max_faces
        self._landmarker: Optional[FaceLandmarker] = None
        self._is_initialised = False

    @property
    def is_initialised(self) -> bool:
        return self._is_initialised

    def __enter__(self) -> FaceEngine:
        self.initialise()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def initialise(self) -> None:
        """Load model and configure FaceLandmarker."""
        if self._is_initialised:
            return

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Face model not found at {self._model_path}. "
                f"Download from: https://storage.googleapis.com/mediapipe-models/"
                f"face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            )

        try:
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(self._model_path)),
                running_mode=RunningMode.IMAGE,
                num_faces=self._max_faces,
                min_face_detection_confidence=self._min_detection_confidence,
                min_face_presence_confidence=self._min_presence_confidence,
                output_face_blendshapes=True,
            )
            self._landmarker = FaceLandmarker.create_from_options(options)
            self._is_initialised = True
            logger.info("FaceEngine initialised with model %s", self._model_path)
        except Exception as exc:
            self._is_initialised = False
            raise RuntimeError(f"Failed to initialise MediaPipe FaceLandmarker: {exc}") from exc

    def close(self) -> None:
        """Release FaceLandmarker resources."""
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None
        self._is_initialised = False

    def process_frame(
        self,
        rgb_frame: np.ndarray,
        *,
        timestamp: float = 0.0,
    ) -> FaceResult:
        """Process an RGB frame and extract facial metrics in-memory.

        PRD §28 Privacy Audit Check:
        No image data is saved to disk, logged, or retained after this call.

        Args:
            rgb_frame: RGB numpy array (e.g. from Camera.to_rgb()).
            timestamp: Timestamp in seconds.

        Returns:
            FaceResult containing scalar FaceFeatures, or flags for no-face/multi-face.
        """
        # Runtime privacy assertion: ensure frame is an in-memory numpy array
        assert isinstance(rgb_frame, np.ndarray), "Input frame must be an in-memory NumPy array"

        if not self._is_initialised or self._landmarker is None:
            raise RuntimeError("FaceEngine is not initialised. Call initialise() or use context manager.")

        if not validate_frame(rgb_frame):
            return FaceResult.empty(status="INVALID_FRAME", timestamp=timestamp)

        # Ensure RGB input
        processed = preprocess(rgb_frame, MEDIAPIPE_PREPROCESSING)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=processed)
        result: FaceLandmarkerResult = self._landmarker.detect(mp_image)

        face_count = len(result.face_landmarks)

        # Case 1: No face found
        if face_count == 0:
            return FaceResult.empty(status="NO_FACE", timestamp=timestamp)

        # Case 2: Multiple faces detected (single-worker constraint violation)
        if face_count > 1:
            logger.warning("Multiple faces detected (%d) — ignoring frame for privacy", face_count)
            return FaceResult.multiple_faces(count=face_count, timestamp=timestamp)

        # Case 3: Exactly 1 face detected
        landmarks = result.face_landmarks[0]
        if len(landmarks) < 468:
            return FaceResult.empty(status="PARTIAL_FACE", timestamp=timestamp)

        # Compute Eye Aspect Ratios
        left_ear = compute_eye_aspect_ratio(
            landmarks[LEFT_EYE_OUTER],
            landmarks[LEFT_EYE_INNER],
            landmarks[LEFT_EYE_TOP_1],
            landmarks[LEFT_EYE_TOP_2],
            landmarks[LEFT_EYE_BOTTOM_1],
            landmarks[LEFT_EYE_BOTTOM_2],
        )
        right_ear = compute_eye_aspect_ratio(
            landmarks[RIGHT_EYE_OUTER],
            landmarks[RIGHT_EYE_INNER],
            landmarks[RIGHT_EYE_TOP_1],
            landmarks[RIGHT_EYE_TOP_2],
            landmarks[RIGHT_EYE_BOTTOM_1],
            landmarks[RIGHT_EYE_BOTTOM_2],
        )
        avg_ear = (left_ear + right_ear) / 2.0

        mar, mouth_curv = compute_mouth_metrics(landmarks)
        brow_furrow = compute_brow_furrow(landmarks)

        # Parse blendshapes if available
        smile_bs = 0.0
        frown_bs = 0.0
        blink_bs = 0.0

        if result.face_blendshapes and len(result.face_blendshapes) > 0:
            for cat in result.face_blendshapes[0]:
                name = cat.category_name
                score = float(cat.score)
                if name in ("mouthSmileLeft", "mouthSmileRight"):
                    smile_bs = max(smile_bs, score)
                elif name in ("mouthFrownLeft", "mouthFrownRight", "mouthPressLeft", "mouthPressRight"):
                    frown_bs = max(frown_bs, score)
                elif name in ("eyeBlinkLeft", "eyeBlinkRight"):
                    blink_bs = max(blink_bs, score)

        # Combine geometric and blendshape scores
        smile_score = max(smile_bs, max(0.0, mouth_curv * 4.0))
        frown_score = max(frown_bs, max(0.0, -mouth_curv * 4.0))

        # Eye closure score: high when EAR is low (< 0.20) or blink blendshape is high
        ear_closure = max(0.0, min(1.0, (0.22 - avg_ear) / 0.10)) if avg_ear < 0.22 else 0.0
        eye_closure_score = max(blink_bs, ear_closure)

        features = FaceFeatures(
            eye_aspect_ratio=round(avg_ear, 4),
            left_ear=round(left_ear, 4),
            right_ear=round(right_ear, 4),
            mouth_aspect_ratio=round(mar, 4),
            mouth_curvature=round(mouth_curv, 4),
            brow_furrow=round(brow_furrow, 4),
            smile_score=round(smile_score, 4),
            frown_score=round(frown_score, 4),
            eye_closure_score=round(eye_closure_score, 4),
            confidence=0.9,
        )

        return FaceResult(
            is_detected=True,
            face_count=1,
            is_multiple_faces=False,
            status="OK",
            features=features,
            confidence=0.9,
            timestamp=timestamp,
        )
