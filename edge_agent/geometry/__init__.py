"""
EdgeErgo — Geometry Module.

Provides:
  - PostureParameters: Joint angle measurements and confidence metrics.
  - AngleCalculator: Geometry engine that extracts angles from landmarks and applies EMA smoothing.
  - TemporalAngleSmoother: Exponential Moving Average smoother for angle streams.
  - Core vector math: angle_between_vectors, angle_at_vertex, angle_with_vertical.
  - Joint angle calculators: compute_trunk_angle, compute_neck_angle, etc.
"""

from edge_agent.geometry.angle_calculator import (
    AngleCalculator,
    PostureParameters,
    TemporalAngleSmoother,
    angle_at_vertex,
    angle_between_vectors,
    angle_with_vertical,
    compute_elbow_angle,
    compute_hip_angle,
    compute_knee_angle,
    compute_neck_angle,
    compute_shoulder_angle,
    compute_trunk_angle,
    compute_wrist_angle,
)

__all__ = [
    "PostureParameters",
    "AngleCalculator",
    "TemporalAngleSmoother",
    "angle_between_vectors",
    "angle_at_vertex",
    "angle_with_vertical",
    "compute_trunk_angle",
    "compute_neck_angle",
    "compute_shoulder_angle",
    "compute_elbow_angle",
    "compute_wrist_angle",
    "compute_hip_angle",
    "compute_knee_angle",
]
