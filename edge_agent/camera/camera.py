"""
Camera capture module.

Provides a thread-safe Camera class wrapping OpenCV's VideoCapture.
Frames are captured as NumPy arrays, optionally resized and colour-
converted, and NEVER written to disk or transmitted over the network.

Dependencies: cv2, numpy — no MediaPipe, no ergonomics, no storage.
"""

from __future__ import annotations

import logging
import time
from enum import Enum, auto
from typing import Generator

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ── Error types ───────────────────────────────────────────────────────────────

class CameraErrorKind(Enum):
    """Classification of camera failures."""

    NOT_FOUND = auto()          # No camera at the given index
    PERMISSION_DENIED = auto()  # OS blocked camera access
    DISCONNECTED = auto()       # Camera was open but vanished mid-run
    READ_FAILURE = auto()       # Frame grab returned False
    ALREADY_OPEN = auto()       # open() called while already streaming
    NOT_OPEN = auto()           # read/close called before open()


class CameraError(Exception):
    """Typed, non-crashing camera error.

    Always carries a ``kind`` so callers can branch on the failure mode
    without parsing the message string.
    """

    def __init__(self, kind: CameraErrorKind, message: str) -> None:
        self.kind = kind
        super().__init__(f"[{kind.name}] {message}")


# ── Frame dataclass ───────────────────────────────────────────────────────────

class Frame:
    """Lightweight wrapper around a captured image array.

    Attributes:
        image:     The raw BGR numpy array (never written to disk).
        timestamp: Monotonic capture time (seconds).
        index:     Sequential frame counter since the camera was opened.
    """

    __slots__ = ("image", "timestamp", "index", "_rgb")

    def __init__(self, image: np.ndarray, timestamp: float, index: int) -> None:
        self.image = image
        self.timestamp = timestamp
        self.index = index
        self._rgb: Optional[np.ndarray] = None

    @property
    def height(self) -> int:
        return self.image.shape[0]

    @property
    def width(self) -> int:
        return self.image.shape[1]

    def to_rgb(self) -> np.ndarray:
        """Return the frame as an RGB array (MediaPipe expects RGB).

        Caches the converted array to eliminate redundant allocations across
        vision models within the same processing cycle.
        """
        if self._rgb is None:
            self._rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        return self._rgb

    def resized(self, width: int, height: int) -> np.ndarray:
        """Return a resized copy of the BGR image.

        Uses INTER_AREA for downscaling (best quality) and INTER_LINEAR
        for upscaling.
        """
        if width == self.width and height == self.height:
            return self.image

        interpolation = (
            cv2.INTER_AREA
            if (width < self.width or height < self.height)
            else cv2.INTER_LINEAR
        )
        return cv2.resize(self.image, (width, height), interpolation=interpolation)

    def resized_rgb(self, width: int, height: int) -> np.ndarray:
        """Convenience: resize then convert BGR→RGB in one call."""
        resized_bgr = self.resized(width, height)
        return cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)


# ── Camera discovery ──────────────────────────────────────────────────────────

def list_available_cameras(max_index: int = 8) -> list[int]:
    """Probe camera indices 0..max_index and return those that open.

    This does a quick open-then-close for each index, so it may take
    a moment on systems with many virtual devices.
    """
    available: list[int] = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
        if cap.isOpened():
            available.append(idx)
            cap.release()
        else:
            cap.release()
    logger.info("Available cameras: %s", available)
    return available


# ── Camera class ──────────────────────────────────────────────────────────────

class Camera:
    """OpenCV camera wrapper with configurable resolution and error handling.

    Typical usage::

        cam = Camera(camera_index=0, frame_width=640, frame_height=480)
        cam.open()
        try:
            frame = cam.read_frame()
            rgb = frame.to_rgb()
            # ... pass rgb to MediaPipe ...
        finally:
            cam.release()

    Or as a context manager::

        with Camera(camera_index=0) as cam:
            for frame in cam.stream():
                process(frame)

    Privacy invariant
    -----------------
    This class NEVER writes frames to disk.  ``Frame`` objects live
    exclusively in memory and are discarded after processing.
    """

    def __init__(
        self,
        camera_index: int = 0,
        frame_width: int = 640,
        frame_height: int = 480,
        capture_fps: int = 10,
    ) -> None:
        self._camera_index = camera_index
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._capture_fps = capture_fps

        self._cap: cv2.VideoCapture | None = None
        self._frame_counter: int = 0
        self._is_open: bool = False

        logger.info(
            "Camera configured: index=%d, resolution=%dx%d, fps=%d",
            camera_index, frame_width, frame_height, capture_fps,
        )

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self) -> Camera:
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        """True if the camera device is currently opened and readable."""
        return self._is_open and self._cap is not None and self._cap.isOpened()

    @property
    def camera_index(self) -> int:
        return self._camera_index

    @property
    def frame_width(self) -> int:
        return self._frame_width

    @property
    def frame_height(self) -> int:
        return self._frame_height

    @property
    def frame_count(self) -> int:
        """Total frames captured since open()."""
        return self._frame_counter

    # ── Lifecycle ─────────────────────────────────────────────────────

    def open(self) -> None:
        """Open the camera device.

        Raises:
            CameraError(ALREADY_OPEN)  if the camera is already streaming.
            CameraError(NOT_FOUND)     if no camera exists at the index.
            CameraError(PERMISSION_DENIED) if the OS blocks access.
        """
        if self._is_open:
            raise CameraError(
                CameraErrorKind.ALREADY_OPEN,
                f"Camera {self._camera_index} is already open.",
            )

        logger.info("Opening camera %d ...", self._camera_index)
        cap = cv2.VideoCapture(self._camera_index, cv2.CAP_ANY)

        if not cap.isOpened():
            cap.release()
            # Distinguish "not found" from "permission denied" as best we
            # can — OpenCV doesn't expose the OS error, so we probe the
            # index list as a heuristic.
            available = list_available_cameras()
            if self._camera_index in available:
                raise CameraError(
                    CameraErrorKind.PERMISSION_DENIED,
                    f"Camera {self._camera_index} exists but could not be opened "
                    f"(possible permission issue). Available: {available}",
                )
            raise CameraError(
                CameraErrorKind.NOT_FOUND,
                f"No camera found at index {self._camera_index}. "
                f"Available: {available}",
            )

        # Request the desired capture properties.  The driver may ignore
        # these — actual resolution is read back after setting.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_height)
        if self._capture_fps > 0:
            cap.set(cv2.CAP_PROP_FPS, self._capture_fps)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)

        logger.info(
            "Camera %d opened — native resolution %dx%d @ %.1f fps "
            "(requested %dx%d @ %d fps; will software-resize if needed)",
            self._camera_index, actual_w, actual_h, actual_fps,
            self._frame_width, self._frame_height, self._capture_fps,
        )

        self._cap = cap
        self._frame_counter = 0
        self._is_open = True

    def release(self) -> None:
        """Release the camera device (safe to call multiple times)."""
        if self._cap is not None:
            self._cap.release()
            logger.info(
                "Camera %d released after %d frames.",
                self._camera_index, self._frame_counter,
            )
        self._cap = None
        self._is_open = False
        self._frame_counter = 0

    # ── Frame capture ─────────────────────────────────────────────────

    def read_frame(self) -> Frame:
        """Capture a single frame, resize it, and return a Frame object.

        The returned Frame contains a BGR image at the configured
        resolution (``frame_width × frame_height``).  Use
        ``frame.to_rgb()`` to convert for MediaPipe.

        Raises:
            CameraError(NOT_OPEN)       if open() hasn't been called.
            CameraError(DISCONNECTED)   if the device vanished mid-run.
            CameraError(READ_FAILURE)   if the grab returned an empty frame.
        """
        if not self.is_open:
            raise CameraError(
                CameraErrorKind.NOT_OPEN,
                "Call open() before reading frames.",
            )

        assert self._cap is not None  # guaranteed by is_open check

        ret, raw_frame = self._cap.read()
        capture_time = time.monotonic()

        if not ret or raw_frame is None or raw_frame.size == 0:
            # Check whether the camera is still physically connected.
            if not self._cap.isOpened():
                self._is_open = False
                raise CameraError(
                    CameraErrorKind.DISCONNECTED,
                    f"Camera {self._camera_index} was disconnected.",
                )
            raise CameraError(
                CameraErrorKind.READ_FAILURE,
                f"Failed to read frame from camera {self._camera_index}.",
            )

        # Software-resize to the target resolution if the native
        # resolution differs.
        h, w = raw_frame.shape[:2]
        if w != self._frame_width or h != self._frame_height:
            interpolation = (
                cv2.INTER_AREA
                if (self._frame_width < w or self._frame_height < h)
                else cv2.INTER_LINEAR
            )
            raw_frame = cv2.resize(
                raw_frame,
                (self._frame_width, self._frame_height),
                interpolation=interpolation,
            )

        self._frame_counter += 1

        return Frame(
            image=raw_frame,
            timestamp=capture_time,
            index=self._frame_counter,
        )

    def read_frame_rgb(self) -> tuple[np.ndarray, float]:
        """Convenience: capture → resize → BGR-to-RGB in one call.

        Returns:
            (rgb_array, timestamp) tuple.
        """
        frame = self.read_frame()
        return frame.to_rgb(), frame.timestamp

    # ── Generator / streaming ─────────────────────────────────────────

    def stream(self, max_frames: int = 0) -> Generator[Frame, None, None]:
        """Yield frames continuously until the camera is released.

        Args:
            max_frames: Stop after this many frames (0 = unlimited).

        Yields:
            Frame objects.  The generator catches READ_FAILURE errors
            and logs them as warnings rather than terminating; it stops
            only on DISCONNECTED or when ``release()`` is called.
        """
        count = 0
        while self.is_open:
            try:
                yield self.read_frame()
                count += 1
                if max_frames > 0 and count >= max_frames:
                    logger.info("Stream stopped: reached max_frames=%d.", max_frames)
                    return
            except CameraError as exc:
                if exc.kind == CameraErrorKind.DISCONNECTED:
                    logger.error("Stream stopped: %s", exc)
                    return
                # Transient read failure — log and retry next iteration.
                logger.warning("Transient frame error: %s", exc)


# ── Factory helper ────────────────────────────────────────────────────────────

def create_camera_from_config(
    camera_index: int | None = None,
    frame_width: int | None = None,
    frame_height: int | None = None,
    capture_fps: int | None = None,
) -> Camera:
    """Create a Camera with explicit overrides or sensible defaults.

    This is a convenience for callers who don't have a full EdgeConfig
    object handy (e.g. test scripts).  The main agent should construct
    Camera directly from config values.
    """
    return Camera(
        camera_index=camera_index if camera_index is not None else 0,
        frame_width=frame_width if frame_width is not None else 640,
        frame_height=frame_height if frame_height is not None else 480,
        capture_fps=capture_fps if capture_fps is not None else 10,
    )
