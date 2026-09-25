"""Calculation and formatting utilities for CAL labels."""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from common.geometry import (
    Point,
    point_at_chainage as _chainage_point,
    polyline_length as _polyline_length,
    readable_angle_deg as _readable_angle,
)

CAL_LAYER: str = "TRACK_CAL"
CAL_COLOR: int = 1
CAL_TEXT_HEIGHT_M: float = 1.0
CAL_FRACTION: float = 0.5
CAL_STACK_BASE_M: float = 2.5
CAL_STACK_STEP_M: float = 4.0
CAL_TEXT_RUN_M: float = 2.0
CAL_TEXT_GAP_M: float = 2.5
CAL_COLUMN_GAP_M: float = 2.0
CAL_MARK_BEFORE_CENTRE_M: float = 50.0
CAL_TEXT_BACK_M: float = 8.0
CAL_TEXT_LIFT_M: float = 3.0
CAL_SURVEY_HALF_M: float = 2.0


def _is_main_line(name: str) -> bool:
    """Whether ``name`` is the base or an added full-length MAIN line."""
    normalized = str(name).upper()
    return normalized == "MAIN_LINE" or normalized.startswith("MAIN_LINE_")


def _is_loop_line(name: str) -> bool:
    """Whether ``name`` is a LOOP running line."""
    return str(name).upper().startswith("LOOP")


def format_loop_name(number: int) -> str:
    """``LOOP LINE NO-n`` -- Column 1 name part."""
    return f"LOOP LINE NO-{int(number)}"


def format_main_name(number: int) -> str:
    """``MAIN LINE NO-n`` -- Column 1 name part."""
    return f"MAIN LINE NO-{int(number)}"


def format_loop_cal_value(length_m: float) -> str:
    """``CAL 776.000M (END TO END)`` -- Column 2 CAL part."""
    return f"CAL {float(length_m):.3f}M (END TO END)"


def format_main_cal_value(length_m: float) -> str:
    """``CAL 822.184M (FM TO FM)`` -- Column 2 CAL part."""
    return f"CAL {float(length_m):.3f}M (FM TO FM)"


def format_loop_cal(number: int, length_m: float) -> str:
    """``LOOP LINE NO-n CAL 776.000M (END TO END)`` -- end to end."""
    return f"{format_loop_name(number)} {format_loop_cal_value(length_m)}"


def format_main_cal(number: int, length_m: float) -> str:
    """``MAIN LINE NO-n CAL 822.184M (FM TO FM)`` -- FM to FM."""
    return f"{format_main_name(number)} {format_main_cal_value(length_m)}"


def split_cal_label(label: str) -> Tuple[str, str]:
    """Split a full CAL label into ``(name, cal_value)`` columns."""
    text = str(label or "")
    marker = " CAL "
    idx = text.find(marker)
    if idx < 0:
        return text, ""
    return text[:idx], text[idx + 1 :]


def assign_line_numbers(
    tracks: Dict[str, Sequence[Point]],
) -> List[Tuple[str, str, int]]:
    """One global line number per running line: LOOPs first, then MAINs."""
    ordered: List[Tuple[str, str]] = []
    for name in tracks or {}:
        if _is_loop_line(name):
            ordered.append((name, "LOOP"))
    for name in tracks or {}:
        if _is_main_line(name):
            ordered.append((name, "MAIN"))
    return [
        (name, kind, index + 1) for index, (name, kind) in enumerate(ordered)
    ]


def main_fm_span_m(marks: Sequence[object], track: str) -> float | None:
    """Along-track FM-to-FM distance on ``track`` (last FM to last FM)."""
    chainages: List[float] = []
    for mark in marks or []:
        try:
            if str(getattr(mark, "track", "")) != str(track):
                continue
            value = float(getattr(mark, "local_chainage"))
        except (TypeError, ValueError, AttributeError):
            continue
        if math.isfinite(value):
            chainages.append(value)
    if len(chainages) < 2:
        return None
    return float(max(chainages) - min(chainages))


def _track_frame(
    points: Sequence[Point],
) -> Tuple[Point, Point, Point, float, float] | None:
    """Centre-station frame of a centreline: tip, tangent, normal, angle, length."""
    try:
        pts = [(float(p[0]), float(p[1])) for p in points]
        if len(pts) < 2:
            return None
        total = _polyline_length(pts)
        if total < 1e-9:
            return None
        station = _chainage_point(
            pts, min(max(CAL_FRACTION * total, 0.0), total)
        )
        tip = (float(station.point[0]), float(station.point[1]))
        tx, ty = float(station.tangent[0]), float(station.tangent[1])
        norm = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norm, ty / norm
        nx, ny = -ty, tx
        try:
            ang = _readable_angle(math.degrees(math.atan2(ty, tx)))
        except Exception:
            ang = 0.0
        return tip, (tx, ty), (nx, ny), float(ang), float(total)
    except Exception:
        return None


def _point_at_u(
    points: Sequence[Point], u_target: float, origin: Point, tangent: Point
) -> Tuple[Point, Point] | None:
    """Point on ``points`` at track-parallel coordinate ``u_target``."""
    try:
        pts = [(float(p[0]), float(p[1])) for p in points]
        if len(pts) < 2:
            return None
        ox, oy = float(origin[0]), float(origin[1])
        tx, ty = float(tangent[0]), float(tangent[1])
        n = math.hypot(tx, ty) or 1.0
        tx, ty = tx / n, ty / n
        us = [(p[0] - ox) * tx + (p[1] - oy) * ty for p in pts]
        for p1, p2, u1, u2 in zip(pts, pts[1:], us, us[1:]):
            if (u1 <= u_target <= u2) or (u2 <= u_target <= u1):
                span = u2 - u1
                r = 0.0 if abs(span) < 1e-12 else (u_target - u1) / span
                r = min(max(r, 0.0), 1.0)
                pt = (
                    p1[0] + r * (p2[0] - p1[0]),
                    p1[1] + r * (p2[1] - p1[1]),
                )
                tan = (p2[0] - p1[0], p2[1] - p1[1])
                tn = math.hypot(*tan) or 1.0
                return pt, (tan[0] / tn, tan[1] / tn)
        if u_target <= min(us[0], us[-1]):
            i = int(min(range(len(us)), key=lambda k: us[k]))
        else:
            i = int(max(range(len(us)), key=lambda k: us[k]))
        best, best_d = pts[0], abs(us[0] - u_target)
        for p, u in zip(pts, us):
            d = abs(u - u_target)
            if d < best_d:
                best, best_d = p, d
        if i == 0:
            tan = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        else:
            tan = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
        tn = math.hypot(*tan) or 1.0
        return best, (tan[0] / tn, tan[1] / tn)
    except Exception:
        return None


def _top_rail_above(
    tracks: Dict[str, Sequence[Point]],
    tip: Point,
    tangent: Point,
    normal: Point,
    doc=None,
) -> float:
    """Highest lateral reach (m) of any track/structure above ``tip`` near the centre."""
    try:
        tx, ty = float(tangent[0]), float(tangent[1])
        nx, ny = float(normal[0]), float(normal[1])
        top = 0.0
        for pts in (tracks or {}).values():
            for p in pts or []:
                try:
                    dx, dy = float(p[0]) - tip[0], float(p[1]) - tip[1]
                except (TypeError, ValueError):
                    continue
                if abs(dx * tx + dy * ty) > CAL_SURVEY_HALF_M:
                    continue
                side = dx * nx + dy * ny
                if side > top:
                    top = side
        if doc is not None:
            try:
                msp = doc.modelspace()
                for e in msp:
                    try:
                        layer = (e.dxf.get("layer", "") or "").upper()
                    except Exception:
                        continue
                    if "DIM" in layer or "CHAINAGE" in layer:
                        continue
                    pts = []
                    is_structure = any(
                        k in layer
                        for k in ["PLATFORM", "STATION", "BUILDING", "FOB"]
                    )
                    if is_structure and e.dxftype() in (
                        "LWPOLYLINE",
                        "POLYLINE",
                    ):
                        try:
                            pts = list(e.get_points())
                        except Exception:
                            pts = []
                    elif is_structure and e.dxftype() == "LINE":
                        try:
                            pts = [e.dxf.start, e.dxf.end]
                        except Exception:
                            pts = []
                    elif e.dxftype() in ("TEXT", "MTEXT"):
                        try:
                            if e.dxftype() == "TEXT":
                                ins = e.dxf.insert
                                cx, cy = float(ins.x), float(ins.y)
                                h = float(e.dxf.get("height", 1.0) or 1.0)
                            else:
                                ins = e.dxf.insert
                                cx, cy = float(ins.x), float(ins.y)
                                h = float(e.dxf.get("char_height", 1.0) or 1.0)
                            dx, dy = cx - tip[0], cy - tip[1]
                            if abs(dx * tx + dy * ty) > CAL_SURVEY_HALF_M + 20.0:
                                continue
                            side = dx * nx + dy * ny + h / 2.0 + 1.0
                            if side > top:
                                top = side
                        except Exception:
                            pass
                        continue
                    else:
                        continue
                    for p in pts:
                        dx = float(p[0]) - tip[0]
                        dy = float(p[1]) - tip[1]
                        if abs(dx * tx + dy * ty) > CAL_SURVEY_HALF_M:
                            continue
                        side = dx * nx + dy * ny
                        if side > top:
                            top = side
            except Exception:
                pass
        return max(float(top), 0.0)
    except Exception:
        return 0.0


__all__ = [
    "CAL_COLUMN_GAP_M",
    "CAL_COLOR",
    "CAL_FRACTION",
    "CAL_LAYER",
    "CAL_MARK_BEFORE_CENTRE_M",
    "CAL_STACK_BASE_M",
    "CAL_STACK_STEP_M",
    "CAL_SURVEY_HALF_M",
    "CAL_TEXT_BACK_M",
    "CAL_TEXT_GAP_M",
    "CAL_TEXT_HEIGHT_M",
    "CAL_TEXT_LIFT_M",
    "CAL_TEXT_RUN_M",
    "_is_loop_line",
    "_is_main_line",
    "_point_at_u",
    "_top_rail_above",
    "_track_frame",
    "assign_line_numbers",
    "format_loop_cal",
    "format_loop_cal_value",
    "format_loop_name",
    "format_main_cal",
    "format_main_cal_value",
    "format_main_name",
    "main_fm_span_m",
    "split_cal_label",
]
