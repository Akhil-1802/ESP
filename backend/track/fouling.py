"""Fouling Mark (FM) drawing and facade."""

from __future__ import annotations

import math
from typing import Sequence

from common.constants import TEXT_CLEARANCE_M as _clr
from common.dxf import (
    _inflate as _inf,
    _register_box as _reg,
    ensure_layer as _ensure_layer,
    ensure_text_style as _style,
    estimate_text_aabb as _aabb,
)
from common.geometry import readable_angle_deg as _readable
from track.fouling_detect import (
    FM_CHAINAGE_TOL_M,
    FM_CLASS_EPS_M,
    FM_COLOR,
    FM_DEDUPE_M,
    FM_DETECT_MARGIN_M,
    FM_DISK_RADIUS_M,
    FM_LAYER,
    FM_SCAN_STEP_M,
    FM_SEARCH_MARGIN_M,
    FM_SRJ_CLEARANCE_M,
    FM_STEM_M,
    FM_TEXT_HEIGHT_M,
    FM_TICK_HALF_M,
    FM_TICK_LINEWEIGHT,
    FM_TICK_WIDTH_M,
    FM_TRI_SIDE_M,
    FoulingMark,
    collect_fouling_marks,
    fouling_threshold_m,
)


def draw_fouling_marks(doc, marks: Sequence[FoulingMark]) -> int:
    """Draw every FM as: bold centre tick + ``FM`` beside it, both floating."""
    if not marks:
        return 0
    _ensure_layer(doc, FM_LAYER, FM_COLOR)
    FM_SIDE_ALONG_M: float = 1.6
    drawn = 0
    for mark in marks:
        try:
            point = mark.display_point or mark.point
            tangent = mark.display_tangent or mark.tangent
            tx, ty = tangent
            norm = math.hypot(tx, ty) or 1.0
            tx, ty = tx / norm, ty / norm
            other = getattr(mark, "other_point", None) or point
            px, py = float(point[0]), float(point[1])
            ox, oy = float(other[0]), float(other[1])
            spacing = math.hypot(px - ox, py - oy)
            try:
                sm = float(getattr(mark, "spacing_m", 0.0) or 0.0)
                if math.isfinite(sm) and sm > 0:
                    spacing = max(spacing, 0.0) or sm
                    spacing = float(sm) if sm > 1e-9 else spacing
            except (TypeError, ValueError):
                pass
            geom_dist = math.hypot(px - ox, py - oy)
            clr = min(1.8, spacing * 0.35) if spacing > 1e-3 else 1.8
            # Displace strictly along the track normal toward the conflicting track (zero along-track shift)
            nx, ny = -ty, tx
            dot = (ox - px) * nx + (oy - py) * ny
            inward_nx = nx if dot >= 0.0 else -nx
            inward_ny = ny if dot >= 0.0 else -ny
            mx = px + inward_nx * clr
            my = py + inward_ny * clr
            half = 0.5
            msp = doc.modelspace()
            qx, qy = -ty, tx
            p1 = (mx + qx * half, my + qy * half)
            p2 = (mx - qx * half, my - qy * half)
            try:
                ent = msp.add_lwpolyline(
                    [(p1[0], p1[1]), (p2[0], p2[1])],
                    dxfattribs={
                        "layer": FM_LAYER,
                        "color": FM_COLOR,
                        "lineweight": int(FM_TICK_LINEWEIGHT),
                    },
                )
                try:
                    ent.dxf.const_width = float(FM_TICK_WIDTH_M)
                except Exception:
                    pass
            except Exception:
                msp.add_line(
                    p1,
                    p2,
                    dxfattribs={
                        "layer": FM_LAYER,
                        "color": FM_COLOR,
                        "lineweight": int(FM_TICK_LINEWEIGHT),
                    },
                )
            mid = (mx + tx * FM_SIDE_ALONG_M, my + ty * FM_SIDE_ALONG_M)
            angle = math.degrees(math.atan2(ty, tx))
            if _readable is not None:
                angle = _readable(angle)
            else:
                while angle > 90.0:
                    angle -= 180.0
                while angle < -90.0:
                    angle += 180.0
            style = _style(doc) if _style is not None else "Standard"
            try:
                msp.add_text(
                    "FM",
                    height=float(FM_TEXT_HEIGHT_M),
                    dxfattribs={
                        "layer": FM_LAYER,
                        "color": FM_COLOR,
                        "style": style,
                        "rotation": angle,
                        "insert": (mid[0], mid[1], 0),
                        "halign": 1,
                        "valign": 2,
                        "align_point": (mid[0], mid[1], 0),
                    },
                )
            except Exception:
                msp.add_text(
                    "FM",
                    height=float(FM_TEXT_HEIGHT_M),
                    dxfattribs={
                        "layer": FM_LAYER,
                        "color": FM_COLOR,
                        "style": style,
                        "rotation": angle,
                        "insert": (mid[0], mid[1], 0),
                    },
                )
            try:
                box = _inf(
                    _aabb(
                        "FM",
                        float(FM_TEXT_HEIGHT_M),
                        angle,
                        (mid[0], mid[1]),
                        "middle-center",
                        0.7,
                    ),
                    _clr,
                )
                _reg(doc, box)
            except Exception:
                pass
            drawn += 1
        except Exception:
            continue
    return drawn


__all__ = [
    "FM_CHAINAGE_TOL_M",
    "FM_CLASS_EPS_M",
    "FM_COLOR",
    "FM_DEDUPE_M",
    "FM_DETECT_MARGIN_M",
    "FM_DISK_RADIUS_M",
    "FM_LAYER",
    "FM_SCAN_STEP_M",
    "FM_SEARCH_MARGIN_M",
    "FM_SRJ_CLEARANCE_M",
    "FM_STEM_M",
    "FM_TEXT_HEIGHT_M",
    "FM_TICK_HALF_M",
    "FM_TICK_LINEWEIGHT",
    "FM_TICK_WIDTH_M",
    "FM_TRI_SIDE_M",
    "FoulingMark",
    "collect_fouling_marks",
    "draw_fouling_marks",
    "fouling_threshold_m",
]
