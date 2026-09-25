"""Turnout geometry module (backward compatibility shim).

Canonical module is now :mod:`track.crossover.turnout`.
"""

from track.crossover.turnout import (
    TurnoutGeometry,
    TurnoutResult,
    _sample_arc,
    _sample_spline,
    _sample_tangent,
    generate_turnout,
    transform_turnout_to_global,
    turnout_angle_f_rad,
    turnout_ratio_n,
)

__all__ = [
    "TurnoutGeometry",
    "TurnoutResult",
    "_sample_arc",
    "_sample_spline",
    "_sample_tangent",
    "generate_turnout",
    "transform_turnout_to_global",
    "turnout_angle_f_rad",
    "turnout_ratio_n",
]
