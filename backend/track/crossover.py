"""Crossover module (backward compatibility facade).

Canonical implementations are now under :mod:`track.crossover`:
- :mod:`track.crossover.core`
- :mod:`track.crossover.loops`
- :mod:`track.crossover.reverse_curve`
- :mod:`track.crossover.turnout`
"""

from track.crossover.core import (
    CrossoverGeometry,
    STANDARD_F_DIAG_TOLERANCE_DEG,
    STANDARD_MAX_VERTEX_GAP_M,
    STANDARD_PARALLEL_TOLERANCE_DEG,
    _build_normal_crossover,
    _build_reverse_curve_crossover,
    build_standard_crossover,
    calculate_crossover,
    centerline_distance_mm,
    generate_crossover_coordinates,
    local_track_spacing_mm,
    standard_crossover_lengths,
)
from track.crossover.loops import (
    LoopGeometry,
    _build_crossover_curve,
    generate_loop,
)
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
    "CrossoverGeometry",
    "LoopGeometry",
    "STANDARD_F_DIAG_TOLERANCE_DEG",
    "STANDARD_MAX_VERTEX_GAP_M",
    "STANDARD_PARALLEL_TOLERANCE_DEG",
    "TurnoutGeometry",
    "TurnoutResult",
    "_build_crossover_curve",
    "_build_normal_crossover",
    "_build_reverse_curve_crossover",
    "_sample_arc",
    "_sample_spline",
    "_sample_tangent",
    "build_standard_crossover",
    "calculate_crossover",
    "centerline_distance_mm",
    "generate_crossover_coordinates",
    "generate_loop",
    "generate_turnout",
    "local_track_spacing_mm",
    "standard_crossover_lengths",
    "transform_turnout_to_global",
    "turnout_angle_f_rad",
    "turnout_ratio_n",
]
