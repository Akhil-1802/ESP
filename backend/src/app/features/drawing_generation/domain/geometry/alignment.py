"""Track alignment and chainage geometry helpers.

Provides chainage accumulation, point-at-chainage interpolation,
sideway offsets, and projection of points onto track centerlines.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Sequence

try:
    import numpy as _np
except ImportError:  # optional accelerator; scalar paths below stay exact
    _np = None  # type: ignore[assignment]

Point = tuple[float, float]

#: Minimum vertices for the vectorized nearest-point path.
_NP_MIN_POINTS: int = 48


def cumulative_chainages(points: Sequence[Point]) -> List[float]:
    """Running distance-along-alignment for each vertex, starting at 0."""
    chainages = [0.0]
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        chainages.append(chainages[-1] + math.hypot(dx, dy))
    return chainages


@lru_cache(maxsize=64)
def _cached_chainages(key: tuple) -> tuple:
    """Cumulative chainages for a snapshot of vertices (exact values)."""
    chainages = [0.0]
    for i in range(1, len(key)):
        dx = key[i][0] - key[i - 1][0]
        dy = key[i][1] - key[i - 1][1]
        chainages.append(chainages[-1] + math.hypot(dx, dy))
    return tuple(chainages)


def _chainages_for(points: Sequence[Point]) -> tuple:
    """Cached cumulative chainages (falls back to fresh math if unhashable)."""
    try:
        return _cached_chainages(tuple(points))
    except TypeError:
        return tuple(cumulative_chainages(points))


@lru_cache(maxsize=64)
def _cached_array(key: tuple):
    """Numpy vertex array for a snapshot of vertices (read-only use)."""
    arr = _np.asarray(key, dtype=_np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2 or arr.shape[0] != len(key):
        raise ValueError("ragged vertex list")
    return arr


def _array_for(key: tuple):
    """Cached vertex array, or None when unavailable/unsuitable."""
    if _np is None:
        return None
    try:
        return _cached_array(key)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class StationPoint:
    """A point on the alignment plus the direction of travel there."""
    point: Point
    tangent: Point  # unit vector, direction of increasing chainage
    chainage: float

    @property
    def normal_left(self) -> Point:
        """Unit vector 90 deg left of travel direction (CCW rotation)."""
        tx, ty = self.tangent
        return (-ty, tx)

    @property
    def normal_right(self) -> Point:
        """Unit vector 90 deg right of travel direction (CW rotation)."""
        tx, ty = self.tangent
        return (ty, -tx)


def _interpolate_on_segment(
    points: Sequence[Point], i: int, chainage: float, seg_start: float, seg_end: float
) -> StationPoint:
    """StationPoint for chainage on segment i."""
    seg_len = seg_end - seg_start
    t = 0.0 if seg_len < 1e-12 else (chainage - seg_start) / seg_len
    x = points[i][0] + t * (points[i + 1][0] - points[i][0])
    y = points[i][1] + t * (points[i + 1][1] - points[i][1])
    dx = points[i + 1][0] - points[i][0]
    dy = points[i + 1][1] - points[i][1]
    length = math.hypot(dx, dy) or 1.0
    return StationPoint((x, y), (dx / length, dy / length), chainage)


def point_at_chainage(points: Sequence[Point], chainage: float) -> StationPoint:
    """Interpolate the alignment at chainage (distance from vertex 0)."""
    if len(points) < 2:
        raise ValueError("Track centerline needs at least 2 vertices")

    chainages = _chainages_for(points)
    total = chainages[-1]

    if chainage < -1e-6 or chainage > total + 1e-6:
        raise ValueError(
            f"Chainage {chainage:.3f} is outside the track extent [0, {total:.3f}]"
        )

    chainage = min(max(chainage, 0.0), total)
    last_seg = len(points) - 2
    i = bisect.bisect_right(chainages, chainage - 1e-9, 0, len(chainages) - 1) - 1
    if i < 0:
        i = 0
    elif i > last_seg:
        i = last_seg
    seg_start, seg_end = chainages[i], chainages[i + 1]
    if seg_start - 1e-9 <= chainage <= seg_end + 1e-9:
        return _interpolate_on_segment(points, i, chainage, seg_start, seg_end)

    for i in range(len(points) - 1):
        seg_start, seg_end = chainages[i], chainages[i + 1]
        if seg_start - 1e-9 <= chainage <= seg_end + 1e-9:
            return _interpolate_on_segment(points, i, chainage, seg_start, seg_end)

    dx = points[-1][0] - points[-2][0]
    dy = points[-1][1] - points[-2][1]
    length = math.hypot(dx, dy) or 1.0
    return StationPoint(points[-1], (dx / length, dy / length), total)


def offset_point(sp: StationPoint, dist: float, side: str) -> Point:
    """Move a StationPoint sideways by dist to LEFT/RIGHT."""
    nx, ny = sp.normal_left if side.upper() == "LEFT" else sp.normal_right
    return (sp.point[0] + nx * dist, sp.point[1] + ny * dist)


def offset_alignment(
    points: Sequence[Point],
    start_chainage: float,
    end_chainage: float,
    dist: float,
    side: str,
    num_samples: int = 2,
) -> List[Point]:
    """Build a parallel line offset dist to one side."""
    if num_samples < 2:
        num_samples = 2
    step = (end_chainage - start_chainage) / (num_samples - 1)
    return [
        offset_point(point_at_chainage(points, start_chainage + step * i), dist, side)
        for i in range(num_samples)
    ]


@dataclass(frozen=True)
class Projection:
    """Closest point projection on an alignment."""
    point: Point       # closest point on the alignment
    chainage: float    # its chainage
    distance: float    # perpendicular distance from the query point


def _nearest_vectorized(
    key: tuple, qx: float, qy: float, chainages: tuple
) -> Projection | None:
    """Nearest-point search over all segments at once (numpy)."""
    arr = _array_for(key)
    if arr is None or len(key) < 2:
        return None
    if not (math.isfinite(qx) and math.isfinite(qy)):
        return None
    if not bool(_np.isfinite(arr).all()):
        return None
    ax = arr[:-1, 0]
    ay = arr[:-1, 1]
    dx = arr[1:, 0] - ax
    dy = arr[1:, 1] - ay
    seg_len_sq = dx * dx + dy * dy
    with _np.errstate(divide="ignore", invalid="ignore"):
        raw = ((qx - ax) * dx + (qy - ay) * dy) / _np.where(
            seg_len_sq < 1e-12, 1.0, seg_len_sq
        )
    t = _np.where(seg_len_sq < 1e-12, 0.0, raw)
    t = _np.minimum(_np.maximum(t, 0.0), 1.0)
    d2 = (qx - (ax + t * dx)) ** 2 + (qy - (ay + t * dy)) ** 2
    i = int(_np.argmin(d2))

    sx, sy = key[i]
    ex, ey = key[i + 1]
    ddx, ddy = ex - sx, ey - sy
    sq = ddx * ddx + ddy * ddy
    if sq < 1e-12:
        tt = 0.0
    else:
        tt = ((qx - sx) * ddx + (qy - sy) * ddy) / sq
        tt = min(max(tt, 0.0), 1.0)
    px, py = sx + tt * ddx, sy + tt * ddy
    d = math.hypot(qx - px, qy - py)
    seg_len = math.hypot(ddx, ddy)
    return Projection((px, py), chainages[i] + tt * seg_len, d)


def nearest_point_on_alignment(points: Sequence[Point], query: Point) -> Projection:
    """Project query onto the polyline; return closest point + chainage."""
    qx, qy = query[0], query[1]
    try:
        n_pts = len(points)
    except TypeError:
        n_pts = 0
    if n_pts >= _NP_MIN_POINTS:
        try:
            key = tuple(points)
        except TypeError:
            key = None
        if key is not None:
            try:
                chainages = _cached_chainages(key)
            except TypeError:
                chainages = None
            if chainages is not None:
                got = _nearest_vectorized(key, qx, qy, chainages)
                if got is not None:
                    return got
    chainages = cumulative_chainages(points)
    best: Projection | None = None

    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-12:
            t = 0.0
        else:
            t = ((query[0] - ax) * dx + (query[1] - ay) * dy) / seg_len_sq
            t = min(max(t, 0.0), 1.0)
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(query[0] - px, query[1] - py)
        seg_len = math.hypot(dx, dy)
        ch = chainages[i] + t * seg_len
        if best is None or d < best.distance:
            best = Projection((px, py), ch, d)

    assert best is not None
    return best


def point_side(sp: StationPoint, other: Point) -> str:
    """Which side (LEFT/RIGHT of travel at sp) is other on?"""
    tx, ty = sp.tangent
    vx, vy = other[0] - sp.point[0], other[1] - sp.point[1]
    return "LEFT" if tx * vy - ty * vx > 0 else "RIGHT"


def rectangle_from_two_offsets(
    near_edge: Sequence[Point], far_edge: Sequence[Point]
) -> List[Point]:
    """Stitch near/far edge polylines into one closed outline."""
    return list(near_edge) + list(reversed(far_edge)) + [near_edge[0]]


def find_straight_window(
    points: Sequence[Point],
    window_length: float,
    preferred_start: float,
    tolerance_degrees: float = 1.0,
) -> float:
    """Find the nearest chainage window whose segments are effectively straight."""
    if len(points) < 2:
        raise ValueError("Track centerline needs at least 2 vertices")
    chainages = cumulative_chainages(points)
    total = chainages[-1]
    if window_length <= 0 or window_length > total:
        raise ValueError(
            f"Platform length {window_length:.3f} is outside the track extent [0, {total:.3f}]"
        )
    tolerance = math.radians(tolerance_degrees)
    preferred_start = min(max(preferred_start, 0.0), total - window_length)
    candidates = {0.0, total - window_length, preferred_start}
    candidates.update(
        max(0.0, min(chainage, total - window_length)) for chainage in chainages
    )

    def angle_difference(first: Point, second: Point) -> float:
        return abs(
            math.atan2(
                first[0] * second[1] - first[1] * second[0],
                first[0] * second[0] + first[1] * second[1],
            )
        )

    valid = []
    for start in candidates:
        end = start + window_length
        directions = []
        for index in range(len(points) - 1):
            seg_start = chainages[index]
            seg_end = chainages[index + 1]
            if max(start, seg_start) < min(end, seg_end) - 1e-6 or (start <= (seg_start + seg_end) / 2.0 <= end):
                dx = points[index + 1][0] - points[index][0]
                dy = points[index + 1][1] - points[index][1]
                seg_len = math.hypot(dx, dy)
                if seg_len > 1e-9:
                    directions.append((dx / seg_len, dy / seg_len))
        if directions and all(
            angle_difference(directions[0], d) <= tolerance for d in directions[1:]
        ):
            valid.append((abs(start - preferred_start), start))
    if not valid:
        raise ValueError(
            f"No straight track section of {window_length:.3f} m found near chainage "
            f"{preferred_start + window_length / 2.0:.3f} m"
        )
    return min(valid)[1]


def validate_straight_interval(
    points: Sequence[Point],
    start_chainage: float,
    end_chainage: float,
    tolerance_degrees: float = 1.0,
    track_name: str = "track",
) -> dict[str, float]:
    """Validate one fixed platform interval without moving its requested centre.

    Survey alignments often contain many short segments with harmless bearing
    noise.  Measure their perpendicular deviation from the interval chord
    instead of requiring every segment to exactly match the first segment.
    """
    if len(points) < 2:
        raise ValueError(f"Track {track_name!r} needs at least 2 vertices")
    chainages = cumulative_chainages(points)
    total = chainages[-1]
    start = float(start_chainage)
    end = float(end_chainage)
    if start < -1e-6 or end > total + 1e-6 or end <= start:
        raise ValueError(
            f"Platform interval [{start:.3f}, {end:.3f}] m on {track_name} "
            f"is outside track extent [0, {total:.3f}] m"
        )
    start = max(0.0, start)
    end = min(total, end)
    start_point = point_at_chainage(points, start).point
    end_point = point_at_chainage(points, end).point
    interval_points = [start_point]
    interval_points.extend(
        point for point, chainage in zip(points, chainages)
        if start < chainage < end
    )
    interval_points.append(end_point)

    dx = end_point[0] - start_point[0]
    dy = end_point[1] - start_point[1]
    chord = math.hypot(dx, dy)
    if chord <= 1e-9:
        raise ValueError(
            f"Platform interval [{start:.3f}, {end:.3f}] m on {track_name} "
            "has coincident endpoints"
        )
    max_deviation = max(
        abs(dx * (point[1] - start_point[1]) - dy * (point[0] - start_point[0])) / chord
        for point in interval_points
    )
    length = end - start
    tolerance = max(0.0, float(tolerance_degrees))
    # Equivalent sagitta allowance for a gentle change of bearing, plus a
    # small survey-coordinate floor for dense KML polylines.
    allowed_deviation = max(0.25, length * math.tan(math.radians(tolerance)) / 8.0)
    report = {
        "start_chainage": start,
        "end_chainage": end,
        "length": length,
        "chord_length": chord,
        "max_deviation": max_deviation,
        "allowed_deviation": allowed_deviation,
    }
    if max_deviation > allowed_deviation + 1e-9:
        raise ValueError(
            f"Platform on {track_name} cannot use fixed interval "
            f"[{start:.3f}, {end:.3f}] m (centre {(start + end) / 2.0:.3f} m): "
            f"maximum alignment deviation is {max_deviation:.3f} m; "
            f"allowed is {allowed_deviation:.3f} m at {tolerance:.3f} deg tolerance"
        )
    return report
