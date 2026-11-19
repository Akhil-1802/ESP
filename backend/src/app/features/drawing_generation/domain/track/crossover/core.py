"""ESP crossover calculations and coordinate generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ...constants import F_DIAG_TOLERANCE_DEG as STANDARD_F_DIAG_TOLERANCE_DEG
from ...constants import MAX_VERTEX_GAP_M as STANDARD_MAX_VERTEX_GAP_M
from ...constants import MM_PER_UNIT, PARALLEL_TOLERANCE_DEGREES
from ...geometry.operations import Point
from ..turnouts import (
    NORMAL_SPACING_LIMIT_MM,
    TurnoutParameters,
)
from .core_build import build_standard_crossover
from .reverse_curve import _build_reverse_curve_crossover
from .turnout import turnout_ratio_n

STANDARD_PARALLEL_TOLERANCE_DEG = PARALLEL_TOLERANCE_DEGREES


@dataclass(frozen=True)
class CrossoverGeometry:
    from_track: str
    to_track: str
    turnout: TurnoutParameters
    distance_mm: float
    crossover_type: str
    separation_mm: float | None
    horizontal_distance_mm: float
    overall_length_mm: float
    theta_rad: float | None = None
    tangent_mm: float | None = None


def _require_geometry_parameters(turnout: TurnoutParameters, large_spacing: bool) -> None:
    missing = []
    if turnout.crossing_angle_rad is None:
        missing.append("crossing_angle_rad (F)")
    if large_spacing and turnout.radius_mm is None:
        missing.append("radius_mm (R)")
    if missing:
        raise ValueError(
            f"Turnout {turnout.designation}/{turnout.variant} is missing {', '.join(missing)} "
            "from the applicable ESP turnout drawing; no engineering value was assumed."
        )


def _track_frame(points: Sequence[Point]) -> tuple[Point, Point]:
    if len(points) < 2:
        raise ValueError("Selected track must contain at least two points")
    dx = points[-1][0] - points[0][0]
    dy = points[-1][1] - points[0][1]
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("Selected track has zero length")
    return points[0], (dx / length, dy / length)


def _midpoint(points: Sequence[Point]) -> Point:
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
    target = sum(lengths) / 2.0
    travelled = 0.0
    for first, second, length in zip(points, points[1:], lengths):
        if travelled + length >= target:
            ratio = (target - travelled) / (length or 1.0)
            return (first[0] + ratio * (second[0] - first[0]), first[1] + ratio * (second[1] - first[1]))
        travelled += length
    return points[-1]


def _polyline_length(points: Sequence[Point]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def _nearest_point(points: Sequence[Point], query: Point) -> Point:
    return _nearest_segment_and_point(points, query)[0]


def _nearest_segment_and_point(
    points: Sequence[Point], query: Point
) -> tuple[Point, tuple[float, float], float]:
    """Find nearest point on a polyline to query, returning (nearest_point, segment_direction, distance)."""
    candidates = []
    for first, second in zip(points, points[1:]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-9:
            continue
        ratio = ((query[0] - first[0]) * dx + (query[1] - first[1]) * dy) / (seg_len * seg_len)
        ratio = min(max(ratio, 0.0), 1.0)
        cand = (first[0] + ratio * dx, first[1] + ratio * dy)
        d = math.hypot(query[0] - cand[0], query[1] - cand[1])
        candidates.append((d, cand, (dx / seg_len, dy / seg_len)))
    if not candidates:
        raise ValueError("Selected track centerline needs at least two points")
    best_dist, best_pt, best_dir = min(candidates, key=lambda c: c[0])
    return best_pt, best_dir, best_dist


def centerline_distance_mm(from_points: Sequence[Point], to_points: Sequence[Point]) -> float:
    if len(from_points) < 2 or len(to_points) < 2:
        raise ValueError("Selected track must contain at least two points")

    len_from = _polyline_length(from_points)
    len_to = _polyline_length(to_points)

    # Use the midpoint of the shorter polyline to evaluate local parallelism & distance
    if len_to <= len_from:
        mid = _midpoint(to_points)
        _, dir_to, _ = _nearest_segment_and_point(to_points, mid)
        target, dir_from, _ = _nearest_segment_and_point(from_points, mid)
    else:
        mid = _midpoint(from_points)
        _, dir_from, _ = _nearest_segment_and_point(from_points, mid)
        target, dir_to, _ = _nearest_segment_and_point(to_points, mid)

    # Compute unoriented angle between the two local tangents
    cos_angle = abs(dir_from[0] * dir_to[0] + dir_from[1] * dir_to[1])
    sin_angle = abs(dir_from[0] * dir_to[1] - dir_from[1] * dir_to[0])
    angle = math.atan2(sin_angle, cos_angle)

    if angle > math.radians(PARALLEL_TOLERANCE_DEGREES):
        raise ValueError("Crossover selection requires locally parallel track centerlines")

    distance = abs((target[0] - mid[0]) * (-dir_from[1]) + (target[1] - mid[1]) * dir_from[0])
    if distance <= 1e-9:
        distance = math.hypot(target[0] - mid[0], target[1] - mid[1])
    distance_mm = distance * MM_PER_UNIT
    if distance_mm <= 0:
        raise ValueError("Selected track centerlines must have a positive separation")
    return distance_mm


def calculate_crossover(
    from_track: str,
    to_track: str,
    from_points: Sequence[Point],
    to_points: Sequence[Point],
    turnout: TurnoutParameters,
) -> CrossoverGeometry:
    distance_mm = centerline_distance_mm(from_points, to_points)
    large_spacing = distance_mm > NORMAL_SPACING_LIMIT_MM
    _require_geometry_parameters(turnout, large_spacing)
    f = turnout.crossing_angle_rad
    assert f is not None
    if not 0 < f < math.pi / 2:
        raise ValueError("Turnout crossing angle F must be between 0 and 90 degrees")
    a, b = turnout.a_mm, turnout.b_mm
    if large_spacing:
        radius = turnout.radius_mm
        assert radius is not None
        argument = (radius * math.cos(f) + b * math.sin(f) - distance_mm / 2) / radius
        if not -1 <= argument <= 1:
            raise ValueError("Selected turnout and track spacing produce an invalid reverse-curve angle")
        theta = math.acos(argument)
        tangent = radius * math.tan((theta - f) / 2)
        x = 2 * ((b + tangent) * math.cos(f) + tangent * math.cos(theta))
        if tangent < 0 or x <= 0:
            raise ValueError("Selected turnout and track spacing produce invalid reverse-curve lengths")
        return CrossoverGeometry(
            from_track, to_track, turnout, distance_mm, "large_spacing_reverse_curves", None, x, x + 2 * a, theta, tangent
        )
    separation = distance_mm / math.sin(f) - 2 * b
    x = distance_mm / math.tan(f)
    if separation <= 0 or x <= 0:
        raise ValueError("Selected turnout and track spacing produce invalid normal crossover lengths")
    return CrossoverGeometry(from_track, to_track, turnout, distance_mm, "normal_spacing", separation, x, x + 2 * a)


def standard_crossover_lengths(tc_mm: float, turnout: TurnoutParameters) -> dict:
    """Apply OL = TC * N + 2 * A for the given spacing and turnout."""
    if not math.isfinite(tc_mm) or tc_mm <= 0:
        raise ValueError(f"Track centre spacing TC must be positive, got {tc_mm!r} mm.")
    n = turnout_ratio_n(turnout)
    a = turnout.a_mm
    if not math.isfinite(a) or a <= 0:
        raise ValueError(f"Turnout {turnout.designation} has invalid A dimension {a!r} mm.")
    f = math.atan(1.0 / n)
    x = tc_mm * n
    ol = x + 2.0 * a
    stored_f_deg = (
        math.degrees(turnout.crossing_angle_rad)
        if turnout.crossing_angle_rad is not None
        else None
    )
    f_deg = math.degrees(f)
    mismatch = stored_f_deg is not None and abs(stored_f_deg - f_deg) > 0.01
    return {
        "tc_mm": tc_mm,
        "n": n,
        "a_mm": a,
        "f_rad": f,
        "f_deg": f_deg,
        "x_mm": x,
        "ol_mm": ol,
        "stored_f_deg": stored_f_deg,
        "stored_f_mismatch": mismatch,
    }


__all__ = [
    "CrossoverGeometry",
    "STANDARD_F_DIAG_TOLERANCE_DEG",
    "STANDARD_MAX_VERTEX_GAP_M",
    "STANDARD_PARALLEL_TOLERANCE_DEG",
    "_build_reverse_curve_crossover",
    "build_standard_crossover",
    "calculate_crossover",
    "centerline_distance_mm",
    "standard_crossover_lengths",
]
