"""
Camera module tests.

Tests are split into two groups:
  1. Unit tests that mock cv2.VideoCapture (always runnable, no camera needed).
  2. A live bench-test (guarded by ``--run-camera``) that opens a real camera,
     shows a preview window, and prints FPS.

Run unit tests:       pytest tests/edge/test_camera.py -v
Run live bench-test:  pytest tests/edge/test_camera.py -v --run-camera
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest

from edge_agent.camera.camera import (
    Camera,
    CameraError,
    CameraErrorKind,
    Frame,
    list_available_cameras,
)


# ── pytest CLI flag for live camera tests ─────────────────────────────────────

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-camera",
        action="store_true",
        default=False,
        help="Run live camera tests (requires a connected camera).",
    )


@pytest.fixture
def run_camera(request: pytest.FixtureRequest) -> bool:
    return request.config.getoption("--run-camera")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fake_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a dummy BGR frame (blue gradient)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = 200  # blue channel
    return frame


# ── Frame class unit tests ────────────────────────────────────────────────────

class TestFrame:
    """Tests for the Frame wrapper (pure NumPy, no camera needed)."""

    def test_dimensions(self) -> None:
        img = _make_fake_frame(320, 240)
        frame = Frame(image=img, timestamp=1.0, index=1)
        assert frame.width == 320
        assert frame.height == 240

    def test_to_rgb_converts_bgr(self) -> None:
        """A pure-blue BGR frame should become pure-blue in the R channel
        after BGR→RGB conversion? No — BGR blue = (255,0,0) becomes
        RGB (0,0,255).  Let's verify the channel swap."""
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        img[:, :, 0] = 255  # BGR blue
        frame = Frame(image=img, timestamp=0.0, index=0)

        rgb = frame.to_rgb()
        # After BGR→RGB, channel 0 (now R) should be 0, channel 2 (now B) = 255.
        assert rgb[0, 0, 0] == 0    # R
        assert rgb[0, 0, 2] == 255  # B

    def test_to_rgb_does_not_mutate_original(self) -> None:
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        img[:, :, 0] = 100
        frame = Frame(image=img, timestamp=0.0, index=0)

        _ = frame.to_rgb()
        assert frame.image[0, 0, 0] == 100  # original unchanged

    def test_resized_noop_when_same_size(self) -> None:
        img = _make_fake_frame(640, 480)
        frame = Frame(image=img, timestamp=0.0, index=0)
        result = frame.resized(640, 480)
        # Should return the same array (identity — no copy).
        assert result is img

    def test_resized_downscale(self) -> None:
        img = _make_fake_frame(640, 480)
        frame = Frame(image=img, timestamp=0.0, index=0)
        result = frame.resized(320, 240)
        assert result.shape == (240, 320, 3)

    def test_resized_rgb(self) -> None:
        img = _make_fake_frame(640, 480)
        frame = Frame(image=img, timestamp=0.0, index=0)
        result = frame.resized_rgb(320, 240)
        assert result.shape == (240, 320, 3)


# ── Camera class unit tests (mocked VideoCapture) ────────────────────────────

class TestCameraMocked:
    """Tests using a mocked cv2.VideoCapture — no real camera needed."""

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_open_success(self, mock_vc_cls: MagicMock) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0  # pretend native res
        mock_vc_cls.return_value = mock_cap

        cam = Camera(camera_index=0, frame_width=640, frame_height=480)
        cam.open()

        assert cam.is_open is True
        mock_vc_cls.assert_called_once()
        cam.release()
        assert cam.is_open is False

    @patch("edge_agent.camera.camera.list_available_cameras", return_value=[])
    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_open_not_found(self, mock_vc_cls: MagicMock, _mock_list: MagicMock) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_cls.return_value = mock_cap

        cam = Camera(camera_index=5)
        with pytest.raises(CameraError) as exc_info:
            cam.open()

        assert exc_info.value.kind == CameraErrorKind.NOT_FOUND

    @patch("edge_agent.camera.camera.list_available_cameras", return_value=[5])
    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_open_permission_denied(self, mock_vc_cls: MagicMock, _mock_list: MagicMock) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_cls.return_value = mock_cap

        cam = Camera(camera_index=5)
        with pytest.raises(CameraError) as exc_info:
            cam.open()

        assert exc_info.value.kind == CameraErrorKind.PERMISSION_DENIED

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_open_already_open(self, mock_vc_cls: MagicMock) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        mock_vc_cls.return_value = mock_cap

        cam = Camera()
        cam.open()
        with pytest.raises(CameraError) as exc_info:
            cam.open()

        assert exc_info.value.kind == CameraErrorKind.ALREADY_OPEN
        cam.release()

    def test_read_frame_not_open(self) -> None:
        cam = Camera()
        with pytest.raises(CameraError) as exc_info:
            cam.read_frame()

        assert exc_info.value.kind == CameraErrorKind.NOT_OPEN

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_read_frame_success(self, mock_vc_cls: MagicMock) -> None:
        fake_img = _make_fake_frame(640, 480)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        mock_cap.read.return_value = (True, fake_img)
        mock_vc_cls.return_value = mock_cap

        cam = Camera(frame_width=640, frame_height=480)
        cam.open()
        frame = cam.read_frame()

        assert isinstance(frame, Frame)
        assert frame.width == 640
        assert frame.height == 480
        assert frame.index == 1
        assert cam.frame_count == 1
        cam.release()

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_read_frame_with_resize(self, mock_vc_cls: MagicMock) -> None:
        """Camera native res is 1920x1080, but we request 640x480."""
        fake_img = _make_fake_frame(1920, 1080)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 1920.0
        mock_cap.read.return_value = (True, fake_img)
        mock_vc_cls.return_value = mock_cap

        cam = Camera(frame_width=640, frame_height=480)
        cam.open()
        frame = cam.read_frame()

        assert frame.width == 640
        assert frame.height == 480
        cam.release()

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_read_frame_disconnected(self, mock_vc_cls: MagicMock) -> None:
        mock_cap = MagicMock()
        # First isOpened call (during open) returns True, then False after read fails.
        mock_cap.isOpened.side_effect = [True, True, False]
        mock_cap.get.return_value = 640.0
        mock_cap.read.return_value = (False, None)
        mock_vc_cls.return_value = mock_cap

        cam = Camera()
        cam.open()
        with pytest.raises(CameraError) as exc_info:
            cam.read_frame()

        assert exc_info.value.kind == CameraErrorKind.DISCONNECTED

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_read_frame_transient_failure(self, mock_vc_cls: MagicMock) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        mock_cap.read.return_value = (False, None)
        mock_vc_cls.return_value = mock_cap

        cam = Camera()
        cam.open()
        with pytest.raises(CameraError) as exc_info:
            cam.read_frame()

        assert exc_info.value.kind == CameraErrorKind.READ_FAILURE
        cam.release()

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_stream_yields_frames(self, mock_vc_cls: MagicMock) -> None:
        fake_img = _make_fake_frame()

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        mock_cap.read.return_value = (True, fake_img.copy())
        mock_vc_cls.return_value = mock_cap

        cam = Camera()
        cam.open()

        frames = list(cam.stream(max_frames=5))
        assert len(frames) == 5
        assert all(isinstance(f, Frame) for f in frames)
        cam.release()

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_context_manager(self, mock_vc_cls: MagicMock) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        mock_vc_cls.return_value = mock_cap

        with Camera() as cam:
            assert cam.is_open is True
        # After exiting the context, the camera should be released.
        assert cam.is_open is False

    def test_release_safe_when_not_open(self) -> None:
        """release() should not raise even if open() was never called."""
        cam = Camera()
        cam.release()  # should be a no-op, not a crash


# ── Camera discovery test (mocked) ───────────────────────────────────────────

class TestCameraDiscovery:

    @patch("edge_agent.camera.camera.cv2.VideoCapture")
    def test_list_available_cameras(self, mock_vc_cls: MagicMock) -> None:
        """Simulate indices 0 and 2 being available."""
        def _make_cap(idx: int, _backend: int = 0) -> MagicMock:
            cap = MagicMock()
            cap.isOpened.return_value = idx in (0, 2)
            return cap

        mock_vc_cls.side_effect = _make_cap
        result = list_available_cameras(max_index=4)
        assert result == [0, 2]


# ── Live camera bench-test ────────────────────────────────────────────────────

class TestCameraLive:
    """Live camera tests — only run with ``--run-camera``."""

    @pytest.mark.skipif(True, reason="Use --run-camera to enable")
    def test_live_preview(self, run_camera: bool) -> None:
        """Open a real camera, capture for ~3 seconds, print FPS."""
        if not run_camera:
            pytest.skip("Live camera test not requested.")

        import cv2 as cv

        available = list_available_cameras()
        if not available:
            pytest.skip("No camera available on this machine.")

        cam = Camera(
            camera_index=available[0],
            frame_width=640,
            frame_height=480,
            capture_fps=30,
        )
        cam.open()

        start = time.monotonic()
        count = 0
        duration_sec = 3.0

        try:
            for frame in cam.stream():
                cv.imshow("EdgeErgo Camera Test", frame.image)
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
        print(f"\n[Camera Bench] {count} frames in {elapsed:.2f}s = {fps:.1f} FPS")
        assert count > 0, "Should have captured at least 1 frame."
