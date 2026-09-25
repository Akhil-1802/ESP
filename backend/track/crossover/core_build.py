"""build_standard_crossover — SRJ-to-SRJ centreline builder.

Extracted from core.py to keep each file under 500 lines.
"""

from __future__ import annotations

import math
from typing import Sequence

from common.constants import (
    F_DIAG_TOLERANCE_DEG as STANDARD_F_DIAG_TOLERANCE_DEG,
    MAX_VERTEX_GAP_M as STANDARD_MAX_VERTEX_GAP_M,
    MM_PER_UNIT,
    PARALLEL_TOLERANCE_DEGREES,
)
from common.geometry import Point, angle_between as _angle_between, rotate as _rotate, unit as _unit
from track.crossover.turnout import _sample_spline, _sample_tangent, turnout_ratio_n
from track.turnouts import (
    BG_1_12_LEAD_RADIUS_M,
    BG_1_8_5_LEAD_RADIUS_M,
    TurnoutParameters,
)

STANDARD_PARALLEL_TOLERANCE_DEG = PARALLEL_TOLERANCE_DEGREES


def build_standard_crossover(
    from_pt: Point,
    from_tangent: Point,
    to_pt: Point,
    to_tangent: Point,
    turnout: TurnoutParameters,
) -> tuple[list[Point], dict]:
    """Build the SRJ-to-SRJ crossover centreline from turnout pieces."""
    u = _unit(from_tangent)
    v = _unit(to_tangent)

    parallel_deg = math.degrees(_angle_between(u, v))
    if parallel_deg > STANDARD_PARALLEL_TOLERANCE_DEG:
        raise ValueError(
            f"Crossover needs locally parallel tracks, but the FROM/TO "
            f"tangents differ by {parallel_deg:.2f} deg "
            f"(limit {STANDARD_PARALLEL_TOLERANCE_DEG:.1f})."
        )

    wx, wy = to_pt[0] - from_pt[0], to_pt[1] - from_pt[1]
    tc_m = abs(wx * (-u[1]) + wy * u[0])
    if tc_m <= 1e-9:
        raise ValueError("FROM and TO SRJs coincide - a crossover needs two distinct tracks.")
    cross = u[0] * wy - u[1] * wx
    s = 1.0 if cross > 0 else -1.0

    n = turnout_ratio_n(turnout)
    f = math.atan(1.0 / n)
    d = _rotate(u, s * f)

    a_m = turnout.a_mm / MM_PER_UNIT
    if turnout.radius_mm is not None and turnout.radius_mm > 0:
        r_lib_m = turnout.radius_mm / MM_PER_UNIT
        r_note = None
    else:
        r_lib_m = (
            BG_1_8_5_LEAD_RADIUS_M
            if getattr(turnout, "designation", "") == "1:8.5"
            else BG_1_12_LEAD_RADIUS_M
        )
        r_note = f"turnout has no verified radius; using RDSO standard {r_lib_m:g} m"

    corner1 = (from_pt[0] + u[0] * a_m, from_pt[1] + u[1] * a_m)
    corner2 = (to_pt[0] - v[0] * a_m, to_pt[1] - v[1] * a_m)
    diag_vec = (corner2[0] - corner1[0], corner2[1] - corner1[1])
    diag_len = math.hypot(diag_vec[0], diag_vec[1])
    if diag_len <= 1e-9:
        raise ValueError(
            f"Crossover corners coincide - TC is too small for the "
            f"{turnout.designation} turnout (A={turnout.a_mm:g} mm)."
        )
    diag_dir = (diag_vec[0] / diag_len, diag_vec[1] / diag_len)

    warnings: list[str] = []
    if r_note is not None:
        warnings.append(r_note)

    diag_vs_f_deg = math.degrees(_angle_between(diag_dir, d))
    if diag_vs_f_deg > STANDARD_F_DIAG_TOLERANCE_DEG:
        warnings.append(
            f"diagonal is {diag_vs_f_deg:.2f} deg off the turnout angle F "
            f"(tracks are curved between the SRJs; F={math.degrees(f):.4f} deg)"
        )

    sweep1 = _angle_between(u, diag_dir)
    sweep2 = _angle_between(diag_dir, v)
    tan1 = math.tan(sweep1 / 2.0)
    tan2 = math.tan(sweep2 / 2.0)
    _eps = 1e-12
    r_candidates: list[float] = []
    if tan1 > _eps:
        r_candidates.append(a_m / tan1)
    if tan2 > _eps:
        r_candidates.append(a_m / tan2)
    if tan1 + tan2 > _eps:
        r_candidates.append(diag_len / (tan1 + tan2))
    if not r_candidates:
        tan_half = math.tan(f / 2.0)
        r_max_m = min(a_m, diag_len / 2.0) / (tan_half or 1.0)
    else:
        r_max_m = min(r_candidates)
    if r_max_m <= 0:
        raise ValueError("Crossover has no room for turnout curves.")
    r_m = min(r_lib_m, r_max_m)
    if r_lib_m - r_m > 1e-9:
        warnings.append(
            f"curve radius constrained to {r_m:.1f} m by fit "
            f"(verified turnout radius {r_lib_m:g} m does not fit A={a_m:g} m straights)"
        )
    t1_m = r_m * tan1
    t2_m = r_m * tan2
    t_m = (t1_m + t2_m) / 2.0

    tp1a = (corner1[0] - u[0] * t1_m, corner1[1] - u[1] * t1_m)
    tp2a = (corner2[0] + v[0] * t2_m, corner2[1] + v[1] * t2_m)

    if abs(math.degrees(sweep1) - math.degrees(f)) > STANDARD_F_DIAG_TOLERANCE_DEG:
        warnings.append(f"FROM turnout sweep {math.degrees(sweep1):.2f} deg differs from F")
    if abs(math.degrees(sweep2) - math.degrees(f)) > STANDARD_F_DIAG_TOLERANCE_DEG:
        warnings.append(f"TO turnout sweep {math.degrees(sweep2):.2f} deg differs from F")

    def _dense_tangent(start: Point, direction: Point, length: float) -> list[Point]:
        samples = max(2, int(length / 2.0) + 1)
        return _sample_tangent(start, _unit(direction), length, samples=samples)

    mid_len = math.hypot(
        corner2[0] - diag_dir[0] * t2_m - (corner1[0] + diag_dir[0] * t1_m),
        corner2[1] - diag_dir[1] * t2_m - (corner1[1] + diag_dir[1] * t1_m),
    )
    n_mid_sparse = max(4, int(mid_len / 3.5) + 1)
    n_transition = 128 + n_mid_sparse + 128

    def _transition_mid(p0: Point, p1: Point) -> list[Point]:
        span = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        w1 = min(span / 5.0 * 1.2, 0.24 * span)
        w2 = 2.0 * w1
        belly_amp = min(0.8, 0.12 * tc_m)
        cx, cy = ((p1[0] - p0[0]) / span, (p1[1] - p0[1]) / span) if span > 1e-12 else (u[0], u[1])
        bx, by = -cy, cx
        _lx, _ly = -u[1], u[0]
        if s < 0:
            _lx, _ly = -_lx, -_ly
        if bx * _lx + by * _ly < 0:
            bx, by = -bx, -by
        B0 = p0
        B1 = (p0[0] + w1 * u[0], p0[1] + w1 * u[1])
        B2 = (p0[0] + w2 * u[0], p0[1] + w2 * u[1])
        B3 = (p1[0] - w2 * v[0], p1[1] - w2 * v[1])
        B4 = (p1[0] - w1 * v[0], p1[1] - w1 * v[1])
        B5 = p1
        pts: list[Point] = []
        for i in range(n_transition + 1):
            t = i / float(n_transition)
            mt = 1.0 - t
            b0 = mt ** 5
            b1 = 5.0 * mt ** 4 * t
            b2 = 10.0 * mt ** 3 * t * t
            b3 = 10.0 * mt * mt * t ** 3
            b4 = 5.0 * mt * t ** 4
            b5 = t ** 5
            t2 = t * t
            t3 = t2 * t
            S = 6.0 * t3 * t2 - 15.0 * t2 * t2 + 10.0 * t3
            bump = belly_amp * 4.0 * S * (1.0 - S) * (math.sin(math.pi * t) ** 2)
            pts.append((
                b0 * B0[0] + b1 * B1[0] + b2 * B2[0]
                + b3 * B3[0] + b4 * B4[0] + b5 * B5[0] + bx * bump,
                b0 * B0[1] + b1 * B1[1] + b2 * B2[1]
                + b3 * B3[1] + b4 * B4[1] + b5 * B5[1] + by * bump,
            ))
        pts[0] = p0
        pts[-1] = p1
        return pts

    raw_points = [from_pt]
    if a_m - t1_m > 1e-4:
        raw_points.extend(_dense_tangent(from_pt, u, a_m - t1_m)[1:])
    raw_points.extend(_transition_mid(tp1a, tp2a)[1:])
    if a_m - t2_m > 1e-4:
        raw_points.extend(_dense_tangent(tp2a, v, a_m - t2_m)[1:])
    raw_points[-1] = to_pt

    points: list[Point] = [raw_points[0]]
    for pt in raw_points[1:]:
        if math.hypot(pt[0] - points[-1][0], pt[1] - points[-1][1]) > 1e-4:
            points.append(pt)
    if math.hypot(points[-1][0] - to_pt[0], points[-1][1] - to_pt[1]) > 1e-4:
        points.append(to_pt)
    else:
        points[-1] = to_pt

    max_gap = max(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(points, points[1:])
    )
    if max_gap > STANDARD_MAX_VERTEX_GAP_M:
        warnings.append(f"polyline vertex gap {max_gap:.2f} m exceeds 5 m")

    longs = [(p[0] - from_pt[0]) * u[0] + (p[1] - from_pt[1]) * u[1] for p in points]
    if any(b < a - 1e-6 for a, b in zip(longs, longs[1:])):
        warnings.append("centreline folds back longitudinally - check TC/turnout")

    lats = [abs((p[0] - from_pt[0]) * (-u[1]) + (p[1] - from_pt[1]) * u[0]) for p in points]
    if any(lat < -1.0 - 1e-6 or lat > tc_m + 1.0 + 1e-6 for lat in lats):
        warnings.append("centreline leaves the corridor between the tracks")

    mid = points[len(points) // 2]
    mid_lat = (mid[0] - from_pt[0]) * (-u[1]) + (mid[1] - from_pt[1]) * u[0]
    mid_frac = (s * mid_lat) / tc_m if tc_m > 0 else 0.0

    report = {
        "tc_m": tc_m,
        "tc_mm": tc_m * MM_PER_UNIT,
        "n": n,
        "a_m": a_m,
        "f_rad": f,
        "f_deg": math.degrees(f),
        "side": "LEFT" if s > 0 else "RIGHT",
        "r_lib_m": r_lib_m,
        "r_used_m": r_m,
        "r_constrained": r_lib_m - r_m > 1e-9,
        "fillet_tangent_m": t_m,
        "diag_len_m": diag_len,
        "diag_vs_f_deg": diag_vs_f_deg,
        "sweep1_deg": math.degrees(sweep1),
        "sweep2_deg": math.degrees(sweep2),
        "mid_straight_m": mid_len,
        "n_points": len(points),
        "max_vertex_gap_m": max_gap,
        "mid_lateral_fraction": mid_frac,
        "parallel_deg": parallel_deg,
        "warnings": warnings,
    }
    return points, report


__all__ = ["build_standard_crossover"]
