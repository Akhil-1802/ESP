"""Track DXF annotation routines.

Handles track name labels and T.C (track centre) spacing annotations.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from common.constants import TEXT_CLEARANCE_M
from common.dxf import (
    _inflate,
    _register_box,
    draw_arrow_dimension as _draw_arrow_dimension,
    ensure_number_style as _ensure_num,
    ensure_text_style as _ensure_text_style,
    estimate_text_aabb as _aabb,
    resolve_text_insert as _resolve_text_insert,
)
from common.geometry import (
    nearest_point_on_alignment as _nearest_point,
    point_at_chainage as _chainage_point,
    polyline_length as _polyline_length,
    readable_angle_deg as _readable,
)

from .splines import _find_track_anchor, _measure_track_clearance_at

Point = Tuple[float, float]

__all__ = [
    "_add_track_label",
    "_tc_text_centered",
    "_add_tc_annotation",
    "_add_all_tc_annotations",
]


def _add_track_label(
    doc,
    label: str,
    points: Sequence[Point],
    layer: str,
    color: int = 1,
    height: float = 1.0,
    align_x: float | None = None,
) -> None:
    """Add a small TEXT annotation on the clear outer side of the track midpoint / station datum."""
    if len(points) < 2:
        return
    if not doc.layers.get(layer):
        doc.layers.add(layer, color=color)

    anchor, tx, ty = _find_track_anchor(doc, points, align_x=align_x)
    length = math.hypot(tx, ty) or 1.0
    ux, uy = tx / length, ty / length
    ang = 0.0
    try:
        ang = _readable(math.degrees(math.atan2(ty, tx)))
    except Exception:
        ang = 0.0

    if ux >= 0:
        up_nx, up_ny = -uy, ux
    else:
        up_nx, up_ny = uy, -ux
    down_nx, down_ny = -up_nx, -up_ny

    d_above, d_below = _measure_track_clearance_at(doc, anchor[0], anchor[1])
    if d_above >= d_below:
        gap = d_above
        normal = (up_nx, up_ny)
    else:
        gap = d_below
        normal = (down_nx, down_ny)

    offset = 1.5
    if math.isfinite(gap) and gap < 5.5:
        offset = max(1.0, min(offset, gap / 2.0))

    text_pos = (anchor[0] + normal[0] * offset, anchor[1] + normal[1] * offset)
    text_pos = _resolve_text_insert(doc, label, height, ang, text_pos, anchor="middle-center")
    doc.modelspace().add_text(
        label,
        height=height,
        dxfattribs={
            "layer": layer,
            "color": color,
            "style": _ensure_text_style(doc),
            "rotation": ang,
            "insert": (text_pos[0], text_pos[1], 0),
            "halign": 1,
            "valign": 2,
            "align_point": (text_pos[0], text_pos[1], 0),
        },
    )


def _tc_text_centered(
    doc,
    mid: Point,
    track_angle_deg: float,
    label: str,
    layer: str,
    color: int,
    height: float,
):
    """Place one T.C label centred between tracks, parallel to the tracks."""
    ang = _readable(float(track_angle_deg))
    style = _ensure_num(doc)
    msp = doc.modelspace()
    try:
        entity = msp.add_text(
            label,
            height=height,
            dxfattribs={
                "layer": layer,
                "color": color,
                "style": style,
                "rotation": ang,
                "insert": (mid[0], mid[1], 0),
                "halign": 1,  # CENTER
                "valign": 2,  # MIDDLE
                "align_point": (mid[0], mid[1], 0),
            },
        )
    except Exception:
        width_factor = 0.55
        est_half = len(label) * float(height) * width_factor / 2.0
        rad = math.radians(ang)
        tx, ty = math.cos(rad), math.sin(rad)
        insert = (mid[0] - tx * est_half, mid[1] - ty * est_half)
        entity = msp.add_text(
            label,
            height=height,
            dxfattribs={
                "layer": layer,
                "color": color,
                "style": style,
                "rotation": ang,
                "insert": (insert[0], insert[1], 0),
            },
        )
    try:
        box = _inflate(
            _aabb(label, float(height), ang, (mid[0], mid[1]), "middle-center", 0.55),
            TEXT_CLEARANCE_M,
        )
        _register_box(doc, box)
    except Exception:
        pass
    return entity


def _add_tc_annotation(
    doc,
    points_a: Sequence[Point],
    points_b: Sequence[Point],
    spacing: float,
    layer: str = "TRACK_CENTERS",
    color: int = 1,
    height: float = 0.8,
) -> None:
    """Draw T.C track-centre labels between two tracks."""
    if len(points_a) < 2 or len(points_b) < 2:
        return
    if not doc.layers.get(layer):
        doc.layers.add(layer, color=color)

    total_a = _polyline_length(points_a)
    if total_a < 1e-9:
        return
    for frac in (0.4, 0.6):
        try:
            station = _chainage_point(
                points_a, min(max(frac * total_a, 0.0), total_a)
            )
        except Exception:
            continue
        try:
            pb = _nearest_point(points_b, station.point).point
        except Exception:
            continue
        pa = station.point
        _draw_arrow_dimension(
            doc,
            pa,
            pb,
            dim_offset=0.0,
            text=f"T.C={spacing:g}M",
            layer=layer,
            color=color,
            height=height,
        )


def _add_all_tc_annotations(
    doc,
    tracks: dict,
    layer: str = "TRACK_CENTERS",
    color: int = 1,
    height: float = 0.8,
    fracs: Sequence[float] = (0.4, 0.6),
) -> None:
    """Annotate every adjacent track gap with a T.C label."""
    if not tracks or "MAIN_LINE" not in tracks:
        return
    main_pts = list(tracks.get("MAIN_LINE") or [])
    if len(main_pts) < 2:
        return
    if layer not in doc.layers:
        try:
            doc.layers.add(layer, color=color)
        except Exception:
            pass
    total_main = _polyline_length(main_pts)
    if total_main < 1e-9:
        return
    names = [n for n, pts in tracks.items() if pts is not None and len(list(pts)) >= 2]
    if len(names) < 2:
        return

    if fracs == (0.4, 0.6) and total_main > 150.0:
        min_reach = 0.0
        max_reach = total_main
        for name in names:
            if name == "MAIN_LINE":
                continue
            pts = list(tracks[name])
            try:
                ch_start = _nearest_point(main_pts, pts[0]).chainage
                ch_end = _nearest_point(main_pts, pts[-1]).chainage
                min_reach = max(min_reach, min(ch_start, ch_end))
                max_reach = min(max_reach, max(ch_start, ch_end))
            except Exception:
                pass
        span_len = max_reach - min_reach
        if span_len > 120.0:
            turnout_margin = min(35.0, span_len * 0.1)
            p_start = min_reach + turnout_margin
            p_end = max_reach - turnout_margin
            center_ch = (p_start + p_end) / 2.0
            ch_left = max(p_start, min(center_ch - 150.0, p_start + (center_ch - p_start) * 0.35))
            ch_right = min(p_end, max(center_ch + 150.0, p_end - (p_end - center_ch) * 0.35))
            target_chainages = [ch_left, ch_right]
        else:
            dist = max(150.0, total_main * 0.22)
            target_chainages = [
                max(total_main * 0.05, total_main * 0.5 - dist),
                min(total_main * 0.95, total_main * 0.5 + dist),
            ]
    else:
        target_chainages = [min(max(float(frac) * total_main, 0.0), total_main) for frac in fracs]

    for chainage in target_chainages:
        try:
            station = _chainage_point(main_pts, chainage)
        except Exception:
            continue
        tx, ty = station.tangent
        nx, ny = -ty, tx
        offsets: list[tuple[float, str]] = []
        for name in names:
            pts = list(tracks[name])
            if name == "MAIN_LINE":
                offsets.append((0.0, name))
                continue
            try:
                proj = _nearest_point(pts, station.point).point
            except Exception:
                continue
            vx, vy = proj[0] - station.point[0], proj[1] - station.point[1]
            if abs(vx * tx + vy * ty) > 5.0:
                continue
            cross = tx * vy - ty * vx
            offsets.append((float(cross), name))
        if len(offsets) < 2:
            continue
        offsets.sort(key=lambda item: item[0])
        for (off_a, _na), (off_b, _nb) in zip(offsets, offsets[1:]):
            gap = abs(off_b - off_a)
            if gap < 0.1 or gap > 50.0:
                continue
            p_a = (station.point[0] + nx * off_a, station.point[1] + ny * off_a)
            p_b = (station.point[0] + nx * off_b, station.point[1] + ny * off_b)
            _draw_arrow_dimension(
                doc,
                p_a,
                p_b,
                dim_offset=0.0,
                text=f"T.C={gap:g}M",
                layer=layer,
                color=color,
                height=height,
            )
