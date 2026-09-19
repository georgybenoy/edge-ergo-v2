"""
Pose estimation engine (MediaPipe Pose Landmarker — Tasks API).

Extracts body landmarks from a single-person RGB frame and returns
them as structured ``LandmarkPoint`` objects with per-point confidence.
Raw frames are processed in-memory only — never written to disk.

Key design decisions
--------------------
- Low-confidence landmarks are explicitly flagged (``is_visible=False``)
  and **not** treated as bad posture.  Downstream consumers (geometry,
  ergonomics) must check visibility before using a point.
- "No person" and "partially visible person" both produce a valid
  ``PoseResult`` with ``is_detected=False`` or reduced visibility —
  never an exception.
- This module has no knowledge of angles, RULA, or REBA.  It only
  produces raw landmark data (keeps geometry engine independent).

Dependencies: mediapipe, cv2, numpy — no ergonomics, no storage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmark,
    PoseLandmarker,
    PoseLandmarkerOptions,
    PoseLandmarkerResult,
    PoseLandmarksConnections,
    RunningMode,
)

from edge_agent.vision.preprocessing import (
    ColorSpace,
    preprocess,
    MEDIAPIPE_PREPROCESSING,
    validate_frame,
)

logger = logging.getLogger(__name__)


# ── Default model path ────────────────────────────────────────────────────────

_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_POSE_MODEL_PATH = _DEFAULT_MODEL_DIR / "pose_landmarker_lite.task"


# ── Ergonomic landmark groups ────────────────────────────────────────────────
# Maps the PRD-required body categories to MediaPipe PoseLandmark indices.

class LandmarkGroup(IntEnum):
    """Semantic groups of landmarks relevant to ergonomic analysis."""
    HEAD = 0
    SHOULDER = 1
    ELBOW = 2
    WRIST = 3
    HIP = 4
    KNEE = 5
    ANKLE = 6


#: Which MediaPipe landmarks belong to each ergonomic group.
ERGONOMIC_LANDMARKS: dict[str, list[PoseLandmark]] = {
    # Head / face region
    "head": [
        PoseLandmark.NOSE,
        PoseLandmark.LEFT_EYE,
        PoseLandmark.RIGHT_EYE,
        PoseLandmark.LEFT_EAR,
        PoseLandmark.RIGHT_EAR,
        PoseLandmark.MOUTH_LEFT,
        PoseLandmark.MOUTH_RIGHT,
    ],
    # Shoulders
    "shoulders": [
        PoseLandmark.LEFT_SHOULDER,
        PoseLandmark.RIGHT_SHOULDER,
    ],
    # Elbows
    "elbows": [
        PoseLandmark.LEFT_ELBOW,
        PoseLandmark.RIGHT_ELBOW,
    ],
    # Wrists
    "wrists": [
        PoseLandmark.LEFT_WRIST,
        PoseLandmark.RIGHT_WRIST,
    ],
    # Hips
    "hips": [
        PoseLandmark.LEFT_HIP,
        PoseLandmark.RIGHT_HIP,
    ],
    # Knees
    "knees": [
        PoseLandmark.LEFT_KNEE,
        PoseLandmark.RIGHT_KNEE,
    ],
    # Ankles
    "ankles": [
        PoseLandmark.LEFT_ANKLE,
        PoseLandmark.RIGHT_ANKLE,
    ],
}

#: Flat set of all ergonomically relevant landmark indices.
ALL_ERGONOMIC_INDICES: set[int] = {
    lm.value for group in ERGONOMIC_LANDMARKS.values() for lm in group
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LandmarkPoint:
    """A single detected landmark with coordinates and confidence.

    Attributes:
        name:         Human-readable landmark name (e.g. "LEFT_SHOULDER").
        index:        MediaPipe PoseLandmark integer index.
        x:            Normalised x coordinate [0.0, 1.0] in image space.
        y:            Normalised y coordinate [0.0, 1.0] in image space.
        z:            Normalised depth relative to the hip midpoint.
        world_x:      World-space x in metres (from hip centre).
        world_y:      World-space y in metres.
        world_z:      World-space z in metres.
        visibility:   MediaPipe's visibility score [0.0, 1.0].
        presence:     MediaPipe's presence score [0.0, 1.0].
        is_visible:   Whether this point should be trusted for analysis
                      (visibility ≥ threshold).  *Low-confidence points
                      are NOT bad posture — they are low confidence.*
    """
    name: str
    index: int
    # Normalised image coordinates
    x: float
    y: float
    z: float
    # World coordinates (metres)
    world_x: float = 0.0
    world_y: float = 0.0
    world_z: float = 0.0
    # Confidence
    visibility: float = 0.0
    presence: float = 0.0
    is_visible: bool = False


@dataclass
class PoseResult:
    """Result of pose detection on a single frame.

    Attributes:
        is_detected:        True if at least one person was found.
        landmarks:          Dict of landmark name → LandmarkPoint for all
                            33 MediaPipe pose landmarks.
        ergonomic_landmarks: Same dict filtered to only the ergonomically
                            relevant points (head, shoulders, elbows,
                            wrists, hips, knees, ankles).
        visible_count:      How many landmarks passed the visibility
                            threshold.
        total_count:        Total landmarks expected (33).
        detection_confidence: Overall confidence for the detection.
        is_partial:         True if a person was detected but many key
                            landmarks have low visibility (partial
                            occlusion / person at frame edge).
    """
    is_detected: bool = False
    landmarks: dict[str, LandmarkPoint] = field(default_factory=dict)
    ergonomic_landmarks: dict[str, LandmarkPoint] = field(default_factory=dict)
    visible_count: int = 0
    total_count: int = 33
    detection_confidence: float = 0.0
    is_partial: bool = False

    def get(self, landmark: PoseLandmark) -> Optional[LandmarkPoint]:
        """Look up a landmark by its MediaPipe enum."""
        return self.landmarks.get(landmark.name)

    def get_visible(self, landmark: PoseLandmark) -> Optional[LandmarkPoint]:
        """Look up a landmark only if it passes the visibility threshold."""
        pt = self.landmarks.get(landmark.name)
        if pt is not None and pt.is_visible:
            return pt
        return None

    @property
    def visible_percentage(self) -> float:
        """Percentage of all 33 landmarks that are visible."""
        return (self.visible_count / self.total_count * 100.0) if self.total_count > 0 else 0.0

    @property
    def ergonomic_visible_percentage(self) -> float:
        """Percentage of ergonomic landmarks that are visible."""
        if not self.ergonomic_landmarks:
            return 0.0
        visible = sum(1 for lm in self.ergonomic_landmarks.values() if lm.is_visible)
        return visible / len(self.ergonomic_landmarks) * 100.0


# ── Pose Engine ───────────────────────────────────────────────────────────────

class PoseEngine:
    """MediaPipe Pose Landmarker wrapper.

    Typical usage::

        engine = PoseEngine()
        engine.initialise()
        try:
            result = engine.process_frame(rgb_frame)
            if result.is_detected:
                shoulder = result.get_visible(PoseLandmark.LEFT_SHOULDER)
                if shoulder is not None:
                    print(f"Left shoulder at ({shoulder.x:.2f}, {shoulder.y:.2f})")
        finally:
            engine.close()

    Or as a context manager::

        with PoseEngine() as engine:
            result = engine.process_frame(rgb_frame)
    """

    # Minimum fraction of ergonomic landmarks that must be visible to
    # consider the detection "complete" (vs. partial).
    PARTIAL_DETECTION_THRESHOLD = 0.5

    def __init__(
        self,
        model_path: Path | str | None = None,
        visibility_threshold: float = 0.5,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        """Configure the pose engine.

        Args:
            model_path:               Path to the .task model bundle.
            visibility_threshold:     Minimum visibility score to mark a
                                      landmark as ``is_visible=True``.
            min_detection_confidence: MediaPipe detection confidence.
            min_presence_confidence:  MediaPipe presence confidence.
            min_tracking_confidence:  MediaPipe tracking confidence.
        """
        if model_path is None:
            self._model_path = DEFAULT_POSE_MODEL_PATH
        elif isinstance(model_path, (str, Path)):
            self._model_path = Path(model_path)
        else:
            self._model_path = model_path
        self._visibility_threshold = visibility_threshold
        self._min_detection_confidence = min_detection_confidence
        self._min_presence_confidence = min_presence_confidence
        self._min_tracking_confidence = min_tracking_confidence

        self._landmarker: Optional[PoseLandmarker] = None
        self._is_initialised = False
        self._frame_count = 0

        logger.info(
            "PoseEngine configured: model=%s, visibility_thresh=%.2f",
            self._model_path.name, visibility_threshold,
        )

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self) -> PoseEngine:
        self.initialise()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_initialised(self) -> bool:
        return self._is_initialised

    @property
    def visibility_threshold(self) -> float:
        return self._visibility_threshold

    @property
    def frame_count(self) -> int:
        """Total frames processed since initialisation."""
        return self._frame_count

    # ── Lifecycle ─────────────────────────────────────────────────────

    def initialise(self) -> None:
        """Load the model and create the PoseLandmarker.

        Raises:
            FileNotFoundError: If the model file doesn't exist.
            RuntimeError:      If MediaPipe initialisation fails.
        """
        if self._is_initialised:
            logger.warning("PoseEngine already initialised — skipping.")
            return

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Pose model not found at {self._model_path}. "
                f"Download from: https://storage.googleapis.com/mediapipe-models/"
                f"pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
            )

        try:
            options = PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(self._model_path)),
                running_mode=RunningMode.IMAGE,
                num_poses=1,  # single-person only (PRD requirement)
                min_pose_detection_confidence=self._min_detection_confidence,
                min_pose_presence_confidence=self._min_presence_confidence,
                min_tracking_confidence=self._min_tracking_confidence,
            )
            self._landmarker = PoseLandmarker.create_from_options(options)
            self._is_initialised = True
            self._frame_count = 0
            logger.info("PoseEngine initialised with model: %s", self._model_path.name)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialise MediaPipe PoseLandmarker: {exc}") from exc

    def close(self) -> None:
        """Release the MediaPipe landmarker (safe to call multiple times)."""
        if self._landmarker is not None:
            self._landmarker.close()
            logger.info("PoseEngine closed after %d frames.", self._frame_count)
        self._landmarker = None
        self._is_initialised = False
        self._frame_count = 0

    # ── Core detection ────────────────────────────────────────────────

    def process_frame(
        self,
        rgb_frame: np.ndarray,
    ) -> PoseResult:
        """Detect pose landmarks in a single RGB frame.

        Args:
            rgb_frame: An RGB image as a numpy array (H, W, 3).
                       Use ``Frame.to_rgb()`` or ``preprocessing.preprocess()``
                       to convert from BGR before calling this.

        Returns:
            A ``PoseResult`` — never raises on "no person" or "partial
            detection".  Only raises if the engine is not initialised.
        """
        if not self._is_initialised or self._landmarker is None:
            raise RuntimeError("PoseEngine not initialised. Call initialise() first.")

        if not validate_frame(rgb_frame):
            logger.warning("Invalid frame passed to PoseEngine — returning empty result.")
            return PoseResult()

        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result: PoseLandmarkerResult = self._landmarker.detect(mp_image)
            self._frame_count += 1
        except Exception as exc:
            logger.error("MediaPipe detection failed: %s", exc)
            return PoseResult()

        return self._parse_result(result)

    # ── Result parsing (private) ──────────────────────────────────────

    def _parse_result(self, result: PoseLandmarkerResult) -> PoseResult:
        """Convert raw MediaPipe output to our structured PoseResult."""

        if not result.pose_landmarks or len(result.pose_landmarks) == 0:
            return PoseResult(is_detected=False)

        # Take the first (and only) detected person.
        norm_landmarks = result.pose_landmarks[0]
        world_landmarks = (
            result.pose_world_landmarks[0]
            if result.pose_world_landmarks and len(result.pose_world_landmarks) > 0
            else None
        )

        all_landmarks: dict[str, LandmarkPoint] = {}
        ergo_landmarks: dict[str, LandmarkPoint] = {}
        visible_count = 0

        for lm_enum in PoseLandmark:
            idx = lm_enum.value
            if idx >= len(norm_landmarks):
                continue

            nl = norm_landmarks[idx]
            wl = world_landmarks[idx] if world_landmarks and idx < len(world_landmarks) else None

            vis = nl.visibility if nl.visibility is not None else 0.0
            pres = nl.presence if nl.presence is not None else 0.0
            is_vis = vis >= self._visibility_threshold

            if is_vis:
                visible_count += 1

            point = LandmarkPoint(
                name=lm_enum.name,
                index=idx,
                x=nl.x,
                y=nl.y,
                z=nl.z,
                world_x=wl.x if wl else 0.0,
                world_y=wl.y if wl else 0.0,
                world_z=wl.z if wl else 0.0,
                visibility=vis,
                presence=pres,
                is_visible=is_vis,
            )

            all_landmarks[lm_enum.name] = point

            if idx in ALL_ERGONOMIC_INDICES:
                ergo_landmarks[lm_enum.name] = point

        # Determine if detection is partial (person at frame edge).
        ergo_visible = sum(1 for pt in ergo_landmarks.values() if pt.is_visible)
        ergo_total = len(ergo_landmarks)
        is_partial = (
            ergo_total > 0
            and (ergo_visible / ergo_total) < self.PARTIAL_DETECTION_THRESHOLD
        )

        avg_visibility = (
            sum(pt.visibility for pt in all_landmarks.values()) / len(all_landmarks)
            if all_landmarks else 0.0
        )

        return PoseResult(
            is_detected=True,
            landmarks=all_landmarks,
            ergonomic_landmarks=ergo_landmarks,
            visible_count=visible_count,
            total_count=len(all_landmarks),
            detection_confidence=avg_visibility,
            is_partial=is_partial,
        )


# ── Debug visualisation ──────────────────────────────────────────────────────

# Connection list for skeleton drawing (pairs of PoseLandmark indices).
_SKELETON_CONNECTIONS: list[tuple[int, int]] = [
    (lm.start, lm.end)
    for lm in PoseLandmarksConnections.POSE_LANDMARKS
]


def draw_skeleton(
    bgr_frame: np.ndarray,
    pose_result: PoseResult,
    *,
    draw_labels: bool = False,
    landmark_color: tuple[int, int, int] = (0, 255, 0),
    low_conf_color: tuple[int, int, int] = (0, 0, 255),
    connection_color: tuple[int, int, int] = (0, 200, 200),
    landmark_radius: int = 4,
    connection_thickness: int = 2,
) -> np.ndarray:
    """Draw detected pose landmarks and skeleton connections on a BGR frame.

    This is a **debug/demo** visualisation gated behind a flag — it should
    NOT be enabled during normal worker operation (PRD §20).

    Args:
        bgr_frame:            The BGR image to draw on (will be mutated).
        pose_result:          PoseResult from ``PoseEngine.process_frame()``.
        draw_labels:          If True, draw landmark names next to dots.
        landmark_color:       BGR colour for high-confidence landmarks.
        low_conf_color:       BGR colour for low-confidence landmarks.
        connection_color:     BGR colour for skeleton connection lines.
        landmark_radius:      Circle radius in pixels.
        connection_thickness: Line thickness in pixels.

    Returns:
        The same (mutated) BGR frame with overlays.
    """
    if not pose_result.is_detected:
        return bgr_frame

    h, w = bgr_frame.shape[:2]
    landmarks = pose_result.landmarks

    # Build a quick index→pixel lookup for connection drawing.
    pixel_map: dict[int, tuple[int, int]] = {}

    for lm_name, pt in landmarks.items():
        px = int(pt.x * w)
        py = int(pt.y * h)
        pixel_map[pt.index] = (px, py)

        colour = landmark_color if pt.is_visible else low_conf_color
        cv2.circle(bgr_frame, (px, py), landmark_radius, colour, -1)

        if draw_labels:
            cv2.putText(
                bgr_frame,
                lm_name,
                (px + 5, py - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.3,
                colour,
                1,
            )

    # Draw connections.
    for start_idx, end_idx in _SKELETON_CONNECTIONS:
        if start_idx in pixel_map and end_idx in pixel_map:
            cv2.line(
                bgr_frame,
                pixel_map[start_idx],
                pixel_map[end_idx],
                connection_color,
                connection_thickness,
            )

    return bgr_frame
