"""Track DXF marker and post drawing routines.

Handles arrowheads, SRJ posts, direction marks, dead-end markers,
and overrun stubs/annotations.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from common.constants import TEXT_CLEARANCE_M
from common.dxf import (
    _inflate,
    _register_box,
    add_arrow_head as _common_arrow_head,
    add_polyline as _common_polyline,
    ensure_text_style as _ensure_text_style,
    estimate_text_aabb as _aabb,
    resolve_text_insert as _resolve_text_insert,
)
from common.geometry import point_at_chainage, polyline_length as _polyline_length, readable_angle_deg as _readable
from track.overrun_metadata import attach_overrun

from .splines import _line_center, _segment_mid, _unit_vec

Point = Tuple[float, float]

__all__ = [
    "_arrow_head",
    "_draw_srj_post",
    "_draw_direction_mark",
    "_dead_end_text",
    "_dead_end_marker",
    "_overrun_cal_label",
    "draw_srj_overrun_stub",
    "_annotate_overrun",
]


def _arrow_head(
    doc,
    tip: Point,
    direction: Point,
    layer: str,
    color: int = 1,
    al: float = 2.0,
    aw: float = 0.7,
) -> None:
    """Filled triangular arrowhead with its tip at `tip` pointing `direction`."""
    _common_arrow_head(doc, tip, direction, layer, color, length=al, half_width=aw)


def _draw_srj_post(doc, tip: Point, travel: Point, outward_left: bool) -> None:
    """Signal post + `SRJ` text at a LOOP-line non-extended tip.

    Post (2m stem + solid 1m disk) stands on the tip toward the outward
    side; `SRJ` sits behind the post along travel direction.
    """
    layer = "SRJ"
    if layer not in doc.layers:
        doc.layers.add(layer, color=1)
    tx, ty = travel
    n = math.hypot(tx, ty) or 1.0
    tx, ty = tx / n, ty / n
    ox, oy = (-ty, tx) if outward_left else (ty, -tx)

    stem, radius = 2.0, 1.0
    doc.modelspace().add_line(
        (tip[0], tip[1]),
        (tip[0] + ox * stem, tip[1] + oy * stem),
        dxfattribs={"layer": layer, "color": 1},
    )
    cx, cy = tip[0] + ox * (stem + radius), tip[1] + oy * (stem + radius)
    disk = [
        (
            cx + radius * math.cos(2.0 * math.pi * i / 16),
            cy + radius * math.sin(2.0 * math.pi * i / 16),
        )
        for i in range(16)
    ]
    doc.modelspace().add_lwpolyline(
        disk, close=True, dxfattribs={"layer": layer, "color": 1},
    )
    try:
        hatch = doc.modelspace().add_hatch(dxfattribs={"layer": layer, "color": 1})
        hatch.set_solid_fill(color=1)
        hatch.paths.add_polyline_path(disk, is_closed=True)
    except Exception:
        pass

    ang = math.degrees(math.atan2(ty, tx))
    while ang > 90.0:
        ang -= 180.0
    while ang < -90.0:
        ang += 180.0
    srj_insert = _resolve_text_insert(
        doc, "SRJ", 1.0, ang, (cx - tx * 3.5, cy - ty * 3.5, 0)
    )
    doc.modelspace().add_text(
        "SRJ",
        height=1.0,
        dxfattribs={
            "layer": layer,
            "color": 1,
            "style": _ensure_text_style(doc),
            "rotation": ang,
            "insert": (srj_insert[0], srj_insert[1], 0),
        },
    )


def _draw_direction_mark(
    doc,
    points: Sequence[Point],
    text: str,
    two_way: bool,
    sense: int = 1,
) -> None:
    """UP/DN direction mark at the centre of a MAIN line.

    A ~16m shaft along the track with filled arrowhead(s): both ends for
    `two_way` ("UP/DN"), otherwise one head toward +chainage (`sense > 0`,
    "UP") or -chainage ("DN"). Label sits centred above the shaft.
    Convention: UP = increasing chainage, DN = decreasing.
    """
    layer = "DIRECTION"
    if layer not in doc.layers:
        doc.layers.add(layer, color=1)
    centre, tangent = _line_center(points)
    tx, ty = tangent
    n = math.hypot(tx, ty) or 1.0
    tx, ty = tx / n, ty / n
    nx, ny = -ty, tx
    half = 8.0
    ahead = (centre[0] + tx * half, centre[1] + ty * half)
    behind = (centre[0] - tx * half, centre[1] - ty * half)
    doc.modelspace().add_line(behind, ahead, dxfattribs={"layer": layer, "color": 1})
    if two_way or sense > 0:
        _arrow_head(doc, ahead, (tx, ty), layer, 1)
    if two_way or sense < 0:
        _arrow_head(doc, behind, (-tx, -ty), layer, 1)
    ang = math.degrees(math.atan2(ty, tx))
    while ang > 90.0:
        ang -= 180.0
    while ang < -90.0:
        ang += 180.0
    shift = len(text) * 1.0 * 0.7 / 2.0
    dir_insert = (
        centre[0] - tx * shift + nx * 2.0,
        centre[1] - ty * shift + ny * 2.0,
        0,
    )
    doc.modelspace().add_text(
        text,
        height=1.0,
        dxfattribs={
            "layer": layer,
            "color": 1,
            "style": _ensure_text_style(doc),
            "rotation": ang,
            "insert": (dir_insert[0], dir_insert[1], 0),
        },
    )


def _dead_end_text(
    doc,
    tip: Point,
    tangent: Sequence[float],
    exterior: Sequence[float],
    layer: str,
    color: int = 1,
    height: float = 1.0,
    label: str = "DE",
) -> None:
    """`DE` label just beyond a dead-end tip (overrun / stub / siding).

    Placed on the outer side of the ``]`` marker (``tip + exterior * 4m``),
    rotated parallel to the track tangent so every dead end shares the
    same alignment. Drawn middle-centre and deterministic.
    """
    tx, ty = _unit_vec(tangent)
    ix, iy = _unit_vec(exterior)
    ang = _readable(math.degrees(math.atan2(ty, tx)))
    if layer not in doc.layers:
        try:
            doc.layers.add(layer, color=color)
        except Exception:
            pass
    pos = (tip[0] + ix * 4.0, tip[1] + iy * 4.0)
    try:
        doc.modelspace().add_text(
            label,
            height=height,
            dxfattribs={
                "layer": layer,
                "color": color,
                "style": _ensure_text_style(doc),
                "rotation": ang,
                "insert": (pos[0], pos[1], 0),
                "halign": 1,  # CENTER
                "valign": 2,  # MIDDLE
                "align_point": (pos[0], pos[1], 0),
            },
        )
    except Exception:
        doc.modelspace().add_text(
            label,
            height=height,
            dxfattribs={
                "layer": layer,
                "color": color,
                "style": _ensure_text_style(doc),
                "rotation": ang,
                "insert": (pos[0], pos[1], 0),
            },
        )
    try:
        box = _inflate(
            _aabb(label, float(height), ang, (pos[0], pos[1]), "middle-center", 0.7),
            TEXT_CLEARANCE_M,
        )
        _register_box(doc, box)
    except Exception:
        pass


def _dead_end_marker(
    doc,
    tip: Point,
    tangent: Sequence[float],
    exterior: Sequence[float],
    layer: str,
    bar_half: float = 2.0,
    cap: float = 1.2,
) -> None:
    """Dead-end marker: bar + caps facing ``exterior`` (overrun language).

    Also draws the ``DE`` tag just beyond the tip so every dead end
    reads with its marker + text together.
    """
    tx, ty = _unit_vec(tangent)
    nx, ny = -ty, tx
    ix, iy = _unit_vec(exterior)
    top = (tip[0] + nx * bar_half, tip[1] + ny * bar_half)
    bot = (tip[0] - nx * bar_half, tip[1] - ny * bar_half)
    _common_polyline(
        doc,
        [
            (top[0] + ix * cap, top[1] + iy * cap),
            top,
            bot,
            (bot[0] + ix * cap, bot[1] + iy * cap),
        ],
        layer,
        1,
        close=False,
    )
    _dead_end_text(doc, tip, tangent, exterior, layer, 1, 1.0, "DE")


def _overrun_cal_label(
    doc,
    mid: Point,
    tangent: Sequence[float],
    outward_left: bool,
    length: float,
    layer: str = "OVER_RUN",
):
    """`OVER RUN LINE, CAL=xx.xx` text at ``mid`` along ``tangent``."""
    tx, ty = _unit_vec(tangent)
    nx, ny = (-ty, tx) if outward_left else (ty, -tx)
    ang = math.degrees(math.atan2(ty, tx))
    while ang > 90.0:
        ang -= 180.0
    while ang < -90.0:
        ang += 180.0
    label = f"OVER RUN LINE, CAL={length:.2f}(SRJ TO DE)"
    shift = len(label) * 1.0 * 0.7 / 2.0
    ov_insert = _resolve_text_insert(
        doc,
        label,
        1.0,
        ang,
        (
            mid[0] - tx * shift + nx * 2.5,
            mid[1] - ty * shift + ny * 2.5,
            0,
        ),
    )
    entity = doc.modelspace().add_text(
        label,
        height=1.0,
        dxfattribs={
            "layer": layer,
            "color": 1,
            "style": _ensure_text_style(doc),
            "rotation": ang,
            "insert": (ov_insert[0], ov_insert[1], 0),
        },
    )
    return entity


def draw_srj_overrun_stub(
    doc,
    stub_points: Sequence[Point],
    at_start: bool,
    outward_left: bool,
    layer: str = "OVER_RUN",
    track_name: str | None = None,
) -> None:
    """Draw one SRJ cut-off stub as an OVER RUN LINE.

    The stub centreline goes on ``layer``, a dead-end marker caps the
    outer tip (facing away from the running line), and a CAL label
    carries the stub's true length. Stubs shorter than ~1 mm are
    skipped. ``at_start`` selects which tip is the outer (dead) end.
    """
    pts = [(float(p[0]), float(p[1])) for p in stub_points]
    if len(pts) < 2:
        return
    if _polyline_length(pts) < 1e-9:
        return
    if layer not in doc.layers:
        doc.layers.add(layer, color=1)
    _common_polyline(doc, pts, layer, 1, close=False)
    if at_start:
        tip = pts[0]
        tangent = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        exterior = (-tangent[0], -tangent[1])
    else:
        tip = pts[-1]
        tangent = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
        exterior = (tangent[0], tangent[1])
    _dead_end_marker(doc, tip, tangent, exterior, layer)
    mid, mtan = _line_center(pts)
    label = _overrun_cal_label(doc, mid, mtan, outward_left, _polyline_length(pts), layer)
    if track_name is not None:
        attach_overrun(label, track_name, pts[-1] if at_start else pts[0],
                       tip, _polyline_length(pts), at_start)


def _annotate_overrun(doc, loop, loop_points: Sequence[Point], c1: float, c2: float, eff_c1: float, eff_c2: float) -> None:
    """Draw dead-end markers + `OVER RUN LINE, CAL=xx.xx` texts.

    Only the extended tip(s) get a marker: START extension -> marker at
    the first point (caps face away from the line, -chainage); END
    extension -> mirrored marker at the last point (caps face +chainage).
    Each overrun segment is labelled at its midpoint with its own length.
    """
    ext_start = getattr(loop, "extend_start_m", 0.0) or 0.0
    ext_end = getattr(loop, "extend_end_m", 0.0) or 0.0
    if ext_start == 0 and ext_end == 0:
        return
    layer = "OVER_RUN"
    if layer not in doc.layers:
        doc.layers.add(layer, color=1)

    outward_left = loop.side.upper() == "LEFT"
    jobs = []
    if ext_start > 0:
        p0, t0 = loop_points[0], (
            loop_points[1][0] - loop_points[0][0],
            loop_points[1][1] - loop_points[0][1],
        )
        jobs.append((p0, t0, (-t0[0], -t0[1]), eff_c1, c1, ext_start, True))
    if ext_end > 0:
        pn, tn = loop_points[-1], (
            loop_points[-1][0] - loop_points[-2][0],
            loop_points[-1][1] - loop_points[-2][1],
        )
        jobs.append((pn, tn, (tn[0], tn[1]), c2, eff_c2, ext_end, False))

    for tip, tangent, exterior, main_a, main_b, ext_len, is_start in jobs:
        _dead_end_marker(doc, tip, tangent, exterior, layer)
        mid, mtan = _segment_mid(loop_points, eff_c1, main_a, main_b)
        label = _overrun_cal_label(doc, mid, mtan, outward_left, ext_len, layer)
        local_anchor = ext_len if is_start else _polyline_length(loop_points) - ext_len
        anchor = point_at_chainage(loop_points, local_anchor).point
        if getattr(loop, "name", None):
            attach_overrun(label, loop.name, anchor, tip, ext_len, is_start)
