"""FOB (Foot Over Bridge) generation package."""

from fob.config import FOBConfig, validate_fob_clearance
from fob.deck import (
    FOB_DEFAULT_WIDTH_M,
    FOB_LABEL,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
    axis_spans,
    build_fob_arms,
    build_fob_outline,
    calculate_fob_chainage,
    choose_label_spot,
    determine_station_edge,
    generate_fob,
    get_fob_track_position,
    track_axis_hits,
    validate_fob_conflicts,
    validate_fob_offset,
    validate_fob_span,
    write_fob_deck,
)
from fob.placement import normalize_fob_direction

__all__ = [
    "FOBConfig",
    "FOB_LABEL",
    "FOB_DEFAULT_WIDTH_M",
    "FOB_MAX_SPAN_M",
    "FOB_VERTICAL_CLEARANCE_M",
    "axis_spans",
    "build_fob_arms",
    "build_fob_outline",
    "calculate_fob_chainage",
    "choose_label_spot",
    "determine_station_edge",
    "generate_fob",
    "get_fob_track_position",
    "normalize_fob_direction",
    "track_axis_hits",
    "validate_fob_clearance",
    "validate_fob_conflicts",
    "validate_fob_offset",
    "validate_fob_span",
    "write_fob_deck",
]
