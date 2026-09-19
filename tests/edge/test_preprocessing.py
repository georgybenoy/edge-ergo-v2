"""
Tests for vision/preprocessing.py.

All tests are pure unit tests — no camera or MediaPipe needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from edge_agent.vision.preprocessing import (
    ColorSpace,
    PreprocessConfig,
    MEDIAPIPE_PREPROCESSING,
    convert_color,
    estimate_brightness,
    normalize_frame,
    preprocess,
    resize_frame,
    validate_frame,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bgr_frame(w: int = 640, h: int = 480, blue: int = 200) -> np.ndarray:
    """Create a dummy BGR frame."""
    f = np.zeros((h, w, 3), dtype=np.uint8)
    f[:, :, 0] = blue
    return f


# ── convert_color ─────────────────────────────────────────────────────────────

class TestConvertColor:

    def test_bgr_to_rgb_swaps_channels(self) -> None:
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        img[:, :, 0] = 255  # BGR blue → should become channel 2 in RGB
        result = convert_color(img, ColorSpace.BGR, ColorSpace.RGB)
        assert result[0, 0, 2] == 255
        assert result[0, 0, 0] == 0

    def test_noop_same_space(self) -> None:
        img = _bgr_frame(4, 4)
        result = convert_color(img, ColorSpace.BGR, ColorSpace.BGR)
        assert result is img  # same object, no copy

    def test_bgr_to_gray(self) -> None:
        img = _bgr_frame(4, 4)
        result = convert_color(img, ColorSpace.BGR, ColorSpace.GRAY)
        assert result.ndim == 2

    def test_unsupported_raises(self) -> None:
        img = _bgr_frame(4, 4)
        with pytest.raises(ValueError, match="Unsupported"):
            convert_color(img, ColorSpace.GRAY, ColorSpace.RGB)


# ── resize_frame ──────────────────────────────────────────────────────────────

class TestResizeFrame:

    def test_downscale(self) -> None:
        img = _bgr_frame(640, 480)
        result = resize_frame(img, 320, 240)
        assert result.shape == (240, 320, 3)

    def test_noop_same_size(self) -> None:
        img = _bgr_frame(640, 480)
        result = resize_frame(img, 640, 480)
        assert result is img

    def test_noop_zero_target(self) -> None:
        img = _bgr_frame(640, 480)
        result = resize_frame(img, 0, 0)
        assert result is img


# ── normalize_frame ───────────────────────────────────────────────────────────

class TestNormalizeFrame:

    def test_output_range(self) -> None:
        img = np.array([[[0, 128, 255]]], dtype=np.uint8)
        result = normalize_frame(img)
        assert result.dtype == np.float32
        np.testing.assert_almost_equal(result[0, 0, 0], 0.0)
        np.testing.assert_almost_equal(result[0, 0, 2], 1.0)


# ── validate_frame ────────────────────────────────────────────────────────────

class TestValidateFrame:

    def test_valid_bgr(self) -> None:
        assert validate_frame(_bgr_frame()) is True

    def test_none(self) -> None:
        assert validate_frame(None) is False

    def test_empty(self) -> None:
        assert validate_frame(np.array([])) is False

    def test_wrong_dims(self) -> None:
        assert validate_frame(np.zeros((5,), dtype=np.uint8)) is False

    def test_gray_valid(self) -> None:
        assert validate_frame(np.zeros((10, 10), dtype=np.uint8)) is True


# ── preprocess (full pipeline) ────────────────────────────────────────────────

class TestPreprocess:

    def test_mediapipe_default_produces_rgb(self) -> None:
        img = _bgr_frame(640, 480)
        result = preprocess(img, MEDIAPIPE_PREPROCESSING, source_color=ColorSpace.BGR)
        # Should be RGB — verify by checking the first pixel channel swap.
        assert result.shape == (480, 640, 3)
        # Original blue channel (200) should now be in channel 2 (blue in RGB).
        assert result[0, 0, 2] == 200

    def test_with_resize_and_normalize(self) -> None:
        cfg = PreprocessConfig(
            target_width=320,
            target_height=240,
            output_color=ColorSpace.RGB,
            normalize=True,
        )
        img = _bgr_frame(640, 480)
        result = preprocess(img, cfg, source_color=ColorSpace.BGR)
        assert result.shape == (240, 320, 3)
        assert result.dtype == np.float32


# ── estimate_brightness ───────────────────────────────────────────────────────

class TestEstimateBrightness:

    def test_black_is_zero(self) -> None:
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        assert estimate_brightness(img) == pytest.approx(0.0)

    def test_white_is_255(self) -> None:
        img = np.full((10, 10, 3), 255, dtype=np.uint8)
        val = estimate_brightness(img)
        assert val == pytest.approx(255.0)
