"""Brownfield railway design package.

Provides structured tools for adding and managing MAIN_LINES with explicit reference tracks:
- BrownfieldMainLineSpec: Specification requiring reference_track for every added main line.
- BrownfieldMainLineBuilder: Dependency resolution and tangent-normal perpendicular offset generation.
- BrownfieldGenerator: Orchestration and DXF rendering for Brownfield layouts.
- BrownfieldLayout: Container holding resolved tracks and their reference relationships.
"""

from .crossover import (
    BrownfieldCrossoverBuilder,
    BrownfieldCrossoverResult,
    BrownfieldCrossoverSpec,
    build_brownfield_crossover,
)
from .geometry import compute_perpendicular_offset
from .generator import BrownfieldGenerator
from .main_lines import BrownfieldMainLineBuilder
from .models import (
    BrownfieldLayout,
    BrownfieldMainLineSpec,
    BrownfieldTrack,
    Point,
    TrackRelationship,
)
from .validation import validate_and_sort_main_lines

__all__ = [
    "Point",
    "BrownfieldMainLineSpec",
    "BrownfieldTrack",
    "TrackRelationship",
    "BrownfieldLayout",
    "BrownfieldMainLineBuilder",
    "BrownfieldGenerator",
    "BrownfieldCrossoverSpec",
    "BrownfieldCrossoverResult",
    "BrownfieldCrossoverBuilder",
    "build_brownfield_crossover",
    "compute_perpendicular_offset",
    "validate_and_sort_main_lines",
]
