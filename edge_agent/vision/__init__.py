"""
EdgeErgo — Vision Module.

Provides:
  - PoseEngine: MediaPipe Pose Landmarker wrapper for ergonomic landmark extraction.
  - FaceEngine: MediaPipe Face Landmarker wrapper for privacy-preserving facial analysis.
  - PoseResult, LandmarkPoint: Typed pose data structures with explicit confidence tracking.
  - FaceResult, FaceFeatures: Normalized scalar facial metrics without raw images.
  - draw_skeleton: Debug/demo skeleton overlay.
  - Preprocessing utilities: Shared frame validation, colour conversion, resize, normalisation.
"""

from edge_agent.vision.face_engine import (
    DEFAULT_FACE_MODEL_PATH,
    FaceEngine,
    FaceFeatures,
    FaceResult,
    compute_brow_furrow,
    compute_eye_aspect_ratio,
    compute_mouth_metrics,
)
from edge_agent.vision.pose_engine import (
    ALL_ERGONOMIC_INDICES,
    DEFAULT_POSE_MODEL_PATH,
    ERGONOMIC_LANDMARKS,
    LandmarkGroup,
    LandmarkPoint,
    PoseEngine,
    PoseResult,
    draw_skeleton,
)
from edge_agent.vision.preprocessing import (
    MEDIAPIPE_PREPROCESSING,
    ColorSpace,
    PreprocessConfig,
    convert_color,
    estimate_brightness,
    normalize_frame,
    preprocess,
    resize_frame,
    validate_frame,
)

__all__ = [
    # Pose Engine
    "PoseEngine",
    "PoseResult",
    "LandmarkPoint",
    "LandmarkGroup",
    "ERGONOMIC_LANDMARKS",
    "ALL_ERGONOMIC_INDICES",
    "DEFAULT_POSE_MODEL_PATH",
    "draw_skeleton",
    # Face Engine
    "FaceEngine",
    "FaceFeatures",
    "FaceResult",
    "DEFAULT_FACE_MODEL_PATH",
    "compute_eye_aspect_ratio",
    "compute_mouth_metrics",
    "compute_brow_furrow",
    # Preprocessing
    "ColorSpace",
    "PreprocessConfig",
    "MEDIAPIPE_PREPROCESSING",
    "convert_color",
    "resize_frame",
    "normalize_frame",
    "validate_frame",
    "estimate_brightness",
    "preprocess",
]
