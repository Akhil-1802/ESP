"""Platform module facade re-exporting generator, models, and functions."""

from platform_gen.generator import PlatformGenerator
from platform_gen.island import island_platform as _island_platform
from platform_gen.models import (
    DimensionSpec,
    LabelSpec,
    PlatformResult,
    StairSpec,
    _order_outward,
)
from platform_gen.side import side_platform as _side_platform
from platform_gen.stairs import generate_stair as _generate_stair

__all__ = [
    "DimensionSpec",
    "LabelSpec",
    "PlatformGenerator",
    "PlatformResult",
    "StairSpec",
    "_generate_stair",
    "_island_platform",
    "_order_outward",
    "_side_platform",
]
