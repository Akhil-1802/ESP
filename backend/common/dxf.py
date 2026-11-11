"""Canonical ezdxf drawing facade.

Re-exports styles, text handling, and primitives from dedicated submodules.
"""

from __future__ import annotations

from common.dxf_primitives import (
    add_arrow_head,
    add_filled_disk,
    add_line,
    add_polyline,
    add_spline,
    add_text,
    draw_arrow_dimension,
)
from common.dxf_styles import (
    ensure_bold_text_style,
    ensure_custom_linetype_5,
    ensure_dashed_linetype,
    ensure_dotted_linetype,
    ensure_layer,
    ensure_number_style,
    ensure_text_style,
    force_all_red,
)
from common.dxf_text import (
    _inflate,
    _register_box,
    estimate_text_aabb,
    resolve_text_insert,
)

__all__ = [
    "add_arrow_head",
    "add_filled_disk",
    "add_line",
    "add_polyline",
    "add_spline",
    "add_text",
    "draw_arrow_dimension",
    "ensure_bold_text_style",
    "ensure_custom_linetype_5",
    "ensure_dashed_linetype",
    "ensure_dotted_linetype",
    "ensure_layer",
    "ensure_number_style",
    "ensure_text_style",
    "estimate_text_aabb",
    "force_all_red",
    "resolve_text_insert",
]
