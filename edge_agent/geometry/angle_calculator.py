"""
Geometry Engine — Joint Angle Calculator.

Converts 2D/3D body landmarks into ergonomic posture parameters using
standard vector mathematics (dot product, norm, trigonometric angles)
implemented in NumPy.

Architecture & Privacy Guarantees
---------------------------------
- PURE MATH MODULE: depends only on NumPy and the standard library.
  Zero imports from ergonomics/, vision/, camera/, or any I/O.
- LOW CONFIDENCE HANDLING: if any landmark required for a joint angle
  is missing or marked low-confidence (is_visible=False), that angle
  returns None — NEVER a fabricated or estimated number.
- TEMPORAL SMOOTHING: implements Exponential Moving Average (EMA)
  smoothing per joint angle to eliminate single-frame noise/jitter
  before angles are passed downstream to scoring engines.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


# ── Posture Parameters Data Structure ─────────────────────────────────────────

@dataclass
class PostureParameters:
    """Computed posture measurements for a single frame.

    All angles are expressed in degrees [0.0, 180.0].
    If any joint's landmarks are missing or low-confidence, that angle is None.

    Attributes:
        neck_angle:           Neck flexion relative to trunk (0° = aligned with torso).
        trunk_angle:          Trunk inclination relative to vertical (0° = upright).
        shoulder_angle:       Primary/dominant upper-arm elevation (0° = arm hanging down).
        elbow_angle:          Primary/dominant elbow flexion (0° = straight arm, 90° = right-angle).
        wrist_angle:          Primary/dominant wrist deviation from forearm line (0° = neutral).
        hip_angle:            Primary/dominant hip angle (90° = seated upright, 180° = standing).
        knee_angle:           Primary/dominant knee angle (90° = seated upright, 180° = standing).
        left_shoulder_angle:  Left upper-arm angle.
        right_shoulder_angle: Right upper-arm angle.
        left_elbow_angle:     Left elbow flexion angle.
        right_elbow_angle:    Right elbow flexion angle.
        left_wrist_angle:     Left wrist deviation angle.
        right_wrist_angle:    Right wrist deviation angle.
        left_hip_angle:       Left hip joint angle.
        right_hip_angle:      Right hip joint angle.
        left_knee_angle:      Left knee joint angle.
        right_knee_angle:     Right knee joint angle.
        confidence:           Average visibility score of landmarks used (0.0 to 1.0).
        timestamp:            Frame timestamp in seconds.
        is_smoothed:          Whether these values have undergone temporal smoothing.
    """

    neck_angle: Optional[float] = None
    trunk_angle: Optional[float] = None

    # Consolidated / primary side angles
    shoulder_angle: Optional[float] = None
    elbow_angle: Optional[float] = None
    wrist_angle: Optional[float] = None
    hip_angle: Optional[float] = None
    knee_angle: Optional[float] = None

    # Bilateral breakdown
    left_shoulder_angle: Optional[float] = None
    right_shoulder_angle: Optional[float] = None
    left_elbow_angle: Optional[float] = None
    right_elbow_angle: Optional[float] = None
    left_wrist_angle: Optional[float] = None
    right_wrist_angle: Optional[float] = None
    left_hip_angle: Optional[float] = None
    right_hip_angle: Optional[float] = None
    left_knee_angle: Optional[float] = None
    right_knee_angle: Optional[float] = None

    confidence: float = 0.0
    timestamp: float = 0.0
    is_smoothed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return parameters as a dictionary."""
        return asdict(self)

    @property
    def available_angle_count(self) -> int:
        """Count how many core angles were successfully calculated."""
        core_angles = [
            self.neck_angle,
            self.trunk_angle,
            self.shoulder_angle,
            self.elbow_angle,
            self.wrist_angle,
            self.hip_angle,
            self.knee_angle,
        ]
        return sum(1 for a in core_angles if a is not None)

    @property
    def has_upper_body(self) -> bool:
        """True if neck, trunk, and at least one arm angle are available."""
        return (
            self.neck_angle is not None
            and self.trunk_angle is not None
            and (self.shoulder_angle is not None or self.elbow_angle is not None)
        )


# ── Core Vector Math Utilities ────────────────────────────────────────────────

def _to_vector(
    p_from: Union[np.ndarray, Sequence[float]],
    p_to: Union[np.ndarray, Sequence[float]],
) -> np.ndarray:
    """Create a vector from point p_from to point p_to."""
    return np.asarray(p_to, dtype=np.float64) - np.asarray(p_from, dtype=np.float64)


def angle_between_vectors(v1: np.ndarray, v2: np.ndarray) -> float:
    """Calculate the unsigned angle in degrees [0.0, 180.0] between two vectors.

    Uses dot product with Euclidean norms:
        cos(theta) = (v1 . v2) / (||v1|| * ||v2||)

    Handles zero-length vectors safely by returning 0.0.
    """
    v1 = np.asarray(v1, dtype=np.float64)
    v2 = np.asarray(v2, dtype=np.float64)

    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 < 1e-9 or norm2 < 1e-9:
        return 0.0

    cos_angle = np.dot(v1, v2) / (norm1 * norm2)
    # Clamp to [-1.0, 1.0] to guard against floating-point precision overflow
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def angle_at_vertex(
    p_a: Union[np.ndarray, Sequence[float]],
    p_vertex: Union[np.ndarray, Sequence[float]],
    p_b: Union[np.ndarray, Sequence[float]],
) -> float:
    """Calculate the angle at p_vertex subtended by rays (p_vertex -> p_a) and (p_vertex -> p_b).

    Returns degrees in [0.0, 180.0].
    """
    v_va = _to_vector(p_vertex, p_a)
    v_vb = _to_vector(p_vertex, p_b)
    return angle_between_vectors(v_va, v_vb)


def angle_with_vertical(
    p_origin: Union[np.ndarray, Sequence[float]],
    p_target: Union[np.ndarray, Sequence[float]],
    *,
    upward: bool = True,
) -> float:
    """Calculate the angle in degrees between vector (p_origin -> p_target) and vertical axis.

    Note on coordinate systems:
      In standard screen/image coordinates, the y-axis points DOWNWARDS.
      Therefore, upward vertical is [0, -1] (or [0, -1, 0] in 3D).
      Downward vertical is [0, 1] (or [0, 1, 0] in 3D).

    Args:
        p_origin: Start point of vector.
        p_target: End point of vector.
        upward:   If True, reference vector points UP (0, -1);
                  if False, reference vector points DOWN (0, 1).

    Returns:
        Angle in degrees [0.0, 180.0].
    """
    v = _to_vector(p_origin, p_target)
    dim = len(v)
    v_ref = np.zeros(dim, dtype=np.float64)
    v_ref[1] = -1.0 if upward else 1.0
    return angle_between_vectors(v, v_ref)


# ── Landmark Coordinate Extraction (Duck-Typing) ──────────────────────────────

def _extract_coord(
    landmarks: Mapping[str, Any],
    key: str,
    *,
    min_confidence: float = 0.5,
    use_3d: bool = False,
) -> Optional[tuple[np.ndarray, float]]:
    """Extract coordinates and confidence for a given landmark key.

    Supports multiple representations seamlessly without importing vision modules:
      - LandmarkPoint dataclass (has .x, .y, .z, .is_visible, .visibility)
      - Tuple or list of (x, y) or (x, y, z)
      - Dictionary {'x': ..., 'y': ..., 'z': ..., 'is_visible': ...}

    Keys are resolved case-insensitively (e.g. 'LEFT_SHOULDER', 'left_shoulder').

    Returns:
        (numpy_array_coord, confidence_float) or None if unavailable/low confidence.
    """
    # Lookup key directly or lowercase/uppercase
    pt = landmarks.get(key)
    if pt is None:
        pt = landmarks.get(key.upper())
    if pt is None:
        pt = landmarks.get(key.lower())
    if pt is None:
        return None

    # Duck-typing checks
    x: Optional[float] = None
    y: Optional[float] = None
    z: float = 0.0
    is_visible: bool = True
    confidence: float = 1.0

    if hasattr(pt, "x") and hasattr(pt, "y"):
        x = float(pt.x)
        y = float(pt.y)
        z = float(getattr(pt, "z", 0.0))
        is_visible = bool(getattr(pt, "is_visible", True))
        confidence = float(getattr(pt, "visibility", 1.0))
    elif isinstance(pt, dict):
        x = pt.get("x")
        y = pt.get("y")
        z = pt.get("z", 0.0)
        is_visible = pt.get("is_visible", True)
        confidence = pt.get("visibility", pt.get("confidence", 1.0))
    elif isinstance(pt, (tuple, list)) and len(pt) >= 2:
        x = float(pt[0])
        y = float(pt[1])
        z = float(pt[2]) if len(pt) > 2 else 0.0

    if x is None or y is None:
        return None

    # Reject if landmark point was explicitly flagged not visible or low confidence
    if not is_visible or confidence < min_confidence:
        return None

    coord = np.array([x, y, z] if use_3d else [x, y], dtype=np.float64)
    return coord, confidence


# ── Joint Angle Computation Functions ─────────────────────────────────────────

def compute_trunk_angle(
    hip: np.ndarray,
    shoulder: np.ndarray,
) -> float:
    """Compute trunk angle relative to vertical.

    Upright torso produces 0.0°. Forward leaning (flexion) increases the angle.
    Vector is from hip to shoulder, compared against upward vertical [0, -1].
    """
    return angle_with_vertical(hip, shoulder, upward=True)


def compute_neck_angle(
    shoulder: np.ndarray,
    head: np.ndarray,
    hip: Optional[np.ndarray] = None,
) -> float:
    """Compute neck flexion angle.

    If hip is provided, measures angle between trunk vector (hip -> shoulder)
    and neck vector (shoulder -> head). When head is aligned with the spine,
    the angle is 0.0°. Forward head posture increases the angle.

    If hip is not provided, measures neck angle relative to upward vertical.
    """
    v_neck = _to_vector(shoulder, head)
    if hip is not None:
        v_trunk = _to_vector(hip, shoulder)
        return angle_between_vectors(v_trunk, v_neck)
    return angle_with_vertical(shoulder, head, upward=True)


def compute_shoulder_angle(
    shoulder: np.ndarray,
    elbow: np.ndarray,
    hip: Optional[np.ndarray] = None,
) -> float:
    """Compute upper arm (shoulder) elevation angle.

    Angle between upper-arm vector (shoulder -> elbow) and downward trunk vector
    (shoulder -> hip) or downward vertical.
    When arm hangs down alongside torso: angle is 0.0°.
    When arm is elevated horizontally: angle is ~90.0°.
    """
    v_arm = _to_vector(shoulder, elbow)
    if hip is not None:
        v_trunk_down = _to_vector(shoulder, hip)
        return angle_between_vectors(v_trunk_down, v_arm)
    return angle_with_vertical(shoulder, elbow, upward=False)


def compute_elbow_angle(
    shoulder: np.ndarray,
    elbow: np.ndarray,
    wrist: np.ndarray,
) -> float:
    """Compute elbow flexion angle.

    Measures flexion from straight arm:
      - Straight arm (shoulder, elbow, wrist collinear) = 0.0° flexion.
      - Right-angle bend = 90.0° flexion.
      - Fully bent arm = ~140.0° - 150.0° flexion.

    Formally: 180.0° minus interior angle at elbow.
    """
    interior_angle = angle_at_vertex(shoulder, elbow, wrist)
    return max(0.0, 180.0 - interior_angle)


def compute_wrist_angle(
    elbow: np.ndarray,
    wrist: np.ndarray,
    hand: np.ndarray,
) -> float:
    """Compute wrist deviation/flexion from forearm line.

    Measures angle between forearm vector (elbow -> wrist) and hand vector
    (wrist -> hand/index).
    Straight/neutral wrist = 0.0°.
    Bent wrist = > 0.0°.
    """
    v_forearm = _to_vector(elbow, wrist)
    v_hand = _to_vector(wrist, hand)
    return angle_between_vectors(v_forearm, v_hand)


def compute_hip_angle(
    shoulder: np.ndarray,
    hip: np.ndarray,
    knee: np.ndarray,
) -> float:
    """Compute hip joint interior angle.

    Interior angle at hip between torso (hip -> shoulder) and thigh (hip -> knee):
      - Seated upright = ~90.0°.
      - Standing upright = ~180.0°.
    """
    return angle_at_vertex(shoulder, hip, knee)


def compute_knee_angle(
    hip: np.ndarray,
    knee: np.ndarray,
    ankle: np.ndarray,
) -> float:
    """Compute knee joint interior angle.

    Interior angle at knee between thigh (knee -> hip) and lower leg (knee -> ankle):
      - Seated upright with feet on floor = ~90.0°.
      - Standing upright = ~180.0°.
    """
    return angle_at_vertex(hip, knee, ankle)


# ── Temporal Angle Smoother ───────────────────────────────────────────────────

class TemporalAngleSmoother:
    """Exponential Moving Average (EMA) smoother for joint angles.

    Prevents single-frame noise/jitter from causing artificial spikes in
    ergonomic scores.

    Formula:
        smoothed[t] = alpha * current + (1 - alpha) * smoothed[t-1]

    Parameters:
        alpha: Smoothing factor in (0.0, 1.0]. Lower values yield heavier
               smoothing (less noise, slight lag); higher values respond faster.
               Default: 0.35 (optimal balance for 15-30 FPS webcams).
    """

    # Keys on PostureParameters subject to temporal smoothing
    SMOOTHED_KEYS = (
        "neck_angle",
        "trunk_angle",
        "shoulder_angle",
        "elbow_angle",
        "wrist_angle",
        "hip_angle",
        "knee_angle",
        "left_shoulder_angle",
        "right_shoulder_angle",
        "left_elbow_angle",
        "right_elbow_angle",
        "left_wrist_angle",
        "right_wrist_angle",
        "left_hip_angle",
        "right_hip_angle",
        "left_knee_angle",
        "right_knee_angle",
    )

    def __init__(self, alpha: float = 0.35) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0.0, 1.0], got {alpha}")
        self._alpha = alpha
        self._state: dict[str, float] = {}

    @property
    def alpha(self) -> float:
        return self._alpha

    @alpha.setter
    def alpha(self, val: float) -> None:
        if not 0.0 < val <= 1.0:
            raise ValueError(f"alpha must be in (0.0, 1.0], got {val}")
        self._alpha = val

    def reset(self) -> None:
        """Clear all historical state."""
        self._state.clear()

    def update(self, raw: PostureParameters) -> PostureParameters:
        """Apply EMA smoothing to a PostureParameters object.

        Returns a new PostureParameters object with smoothed values.
        Missing (None) values are NOT fabricated and clear that joint's state.
        """
        smoothed_dict = raw.to_dict()

        for k in self.SMOOTHED_KEYS:
            curr_val = getattr(raw, k)
            if curr_val is None:
                # Landmark missing: reset smoothing for this joint so stale
                # values don't leak into future frames.
                self._state.pop(k, None)
                smoothed_dict[k] = None
            else:
                prev_val = self._state.get(k)
                if prev_val is None:
                    # First observation
                    smoothed_val = curr_val
                else:
                    smoothed_val = self._alpha * curr_val + (1.0 - self._alpha) * prev_val
                self._state[k] = smoothed_val
                smoothed_dict[k] = round(smoothed_val, 2)

        smoothed_dict["is_smoothed"] = True
        return PostureParameters(**smoothed_dict)


# ── Angle Calculator ──────────────────────────────────────────────────────────

class AngleCalculator:
    """Geometry engine orchestrator.

    Converts landmark coordinates to raw joint angles and applies temporal smoothing.

    Args:
        min_confidence:  Minimum visibility threshold for a landmark to be used.
        smoothing_alpha: EMA alpha parameter in (0.0, 1.0]. Set to 1.0 to disable smoothing.
        use_3d:          Whether to use z-coordinate in vector calculations.
                         Defaults to False (2D projection) because single monocular
                         camera depth estimation has high variance for posture.
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        smoothing_alpha: float = 0.35,
        use_3d: bool = False,
    ) -> None:
        self.min_confidence = min_confidence
        self.use_3d = use_3d
        self._smoother = TemporalAngleSmoother(alpha=smoothing_alpha)

    @property
    def smoothing_alpha(self) -> float:
        return self._smoother.alpha

    @smoothing_alpha.setter
    def smoothing_alpha(self, val: float) -> None:
        self._smoother.alpha = val

    def reset(self) -> None:
        """Reset temporal smoother state."""
        self._smoother.reset()

    def calculate(
        self,
        landmarks: Mapping[str, Any],
        timestamp: float = 0.0,
    ) -> PostureParameters:
        """Calculate posture angles from a dictionary of landmarks.

        Args:
            landmarks: Mapping from landmark names to coordinate objects.
                       Supports dicts, tuples, or LandmarkPoint objects.
            timestamp: Optional timestamp for this frame.

        Returns:
            PostureParameters with smoothed joint angles.
        """
        raw = self.calculate_raw(landmarks, timestamp=timestamp)
        if self._smoother.alpha >= 1.0:
            return raw
        return self._smoother.update(raw)

    calculate_angles = calculate

    def calculate_raw(
        self,
        landmarks: Mapping[str, Any],
        timestamp: float = 0.0,
    ) -> PostureParameters:
        """Calculate raw (unsmoothed) joint angles.

        Missing or low-confidence joints are marked None.
        """
        confidences: list[float] = []

        def _get(key: str) -> Optional[np.ndarray]:
            res = _extract_coord(
                landmarks,
                key,
                min_confidence=self.min_confidence,
                use_3d=self.use_3d,
            )
            if res is not None:
                coord, conf = res
                confidences.append(conf)
                return coord
            return None

        # Extract landmark coordinates
        nose = _get("NOSE")
        left_ear = _get("LEFT_EAR")
        right_ear = _get("RIGHT_EAR")
        left_shoulder = _get("LEFT_SHOULDER")
        right_shoulder = _get("RIGHT_SHOULDER")
        left_elbow = _get("LEFT_ELBOW")
        right_elbow = _get("RIGHT_ELBOW")
        left_wrist = _get("LEFT_WRIST")
        right_wrist = _get("RIGHT_WRIST")
        left_index = _get("LEFT_INDEX")
        right_index = _get("RIGHT_INDEX")
        left_hip = _get("LEFT_HIP")
        right_hip = _get("RIGHT_HIP")
        left_knee = _get("LEFT_KNEE")
        right_knee = _get("RIGHT_KNEE")
        left_ankle = _get("LEFT_ANKLE")
        right_ankle = _get("RIGHT_ANKLE")

        # Synthesize midpoints when both sides are available
        shoulder_mid: Optional[np.ndarray] = None
        if left_shoulder is not None and right_shoulder is not None:
            shoulder_mid = (left_shoulder + right_shoulder) / 2.0

        hip_mid: Optional[np.ndarray] = None
        if left_hip is not None and right_hip is not None:
            hip_mid = (left_hip + right_hip) / 2.0

        ear_mid: Optional[np.ndarray] = None
        if left_ear is not None and right_ear is not None:
            ear_mid = (left_ear + right_ear) / 2.0
        elif nose is not None:
            ear_mid = nose

        # 1. Trunk angle (hip_mid -> shoulder_mid or best visible side)
        trunk_angle: Optional[float] = None
        if hip_mid is not None and shoulder_mid is not None:
            trunk_angle = compute_trunk_angle(hip_mid, shoulder_mid)
        elif left_hip is not None and left_shoulder is not None:
            trunk_angle = compute_trunk_angle(left_hip, left_shoulder)
        elif right_hip is not None and right_shoulder is not None:
            trunk_angle = compute_trunk_angle(right_hip, right_shoulder)

        # 2. Neck angle (shoulder_mid -> ear_mid relative to trunk)
        neck_angle: Optional[float] = None
        head_pt = ear_mid if ear_mid is not None else nose
        if head_pt is not None:
            if shoulder_mid is not None:
                neck_angle = compute_neck_angle(shoulder_mid, head_pt, hip_mid)
            elif left_shoulder is not None:
                neck_angle = compute_neck_angle(left_shoulder, head_pt, left_hip)
            elif right_shoulder is not None:
                neck_angle = compute_neck_angle(right_shoulder, head_pt, right_hip)

        # 3. Bilateral upper limbs
        left_shoulder_angle: Optional[float] = None
        if left_shoulder is not None and left_elbow is not None:
            left_shoulder_angle = compute_shoulder_angle(left_shoulder, left_elbow, left_hip)

        right_shoulder_angle: Optional[float] = None
        if right_shoulder is not None and right_elbow is not None:
            right_shoulder_angle = compute_shoulder_angle(right_shoulder, right_elbow, right_hip)

        left_elbow_angle: Optional[float] = None
        if left_shoulder is not None and left_elbow is not None and left_wrist is not None:
            left_elbow_angle = compute_elbow_angle(left_shoulder, left_elbow, left_wrist)

        right_elbow_angle: Optional[float] = None
        if right_shoulder is not None and right_elbow is not None and right_wrist is not None:
            right_elbow_angle = compute_elbow_angle(right_shoulder, right_elbow, right_wrist)

        left_wrist_angle: Optional[float] = None
        if left_elbow is not None and left_wrist is not None and left_index is not None:
            left_wrist_angle = compute_wrist_angle(left_elbow, left_wrist, left_index)

        right_wrist_angle: Optional[float] = None
        if right_elbow is not None and right_wrist is not None and right_index is not None:
            right_wrist_angle = compute_wrist_angle(right_elbow, right_wrist, right_index)

        # 4. Bilateral lower limbs
        left_hip_angle: Optional[float] = None
        if left_shoulder is not None and left_hip is not None and left_knee is not None:
            left_hip_angle = compute_hip_angle(left_shoulder, left_hip, left_knee)

        right_hip_angle: Optional[float] = None
        if right_shoulder is not None and right_hip is not None and right_knee is not None:
            right_hip_angle = compute_hip_angle(right_shoulder, right_hip, right_knee)

        left_knee_angle: Optional[float] = None
        if left_hip is not None and left_knee is not None and left_ankle is not None:
            left_knee_angle = compute_knee_angle(left_hip, left_knee, left_ankle)

        right_knee_angle: Optional[float] = None
        if right_hip is not None and right_knee is not None and right_ankle is not None:
            right_knee_angle = compute_knee_angle(right_hip, right_knee, right_ankle)

        # 5. Consolidated primary angles (average of available sides)
        def _consolidate(a: Optional[float], b: Optional[float]) -> Optional[float]:
            if a is not None and b is not None:
                return (a + b) / 2.0
            return a if a is not None else b

        shoulder_angle = _consolidate(left_shoulder_angle, right_shoulder_angle)
        elbow_angle = _consolidate(left_elbow_angle, right_elbow_angle)
        wrist_angle = _consolidate(left_wrist_angle, right_wrist_angle)
        hip_angle = _consolidate(left_hip_angle, right_hip_angle)
        knee_angle = _consolidate(left_knee_angle, right_knee_angle)

        avg_confidence = float(np.mean(confidences)) if confidences else 0.0

        # Round values to 2 decimal places for clean representation
        def _round_opt(v: Optional[float]) -> Optional[float]:
            return round(v, 2) if v is not None else None

        return PostureParameters(
            neck_angle=_round_opt(neck_angle),
            trunk_angle=_round_opt(trunk_angle),
            shoulder_angle=_round_opt(shoulder_angle),
            elbow_angle=_round_opt(elbow_angle),
            wrist_angle=_round_opt(wrist_angle),
            hip_angle=_round_opt(hip_angle),
            knee_angle=_round_opt(knee_angle),
            left_shoulder_angle=_round_opt(left_shoulder_angle),
            right_shoulder_angle=_round_opt(right_shoulder_angle),
            left_elbow_angle=_round_opt(left_elbow_angle),
            right_elbow_angle=_round_opt(right_elbow_angle),
            left_wrist_angle=_round_opt(left_wrist_angle),
            right_wrist_angle=_round_opt(right_wrist_angle),
            left_hip_angle=_round_opt(left_hip_angle),
            right_hip_angle=_round_opt(right_hip_angle),
            left_knee_angle=_round_opt(left_knee_angle),
            right_knee_angle=_round_opt(right_knee_angle),
            confidence=round(avg_confidence, 3),
            timestamp=timestamp,
            is_smoothed=False,
        )
