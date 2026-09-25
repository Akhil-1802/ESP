"""Shared foundation imports and utilities for CLI modules."""

from __future__ import annotations

from common.constants import (
    DEFAULT_FOB_OFFSET_M,
    DEFAULT_FOB_WIDTH_M,
    LOOP_CROSSOVER_DISTANCE_M,
    LOOP_HALF_LENGTH_M,
    MIN_TRACK_SPACING_M,
)
from common.geometry import polyline_length
from common.prompts import (
    UserAbort,
    ask,
    ask_choice,
    ask_count,
    ask_nonnegative,
    ask_positive,
    ask_track_spacing,
)

__all__ = [
    "DEFAULT_FOB_OFFSET_M",
    "DEFAULT_FOB_WIDTH_M",
    "LOOP_CROSSOVER_DISTANCE_M",
    "LOOP_HALF_LENGTH_M",
    "MIN_TRACK_SPACING_M",
    "UserAbort",
    "ask",
    "ask_choice",
    "ask_count",
    "ask_nonnegative",
    "ask_positive",
    "ask_track_spacing",
    "polyline_length",
]
