"""
Frame pre-processing utilities.

Shared pipeline for resizing, colour-space conversion, and normalisation
used by both the Pose Engine (Phase 3) and the Face Engine (Phase 5).

No frame is ever persisted or transmitted — all operations are in-memory.

Dependencies: cv2, numpy — no MediaPipe, no ergonomics, no storage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ── Colour-space enum ─────────────────────────────────────────────────────────

class ColorSpace(Enum):
    """Supported colour spaces."""
    BGR = auto()
    RGB = auto()
    GRAY = auto()


# ── Preprocessing configuration ──────────────────────────────────────────────

@dataclass(frozen=True)
class PreprocessConfig:
    """Immutable preprocessing settings.

    Attributes:
        target_width:  Desired width after resize (0 = keep original).
        target_height: Desired height after resize (0 = keep original).
        output_color:  Colour space for the output array.
        normalize:     If True, scale pixel values to [0.0, 1.0] float32.
    """
    target_width: int = 0
    target_height: int = 0
    output_color: ColorSpace = ColorSpace.RGB
    normalize: bool = False


# ── Default configs for common use cases ──────────────────────────────────────

#: Config for MediaPipe models (RGB, no normalisation — MediaPipe does its own).
MEDIAPIPE_PREPROCESSING = PreprocessConfig(
    target_width=0,       # keep camera-configured resolution
    target_height=0,
    output_color=ColorSpace.RGB,
    normalize=False,
)


# ── Core preprocessing functions ──────────────────────────────────────────────

def convert_color(
    image: np.ndarray,
    source: ColorSpace,
    target: ColorSpace,
) -> np.ndarray:
    """Convert an image between supported colour spaces.

    Returns:
        A new array in the target colour space.  The original is not mutated.
    """
    if source == target:
        return image

    conversion_map = {
        (ColorSpace.BGR, ColorSpace.RGB): cv2.COLOR_BGR2RGB,
        (ColorSpace.RGB, ColorSpace.BGR): cv2.COLOR_RGB2BGR,
        (ColorSpace.BGR, ColorSpace.GRAY): cv2.COLOR_BGR2GRAY,
        (ColorSpace.RGB, ColorSpace.GRAY): cv2.COLOR_RGB2GRAY,
    }

    key = (source, target)
    if key not in conversion_map:
        raise ValueError(f"Unsupported colour conversion: {source.name} → {target.name}")

    return cv2.cvtColor(image, conversion_map[key])


def resize_frame(
    image: np.ndarray,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    """Resize an image to the target dimensions.

    Uses INTER_AREA for downscaling (highest quality) and INTER_LINEAR
    for upscaling.  Returns the original if dimensions already match.
    """
    h, w = image.shape[:2]
    if (target_width <= 0 or target_height <= 0) or (w == target_width and h == target_height):
        return image

    interpolation = (
        cv2.INTER_AREA
        if (target_width < w or target_height < h)
        else cv2.INTER_LINEAR
    )
    return cv2.resize(image, (target_width, target_height), interpolation=interpolation)


def normalize_frame(image: np.ndarray) -> np.ndarray:
    """Scale pixel values from [0, 255] uint8 to [0.0, 1.0] float32."""
    return image.astype(np.float32) / 255.0


def preprocess(
    image: np.ndarray,
    config: PreprocessConfig = MEDIAPIPE_PREPROCESSING,
    source_color: ColorSpace = ColorSpace.BGR,
) -> np.ndarray:
    """Run the full preprocessing pipeline.

    Steps (in order):
      1. Resize (if target dimensions are set).
      2. Colour-space conversion (if needed).
      3. Normalisation (if requested).

    Args:
        image:        Input frame as a NumPy array.
        config:       Preprocessing settings.
        source_color: Colour space of the input image.

    Returns:
        Preprocessed frame ready for inference (new array, original untouched).
    """
    result = image

    # 1. Resize
    result = resize_frame(result, config.target_width, config.target_height)

    # 2. Colour conversion
    result = convert_color(result, source_color, config.output_color)

    # 3. Normalise
    if config.normalize:
        result = normalize_frame(result)

    return result


# ── Validation helpers ────────────────────────────────────────────────────────

def validate_frame(image: np.ndarray) -> bool:
    """Quick sanity check that an image array is usable.

    Returns True if the array is a non-empty 3-channel (or greyscale) image.
    """
    if image is None or not isinstance(image, np.ndarray):
        return False
    if image.size == 0:
        return False
    if image.ndim not in (2, 3):
        return False
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        return False
    return True


def estimate_brightness(image: np.ndarray) -> float:
    """Estimate mean brightness (0.0–255.0) of a frame.

    Useful for warning the user about very dark or very bright conditions
    that degrade pose detection quality.
    """
    gray = convert_color(image, ColorSpace.BGR, ColorSpace.GRAY) if image.ndim == 3 else image
    return float(np.mean(gray))
