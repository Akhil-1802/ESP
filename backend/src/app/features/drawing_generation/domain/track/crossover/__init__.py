"""Crossover engineering, planning, geometry, and validation package."""

from .conflicts import (
    RESTRICT_TOL_M,
    crossover_track_intervals,
    find_restriction_conflicts,
    platforms_to_restricted_regions,
    stations_to_restricted_regions,
)
from .core import (
    STANDARD_F_DIAG_TOLERANCE_DEG,
    STANDARD_MAX_VERTEX_GAP_M,
    STANDARD_PARALLEL_TOLERANCE_DEG,
    CrossoverGeometry,
    _build_reverse_curve_crossover,
    build_standard_crossover,
    calculate_crossover,
    centerline_distance_mm,
    standard_crossover_lengths,
)
from .defaults import compute_default_chainages, format_debug_block, requests_from_specs
from .footprints import footprints_overlap, is_main_track, polyline_self_intersects
from .loops import LoopGeometry, generate_loop
from .models import (
    AdjacentSpacingCheck,
    CrossoverRequest,
    CrossoverResult,
    CrossoverValidationReport,
    FootprintCheck,
    RestrictedConflict,
    RestrictedRegion,
)
from .normalize import (
    is_auto_chainage,
    normalize_direction,
    normalize_placement,
    normalize_position_mode,
)
from .planner import CrossoverPlanner
from .turnout import (
    TurnoutGeometry,
    TurnoutResult,
    _sample_arc,
    _sample_spline,
    _sample_tangent,
    generate_turnout,
    transform_turnout_to_global,
    turnout_ratio_n,
)
from .validator import CrossoverConstraintValidator

__all__ = [
    "AdjacentSpacingCheck",
    "CrossoverConstraintValidator",
    "CrossoverGeometry",
    "CrossoverPlanner",
    "CrossoverRequest",
    "CrossoverResult",
    "CrossoverValidationReport",
    "FootprintCheck",
    "LoopGeometry",
    "RESTRICT_TOL_M",
    "RestrictedConflict",
    "RestrictedRegion",
    "STANDARD_F_DIAG_TOLERANCE_DEG",
    "STANDARD_MAX_VERTEX_GAP_M",
    "STANDARD_PARALLEL_TOLERANCE_DEG",
    "TurnoutGeometry",
    "TurnoutResult",
    "_build_reverse_curve_crossover",
    "_sample_arc",
    "_sample_spline",
    "_sample_tangent",
    "build_standard_crossover",
    "calculate_crossover",
    "centerline_distance_mm",
    "compute_default_chainages",
    "crossover_track_intervals",
    "find_restriction_conflicts",
    "footprints_overlap",
    "format_debug_block",
    "generate_loop",
    "generate_turnout",
    "is_auto_chainage",
    "is_main_track",
    "normalize_direction",
    "normalize_placement",
    "normalize_position_mode",
    "platforms_to_restricted_regions",
    "polyline_self_intersects",
    "requests_from_specs",
    "standard_crossover_lengths",
    "stations_to_restricted_regions",
    "transform_turnout_to_global",
    "turnout_ratio_n",
]
