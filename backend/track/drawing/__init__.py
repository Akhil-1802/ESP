"""Track drawing package: splines, markers, annotations, and track rendering."""

from .annotations import (
    _add_all_tc_annotations,
    _add_tc_annotation,
    _add_track_label,
    _tc_text_centered,
)
from .markers import (
    _annotate_overrun,
    _arrow_head,
    _dead_end_marker,
    _dead_end_text,
    _draw_direction_mark,
    _draw_srj_post,
    _overrun_cal_label,
    draw_srj_overrun_stub,
)
from .splines import (
    _add_spline,
    _find_track_anchor,
    _line_center,
    _measure_track_clearance_at,
    _segment_mid,
    _unit_vec,
)
from .tracks import clear_drawing_layers, draw_tracks, track_drawing_layers

__all__ = [
    "_add_all_tc_annotations",
    "_add_spline",
    "_add_tc_annotation",
    "_add_track_label",
    "_annotate_overrun",
    "_arrow_head",
    "_dead_end_marker",
    "_dead_end_text",
    "_draw_direction_mark",
    "_draw_srj_post",
    "_find_track_anchor",
    "_line_center",
    "_measure_track_clearance_at",
    "_overrun_cal_label",
    "_segment_mid",
    "_tc_text_centered",
    "_unit_vec",
    "clear_drawing_layers",
    "draw_srj_overrun_stub",
    "draw_tracks",
    "track_drawing_layers",
]
