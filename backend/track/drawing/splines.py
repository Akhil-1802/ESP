"""Track DXF spline and geometric measurement helpers.

Pure geometry/drawing helpers used by track drawing and annotations.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from common.dxf import add_spline as _common_spline
from common.geometry import nearest_point_on_alignment as _nearest_point
from common.geometry import polyline_length as _polyline_length

Point = Tuple[float, float]

__all__ = [
    "_add_spline",
    "_measure_track_clearance_at",
    "_find_track_anchor",
    "_line_center",
    "_unit_vec",
    "_segment_mid",
]


def _add_spline(doc, points: List[Point], layer: str, color: int) -> None:
    """Add a smooth spline curve through the given points (canonical impl)."""
    _common_spline(doc, list(points), layer, color)


def _unit_vec(v: Sequence[float]) -> Tuple[float, float]:
    """Return unit vector for a 2D vector."""
    n = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / n, v[1] / n)


def _line_center(points: Sequence[Point]) -> Tuple[Point, Point]:
    """Centre of a polyline by length + its tangent there."""
    total = _polyline_length(points)
    half = total / 2.0
    travelled = 0.0
    pts = list(points)
    for first, second in zip(pts, pts[1:]):
        seg = math.hypot(second[0] - first[0], second[1] - first[1])
        if travelled + seg >= half:
            ratio = (half - travelled) / (seg or 1.0)
            anchor = (
                first[0] + ratio * (second[0] - first[0]),
                first[1] + ratio * (second[1] - first[1]),
            )
            return anchor, (second[0] - first[0], second[1] - first[1])
        travelled += seg
    return pts[-1], (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])


def _segment_mid(loop_points: Sequence[Point], eff_c1: float, main_a: float, main_b: float) -> Tuple[Point, Tuple[float, float]]:
    """Midpoint (+tangent) of a MAIN-datum segment on a loop centreline."""
    total = _polyline_length(loop_points)
    la = min(max(main_a - eff_c1, 0.0), total)
    lb = min(max(main_b - eff_c1, 0.0), total)
    mid_local = (la + lb) / 2.0
    travelled = 0.0
    pts = list(loop_points)
    for first, second in zip(pts, pts[1:]):
        seg = math.hypot(second[0] - first[0], second[1] - first[1])
        if travelled + seg >= mid_local:
            ratio = (mid_local - travelled) / (seg or 1.0)
            px = first[0] + ratio * (second[0] - first[0])
            py = first[1] + ratio * (second[1] - first[1])
            return (px, py), _unit_vec((second[0] - first[0], second[1] - first[1]))
        travelled += seg
    return pts[-1], _unit_vec((pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]))


def _measure_track_clearance_at(doc, anchor_x: float, anchor_y: float) -> Tuple[float, float]:
    """Measure vertical clearance to the nearest tracks/obstacles above and below anchor point."""
    above, below = [], []
    try:
        msp = doc.modelspace()
    except Exception:
        return math.inf, math.inf

    for e in msp:
        layer_name = (e.dxf.get("layer", "") or "").upper()
        if not any(k in layer_name for k in ["MAIN", "LOOP", "SIDING", "PROPOSED", "PLATFORM", "STATION", "BUILDING", "DIRECTION"]):
            continue
        if "DIM" in layer_name or "CHAINAGE" in layer_name:
            continue
        pts = None
        dxftype = e.dxftype()
        if dxftype in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = list(e.get_points())
                if getattr(e, "is_closed", False) or (int(e.dxf.get("flags", 0)) & 1):
                    if pts and pts[0] != pts[-1]:
                        pts.append(pts[0])
            except Exception:
                pass
        elif dxftype == "SPLINE":
            try:
                pts = list(e.control_points)
            except Exception:
                pass
        elif dxftype == "LINE":
            try:
                pts = [e.dxf.start, e.dxf.end]
            except Exception:
                pass
        elif dxftype in ("TEXT", "MTEXT"):
            try:
                ins = e.dxf.insert
                tx, ty = float(ins.x), float(ins.y)
                if abs(anchor_x - tx) < 8.0:
                    if ty > anchor_y + 0.3:
                        above.append(ty)
                    elif ty < anchor_y - 0.3:
                        below.append(ty)
            except Exception:
                pass
            continue

        if not pts or len(pts) < 2:
            continue
        for p1, p2 in zip(pts, pts[1:]):
            min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
            if min_x - 1e-3 <= anchor_x <= max_x + 1e-3:
                if abs(max_x - min_x) < 1e-6:
                    y = (p1[1] + p2[1]) / 2.0
                else:
                    r = (anchor_x - p1[0]) / (p2[0] - p1[0])
                    y = p1[1] + r * (p2[1] - p1[1])
                if y > anchor_y + 0.3:
                    above.append(y)
                elif y < anchor_y - 0.3:
                    below.append(y)
    d_above = min(above) - anchor_y if above else math.inf
    d_below = anchor_y - max(below) if below else math.inf
    return d_above, d_below


def _find_track_anchor(doc, points: Sequence[Point], align_x: float | None = None) -> Tuple[Point, float, float]:
    """Find the best anchor point along points, aligning with station datum/center if possible.

    Returns (anchor, tx, ty) where (tx, ty) is the tangent vector at anchor.
    """
    total = _polyline_length(points)
    half = total / 2.0
    travelled = 0.0
    anchor = points[-1]
    tx, ty = 1.0, 0.0
    for first, second in zip(points, points[1:]):
        seg = math.hypot(second[0] - first[0], second[1] - first[1])
        if travelled + seg >= half:
            ratio = (half - travelled) / (seg or 1.0)
            anchor = (
                first[0] + ratio * (second[0] - first[0]),
                first[1] + ratio * (second[1] - first[1]),
            )
            tx, ty = second[0] - first[0], second[1] - first[1]
            break
        travelled += seg

    ref_x = align_x
    if ref_x is None and doc is not None:
        try:
            msp = doc.modelspace()
            # 1. Look for STATION-BUILDING center
            for e in msp:
                layer = (e.dxf.get("layer", "") or "").upper()
                if "STATION-BUILDING" in layer:
                    if e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                        xs = [p[0] for p in e.get_points()]
                        if xs:
                            ref_x = (min(xs) + max(xs)) / 2.0
                            break
                    elif e.dxftype() == "MTEXT":
                        ref_x = float(e.dxf.insert.x)
                        break
            # 2. Look for DIRECTION mark center
            if ref_x is None:
                for e in msp:
                    layer = (e.dxf.get("layer", "") or "").upper()
                    if layer == "DIRECTION" and e.dxftype() == "LINE":
                        ref_x = (float(e.dxf.start.x) + float(e.dxf.end.x)) / 2.0
                        break
            # 3. Look for MAIN_LINE midpoint
            if ref_x is None:
                for e in msp:
                    layer = (e.dxf.get("layer", "") or "").upper()
                    if layer == "MAIN_LINE" and e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                        mpts = list(e.get_points())
                        if len(mpts) >= 2:
                            mlen = _polyline_length(mpts)
                            mtrav = 0.0
                            for f, s in zip(mpts, mpts[1:]):
                                mseg = math.hypot(s[0] - f[0], s[1] - f[1])
                                if mtrav + mseg >= mlen / 2.0:
                                    r = (mlen / 2.0 - mtrav) / (mseg or 1.0)
                                    ref_x = f[0] + r * (s[0] - f[0])
                                    break
                                mtrav += mseg
                            if ref_x is not None:
                                break
        except Exception:
            pass

    if ref_x is not None:
        xs = [p[0] for p in points]
        if min(xs) - 1e-3 <= ref_x <= max(xs) + 1e-3:
            for first, second in zip(points, points[1:]):
                x1, x2 = min(first[0], second[0]), max(first[0], second[0])
                if x1 - 1e-3 <= ref_x <= x2 + 1e-3:
                    if abs(second[0] - first[0]) < 1e-6:
                        ratio = 0.5
                    else:
                        ratio = (ref_x - first[0]) / (second[0] - first[0])
                    ratio = min(max(ratio, 0.0), 1.0)
                    anchor = (
                        first[0] + ratio * (second[0] - first[0]),
                        first[1] + ratio * (second[1] - first[1]),
                    )
                    tx, ty = second[0] - first[0], second[1] - first[1]
                    break

    return anchor, tx, ty
