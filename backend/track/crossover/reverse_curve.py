"""Reverse-curve crossover geometry for large track spacing (> 8000 mm)."""

from __future__ import annotations

import math
from typing import Sequence

from common.geometry import Point, rotate as _rotate
from track.crossover.turnout import _sample_spline, _sample_tangent


def _build_reverse_curve_crossover(
    start: Point,
    end: Point,
    alignment: Point,
    normal: Point,
    a_m: float,
    b_m: float,
    radius_m: float,
    theta: float,
    tangent_m: float,
) -> list[Point]:
    """Build a large-spacing crossover using two reverse curves joined by tangents."""
    points: list[Point] = [start]
    pts_a1 = _sample_tangent(start, alignment, a_m)
    points.extend(pts_a1[1:])
    s1 = pts_a1[-1]
    dir_in = _rotate(alignment, theta)
    arc1 = _sample_spline(s1, alignment, dir_in, radius_m, theta, samples=128)
    points.extend(arc1[1:])
    s2 = arc1[-1]
    pts_t1 = _sample_tangent(s2, dir_in, tangent_m)
    points.extend(pts_t1[1:])
    s3 = pts_t1[-1]
    pts_b = _sample_tangent(s3, alignment, b_m)
    points.extend(pts_b[1:])
    s4 = pts_b[-1]
    dir_out = _rotate(alignment, -theta)
    pts_t2 = _sample_tangent(s4, dir_out, tangent_m)
    points.extend(pts_t2[1:])
    s5 = pts_t2[-1]
    arc2 = _sample_spline(s5, dir_out, alignment, radius_m, theta, samples=128)
    points.extend(arc2[1:])
    s6 = arc2[-1]
    pts_a2 = _sample_tangent(s6, alignment, a_m)
    points.extend(pts_a2[1:])
    if points:
        points[-1] = end
    return points


__all__ = ["_build_reverse_curve_crossover"]
