"""Crossover footprint and intersection geometric predicates."""

from __future__ import annotations

from typing import Sequence

from ...geometry.operations import Point


def footprints_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """True when two MAIN-datum footprint intervals strictly overlap."""
    a0, a1 = min(a), max(a)
    b0, b1 = min(b), max(b)
    return max(a0, b0) < min(a1, b1) - 1e-9


def _segments_intersect(p1, p2, p3, p4) -> bool:
    def _orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def _on_seg(a, b, p):
        return (
            min(a[0], b[0]) - 1e-9 <= p[0] <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= p[1] <= max(a[1], b[1]) + 1e-9
        )

    o1, o2, o3, o4 = (
        _orient(p1, p2, p3),
        _orient(p1, p2, p4),
        _orient(p3, p4, p1),
        _orient(p3, p4, p2),
    )
    if ((o1 > 1e-9 and o2 < -1e-9) or (o1 < -1e-9 and o2 > 1e-9)) and (
        (o3 > 1e-9 and o4 < -1e-9) or (o3 < -1e-9 and o4 > 1e-9)
    ):
        return True
    return any(
        abs(o) <= 1e-9 and _on_seg(a, b, p)
        for o, a, b, p in (
            (o1, p1, p2, p3),
            (o2, p1, p2, p4),
            (o3, p3, p4, p1),
            (o4, p3, p4, p2),
        )
    )


def polyline_self_intersects(points: Sequence[Point]) -> bool:
    """Detect self-intersection excluding consecutive segments."""
    pts = list(points)
    n = len(pts) - 1
    if n < 2:
        return False
    tol = 1e-9
    boxes: list[tuple[float, float, float, float]] = []
    for k in range(n):
        try:
            ax, ay = float(pts[k][0]), float(pts[k][1])
            bx, by = float(pts[k + 1][0]), float(pts[k + 1][1])
        except (TypeError, ValueError, IndexError):
            return any(
                _segments_intersect(pts[i], pts[i + 1], pts[j], pts[j + 1])
                for i in range(n)
                for j in range(i + 2, n)
                if not (i == 0 and j == n - 1)
            )
        boxes.append(
            (
                min(ax, bx) - tol,
                min(ay, by) - tol,
                max(ax, bx) + tol,
                max(ay, by) + tol,
            )
        )
    test = _segments_intersect
    for i in range(n):
        a0x, a0y, a1x, a1y = boxes[i]
        pi0, pi1 = pts[i], pts[i + 1]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            b0x, b0y, b1x, b1y = boxes[j]
            if a1x < b0x or b1x < a0x or a1y < b0y or b1y < a0y:
                continue
            if test(pi0, pi1, pts[j], pts[j + 1]):
                return True
    return False


def is_main_track(name: str) -> bool:
    """True for MAIN_LINE and MAIN_LINE_N variants."""
    try:
        s = str(name)
    except Exception:
        return False
    return s == "MAIN_LINE" or s.startswith("MAIN_LINE")


__all__ = [
    "_segments_intersect",
    "footprints_overlap",
    "is_main_track",
    "polyline_self_intersects",
]
