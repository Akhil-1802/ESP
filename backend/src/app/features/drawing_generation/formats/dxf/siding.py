"""DXF annotations for a siding's dead end and clear standing length."""
from __future__ import annotations

import math

from ...domain.geometry.operations import Point
from ...domain.track.siding import _unit
from .primitives import add_polyline as _add_polyline

SIDING_DEAD_END_BAR_M = 2.0
SIDING_DEAD_END_CAP_M = 1.2


def draw_siding_dead_end(
    doc,
    tip: Point,
    tangent: Point,
    layer: str,
    color: int = 1,
    standing_length_m: float | None = None,
) -> None:
    """Dead-end marker at the siding tip: bar + caps facing outward + DE and CSL."""
    tx, ty = _unit(tangent)
    nx, ny = -ty, tx
    half, cap = SIDING_DEAD_END_BAR_M, SIDING_DEAD_END_CAP_M
    top = (tip[0] + nx * half, tip[1] + ny * half)
    bot = (tip[0] - nx * half, tip[1] - ny * half)
    _add_polyline(
        doc,
        [
            (top[0] + tx * cap, top[1] + ty * cap),
            top,
            bot,
            (bot[0] + tx * cap, bot[1] + ty * cap),
        ],
        layer,
        color,
        close=False,
    )
    try:
        from .tracks.markers import _dead_end_text as _de_text
    except ImportError:
        _de_text = None

    if _de_text is not None:
        try:
            _de_text(doc, tip, tangent, tangent, layer, color, 1.0, "DE")
        except Exception:
            pass
    else:
        try:
            from ...domain.geometry.operations import readable_angle_deg as _readable
            from .styles import ensure_text_style as _style

            ang = _readable(math.degrees(math.atan2(ty, tx)))
            pos = (tip[0] + tx * 3.5, tip[1] + ty * 3.5)
            if layer not in doc.layers:
                try:
                    doc.layers.add(layer, color=color)
                except Exception:
                    pass
            doc.modelspace().add_text(
                "DE",
                height=1.0,
                dxfattribs={
                    "layer": layer,
                    "color": color,
                    "style": _style(doc),
                    "rotation": ang,
                    "insert": (pos[0], pos[1], 0),
                    "halign": 1,
                    "valign": 2,
                    "align_point": (pos[0], pos[1], 0),
                },
            )
        except Exception:
            pass

    if standing_length_m is not None and standing_length_m > 0:
        try:
            from ...domain.geometry.operations import readable_angle_deg as _readable
            from .styles import ensure_text_style as _style

            ang = _readable(math.degrees(math.atan2(ty, tx)))
            csl_label = f"CSL={standing_length_m:g}M"
            csl_back = min(
                15.0, standing_length_m * 0.3 if standing_length_m else 15.0
            )
            csl_back = max(csl_back, 8.0)
            if tx >= 0:
                down_nx, down_ny = ty, -tx
            else:
                down_nx, down_ny = -ty, tx
            offset_under = 1.2
            csl_pos = (
                tip[0] - tx * csl_back + down_nx * offset_under,
                tip[1] - ty * csl_back + down_ny * offset_under,
            )
            if layer not in doc.layers:
                try:
                    doc.layers.add(layer, color=color)
                except Exception:
                    pass
            doc.modelspace().add_text(
                csl_label,
                height=1.0,
                dxfattribs={
                    "layer": layer,
                    "color": color,
                    "style": _style(doc),
                    "rotation": ang,
                    "insert": (csl_pos[0], csl_pos[1], 0),
                    "halign": 1,
                    "valign": 3,
                    "align_point": (csl_pos[0], csl_pos[1], 0),
                },
            )
        except Exception:
            pass
