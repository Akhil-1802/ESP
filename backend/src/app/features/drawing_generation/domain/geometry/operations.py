"""Canonical pure 2D geometry helpers (dependency-free).

Everything works on plain ``(x, y)`` tuples and polylines. Units are
whatever the caller uses (the ESP pipeline uses metres for DXF
coordinates and converts to mm only for turnout formulas).
"""

from __future__ import annotations

import math
from typing import Sequence

# Alignment and chainage imports re-exported for convenience
from .alignment import (
    Projection,
    StationPoint,
    cumulative_chainages,
    find_straight_window,
    nearest_point_on_alignment,
    offset_alignment,
    offset_point,
    point_at_chainage,
    point_side,
    rectangle_from_two_offsets,
    validate_straight_interval,
)

Point = tuple[float, float]
EPS: float = 1e-9

__all__ = [
    "EPS",
    "Point",
    "Projection",
    "StationPoint",
    "angle_between",
    "bounds",
    "cumulative_chainages",
    "distance",
    "find_straight_window",
    "validate_straight_interval",
    "nearest_point_on_alignment",
    "offset_alignment",
    "offset_point",
    "point_at_chainage",
    "point_side",
    "polygon_contains",
    "polygons_overlap",
    "polyline_length",
    "readable_angle_deg",
    "rectangle_from_two_offsets",
    "rotate",
    "segments_intersect",
    "unit",
]


# --- basic vectors ---------------------------------------------------------

def distance(a: Point, b: Point) -> float:
    """Euclidean distance between two points."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


def unit(v: Point) -> Point:
    """Unit vector in the direction of v (zero vector -> (0, 0))."""
    n = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / n, v[1] / n)


def rotate(v: Point, angle: float) -> Point:
    """Rotate vector v by angle radians (CCW positive)."""
    ca, sa = math.cos(angle), math.sin(angle)
    return (v[0] * ca - v[1] * sa, v[0] * sa + v[1] * ca)


def angle_between(a: Point, b: Point) -> float:
    """Unsigned angle (radians) between two vectors."""
    ua, ub = unit(a), unit(b)
    dot = min(max(ua[0] * ub[0] + ua[1] * ub[1], -1.0), 1.0)
    return math.acos(dot)


def readable_angle_deg(angle: float) -> float:
    """Normalise a text rotation to (-90, 90] so labels stay readable."""
    while angle > 90.0 + 1e-4:
        angle -= 180.0
    while angle <= -90.0 + 1e-4:
        angle += 180.0
    if abs(abs(angle) - 90.0) < 1e-3:
        return 90.0
    return angle


# --- polylines ---------------------------------------------------------------

def polyline_length(points: Sequence[Point]) -> float:
    """Total length along a chain of points."""
    return sum(distance(a, b) for a, b in zip(points, points[1:]))


# --- polygon predicates (single implementation) --------------------------------

def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point, eps: float = 1e-9) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point, eps: float = 1e-9) -> bool:
    """True when segments p1-p2 and p3-p4 intersect (touching counts)."""
    o1, o2, o3, o4 = (
        _orientation(p1, p2, p3),
        _orientation(p1, p2, p4),
        _orientation(p3, p4, p1),
        _orientation(p3, p4, p2),
    )
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    ):
        return True
    return any(
        abs(v) <= eps and _on_segment(a, b, pt, eps)
        for v, a, b, pt in (
            (o1, p1, p2, p3),
            (o2, p1, p2, p4),
            (o3, p3, p4, p1),
            (o4, p3, p4, p2),
        )
    )


def polygon_contains(polygon: Sequence[Point], point: Point) -> bool:
    """Ray-cast point-in-polygon test."""
    inside = False
    ring = list(polygon)
    for first, second in zip(ring, ring[1:] + ring[:1]):
        if (first[1] > point[1]) != (second[1] > point[1]):
            crossing = (second[0] - first[0]) * (point[1] - first[1]) / (
                second[1] - first[1]
            ) + first[0]
            if point[0] < crossing:
                inside = not inside
    return inside


def polygons_overlap(first: Sequence[Point], second: Sequence[Point]) -> bool:
    """True when two polygons intersect or one contains the other."""
    f, s = list(first), list(second)
    return (
        any(
            segments_intersect(a, b, c, d)
            for a, b in zip(f, f[1:] + f[:1])
            for c, d in zip(s, s[1:] + s[:1])
        )
        or polygon_contains(f, s[0])
        or polygon_contains(s, f[0])
    )


def bounds(points: Sequence[Point]) -> tuple[float, float, float, float]:
    """Bounding box (min_x, min_y, max_x, max_y)."""
    return (
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )
