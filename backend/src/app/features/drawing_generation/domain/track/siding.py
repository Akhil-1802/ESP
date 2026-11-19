"""Dead-end siding geometry + validation math (single definition).

A siding leaves its source track through ONE turnout (switch at the
start chainage), runs out through a turnout curve + closure straight +
reverse curve to a parallel offset, continues straight for the required
clear standing length, and terminates in a dead end. There is never a
second connection back: this is not a loop or through track.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence

from ..constants import (
    MIN_TRACK_SPACING_M,
    OPPOSITE_DIRECTION_MIN_SEPARATION_M,
    SAME_DIRECTION_MIN_SEPARATION_M,
)
from ..geometry.operations import Point, point_at_chainage, polyline_length
from ..geometry.operations import polygons_overlap as _overlap
from .crossover.turnout import _sample_arc as _arc
from .crossover.turnout import _sample_tangent as _straight
from .crossover.turnout import turnout_ratio_n as _turnout_n
from .turnouts import TurnoutParameters

#: Corridor half-width (m) used when checking the siding footprint
#: against platforms/station buildings: structure gauge 1.68 m + margin.
SIDING_CORRIDOR_HALF_M = 2.5
#: Design tolerance (m) for clearance comparisons.
SIDING_TOL_M = 0.05


@dataclass
class SidingResult:
    """Built centreline for ONE dead-end siding."""

    points: List[Point]
    tip: Point
    tip_tangent: Point
    ladder_length_m: float
    standing_length_m: float
    total_length_m: float
    spacing_m: float
    turnout_label: str


def _rotate(vector: Point, angle_rad: float) -> Point:
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return (
        vector[0] * cos_a - vector[1] * sin_a,
        vector[0] * sin_a + vector[1] * cos_a,
    )


def _unit(vector: Point) -> Point:
    n = math.hypot(vector[0], vector[1]) or 1.0
    return (vector[0] / n, vector[1] / n)


def build_siding_points(
    source_points: Sequence[Point],
    local_start: float,
    direction: str,
    side: str,
    turnout: TurnoutParameters,
    spacing: float,
    standing_length: float,
) -> SidingResult:
    """Build the siding centreline from the turnout switch onwards."""
    direction = str(direction or "").strip().upper()
    if direction not in ("FORWARD", "REVERSE"):
        raise ValueError(
            f"Siding direction must be FORWARD or REVERSE, got {direction!r}."
        )
    side = str(side or "").strip().upper()
    if side not in ("LEFT", "RIGHT"):
        raise ValueError(f"Siding side must be LEFT or RIGHT, got {side!r}.")
    try:
        spacing = float(spacing)
        standing_length = float(standing_length)
    except (TypeError, ValueError):
        raise ValueError("Siding spacing/standing length must be numbers.")
    if spacing <= 0:
        raise ValueError("Siding spacing must be > 0.")
    if standing_length <= 0:
        raise ValueError("Siding standing length must be > 0.")

    station = point_at_chainage(list(source_points), float(local_start))
    ux, uy = _unit(station.tangent)
    travel = (ux, uy) if direction == "FORWARD" else (-ux, -uy)
    side_normal = (-uy, ux) if side == "LEFT" else (uy, -ux)

    if turnout.radius_mm is None or turnout.radius_mm <= 0:
        raise ValueError(
            f"Turnout {turnout.designation!r} has no lead radius - cannot "
            f"build siding curves."
        )
    radius = float(turnout.radius_mm) / 1000.0
    if turnout.crossing_angle_rad:
        angle = float(turnout.crossing_angle_rad)
    else:
        angle = math.atan(1.0 / _turnout_n(turnout))
    if angle <= 0:
        raise ValueError(
            f"Turnout {turnout.designation!r} has no usable crossing angle."
        )

    perp = (-travel[1], travel[0])
    sign = (
        1.0
        if (perp[0] * side_normal[0] + perp[1] * side_normal[1]) >= 0
        else -1.0
    )
    diverging = _rotate(travel, sign * angle)

    sin_f, cos_f = math.sin(angle), math.cos(angle)
    base = 2.0 * radius * (1.0 - cos_f)
    closure = (spacing - base) / sin_f
    if closure < -1e-9:
        raise ValueError(
            f"Siding spacing {spacing:.2f} m is too small for a "
            f"{turnout.designation} ladder (needs >= {base:.2f} m) - "
            f"increase the spacing."
        )
    closure = max(closure, 0.0)

    arc_samples = max(24, int(radius * angle / 0.5) + 1)
    start = (float(station.point[0]), float(station.point[1]))
    arc1 = _arc(start, travel, diverging, radius, angle, arc_samples)
    leg1 = _straight(
        arc1[-1], diverging, closure, max(2, int(closure / 5.0) + 1)
    )
    arc2 = _arc(leg1[-1], diverging, travel, radius, angle, arc_samples)
    leg2 = _straight(
        arc2[-1], travel, standing_length, max(2, int(standing_length / 5.0) + 1)
    )
    points = (
        list(arc1)
        + [p for p in leg1[1:]]
        + [p for p in arc2[1:]]
        + [p for p in leg2[1:]]
    )
    ladder = radius * angle + closure + radius * angle
    return SidingResult(
        points=points,
        tip=points[-1],
        tip_tangent=travel,
        ladder_length_m=ladder,
        standing_length_m=standing_length,
        total_length_m=ladder + standing_length,
        spacing_m=spacing,
        turnout_label=turnout.designation,
    )


def portion_from(points: Sequence[Point], dist: float) -> List[Point]:
    """Centreline subset from arc-length ``dist`` to the tip."""
    pts = [(float(p[0]), float(p[1])) for p in points]
    if dist <= 0:
        return pts
    travelled = 0.0
    for i, (first, second) in enumerate(zip(pts, pts[1:])):
        seg = math.hypot(second[0] - first[0], second[1] - first[1])
        if travelled + seg >= dist:
            ratio = (dist - travelled) / (seg or 1.0)
            cut = (
                first[0] + ratio * (second[0] - first[0]),
                first[1] + ratio * (second[1] - first[1]),
            )
            return [cut] + pts[i + 1 :]
        travelled += seg
    return [pts[-1]]


def _point_seg_dist(point: Point, seg_start: Point, seg_end: Point) -> float:
    dx, dy = seg_end[0] - seg_start[0], seg_end[1] - seg_start[1]
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return math.hypot(point[0] - seg_start[0], point[1] - seg_start[1])
    t = (
        (point[0] - seg_start[0]) * dx + (point[1] - seg_start[1]) * dy
    ) / length_sq
    t = min(max(t, 0.0), 1.0)
    return math.hypot(
        point[0] - (seg_start[0] + t * dx), point[1] - (seg_start[1] + t * dy)
    )


def min_separation(
    a_points: Sequence[Point], b_points: Sequence[Point], step: float = 2.0
) -> float:
    """Minimum point-to-polyline distance sampling ``a`` every ``step`` m."""
    a_pts = [(float(p[0]), float(p[1])) for p in a_points]
    b_pts = [(float(p[0]), float(p[1])) for p in b_points]
    if len(a_pts) < 2 or len(b_pts) < 1:
        raise ValueError("Need at least two points to measure separation.")
    if len(b_pts) < 2:
        segments = [(b_pts[0], b_pts[0])]
    else:
        segments = list(zip(b_pts, b_pts[1:]))
    total = polyline_length(a_pts)
    best = math.inf
    dist = 0.0
    while True:
        probe = point_at_chainage(a_pts, min(dist, total)).point
        for seg_start, seg_end in segments:
            gap = _point_seg_dist(probe, seg_start, seg_end)
            if gap < best:
                best = gap
        if dist >= total:
            break
        dist += step
    return best


def corridor_polygon(points: Sequence[Point], half_width: float) -> List[Point]:
    """Centreline strip polygon (half width each side)."""
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 2:
        raise ValueError("Need at least two points for a corridor.")
    if half_width <= 0:
        raise ValueError("Corridor half width must be > 0.")
    left, right = [], []
    for i, point in enumerate(pts):
        prev = pts[i - 1] if i > 0 else point
        nxt = pts[i + 1] if i < len(pts) - 1 else point
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        left.append((point[0] + nx * half_width, point[1] + ny * half_width))
        right.append((point[0] - nx * half_width, point[1] - ny * half_width))
    return left + right[::-1]





def required_separation(direction_a: str, direction_b: str) -> float:
    """13 m same direction / 54 m opposite (crossover rule, reused)."""
    if str(direction_a).strip().upper() == str(direction_b).strip().upper():
        return SAME_DIRECTION_MIN_SEPARATION_M
    return OPPOSITE_DIRECTION_MIN_SEPARATION_M


def validate_siding(
    sid: str,
    source_track: str,
    start_main: float,
    direction: str,
    result: SidingResult,
    tracks: Dict[str, List[Point]],
    srjs_on_source: Sequence[tuple],
    platform_outlines: Sequence[tuple],
    station_outlines: Sequence[List[Point]],
    other_sidings: Sequence[tuple],
) -> None:
    """Validate one built siding. Raises ValueError on any conflict."""
    direction = str(direction).strip().upper()
    for chainage, other_dir, label in srjs_on_source:
        need = required_separation(direction, other_dir)
        gap = abs(float(start_main) - float(chainage))
        if gap < need - 1e-9:
            raise ValueError(
                f"Siding {sid} turnout at {start_main:.3f} m on "
                f"{source_track} is {gap:.2f} m from {label} "
                f"(needs {need:.0f} m) - move the siding start or resolve "
                f"the conflict. Siding geometry is never moved "
                f"automatically."
            )

    for other_id, other_start, other_dir, _other in other_sidings:
        if other_id is None:
            continue
        need = required_separation(direction, other_dir)
        gap = abs(float(start_main) - float(other_start))
        if gap < need - 1e-9:
            raise ValueError(
                f"Siding {sid} turnout at {start_main:.3f} m on "
                f"{source_track} is {gap:.2f} m from siding "
                f"{other_id} turnout (needs {need:.0f} m) - move one of "
                f"the siding starts. Siding geometry is never moved "
                f"automatically."
            )

    parallel = portion_from(result.points, result.ladder_length_m)
    src_gap = min_separation(parallel, tracks[source_track])
    if src_gap < result.spacing_m - SIDING_TOL_M:
        raise ValueError(
            f"Siding {sid} parallel run is {src_gap:.2f} m from "
            f"{source_track} (expected {result.spacing_m:.2f} m)."
        )

    for name, other_points in tracks.items():
        if name == source_track:
            continue
        gap = min_separation(result.points, other_points)
        if gap < MIN_TRACK_SPACING_M - SIDING_TOL_M:
            raise ValueError(
                f"Siding {sid} passes {gap:.2f} m from {name} (needs "
                f"{MIN_TRACK_SPACING_M:.1f} m) - pick the other side, "
                f"another source track, or another start chainage. "
                f"Siding geometry is never moved automatically."
            )

    for other_id, _start, _dir, other in other_sidings:
        gap = min_separation(result.points, other.points)
        if gap < MIN_TRACK_SPACING_M - SIDING_TOL_M:
            raise ValueError(
                f"Siding {sid} passes {gap:.2f} m from siding {other_id} "
                f"(needs {MIN_TRACK_SPACING_M:.1f} m) - move one of the "
                f"siding starts. Siding geometry is never moved "
                f"automatically."
            )

    corridor = corridor_polygon(result.points, SIDING_CORRIDOR_HALF_M)
    for layer, outline in platform_outlines:
        if _overlap(corridor, outline):
            raise ValueError(
                f"Siding {sid} footprint crosses {layer} - move the "
                f"siding start or resolve the conflict. Siding geometry "
                f"is never moved automatically."
            )
    for outline in station_outlines:
        if _overlap(corridor, outline):
            raise ValueError(
                f"Siding {sid} footprint crosses a station building - "
                f"move the siding start or resolve the conflict. Siding "
                f"geometry is never moved automatically."
            )


__all__ = [
    "SIDING_CORRIDOR_HALF_M",
    "SidingResult",
    "build_siding_points",
    "corridor_polygon",
    "min_separation",
    "portion_from",
    "required_separation",
    "validate_siding",
]
