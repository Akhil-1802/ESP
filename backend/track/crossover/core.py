"""ESP crossover calculations and coordinate generation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from common.constants import (
    F_DIAG_TOLERANCE_DEG as STANDARD_F_DIAG_TOLERANCE_DEG,
    MAX_VERTEX_GAP_M as STANDARD_MAX_VERTEX_GAP_M,
    MM_PER_UNIT,
    PARALLEL_TOLERANCE_DEGREES,
)
from common.geometry import (
    Point,
    angle_between as _angle_between,
    nearest_point_on_alignment,
    point_at_chainage,
    polyline_length,
    rotate as _rotate,
    unit as _unit,
)
from track.crossover.reverse_curve import _build_reverse_curve_crossover
from track.crossover.turnout import (
    _sample_spline,
    _sample_tangent,
    turnout_ratio_n,
)
from track.turnouts import (
    BG_1_12_LEAD_RADIUS_M,
    BG_1_12_LEAD_RADIUS_MM,
    BG_1_8_5_LEAD_RADIUS_M,
    BG_1_8_5_LEAD_RADIUS_MM,
    NORMAL_SPACING_LIMIT_MM,
    TurnoutParameters,
)
from track.crossover.core_build import build_standard_crossover  # noqa: F401 re-export

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
    candidates = []
    for first, second in zip(points, points[1:]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        ratio = ((query[0] - first[0]) * dx + (query[1] - first[1]) * dy) / (dx * dx + dy * dy or 1.0)
        ratio = min(max(ratio, 0.0), 1.0)
        candidate = (first[0] + ratio * dx, first[1] + ratio * dy)
        candidates.append((math.hypot(query[0] - candidate[0], query[1] - candidate[1]), candidate))
    if not candidates:
        raise ValueError("Selected track centerline needs at least two points")
    return min(candidates)[1]


def centerline_distance_mm(from_points: Sequence[Point], to_points: Sequence[Point]) -> float:
    _, direction = _track_frame(from_points)
    _, target_direction = _track_frame(to_points)
    angle = abs(
        math.atan2(
            direction[0] * target_direction[1] - direction[1] * target_direction[0],
            direction[0] * target_direction[0] + direction[1] * target_direction[1],
        )
    )
    if angle > math.radians(PARALLEL_TOLERANCE_DEGREES):
        raise ValueError("Crossover selection requires locally parallel track centerlines")
    origin = _midpoint(from_points)
    target = _nearest_point(to_points, origin)
    distance = abs((target[0] - origin[0]) * (-direction[1]) + (target[1] - origin[1]) * direction[0])
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


def _point_at_chainage(points: Sequence[Point], chainage_m: float) -> Point:
    if chainage_m < 0 or chainage_m > _polyline_length(points):
        raise ValueError("Crossover connection point lies outside the selected track")
    travelled = 0.0
    for first, second in zip(points, points[1:]):
        length = math.hypot(second[0] - first[0], second[1] - first[1])
        if travelled + length >= chainage_m:
            ratio = (chainage_m - travelled) / (length or 1.0)
            return (first[0] + ratio * (second[0] - first[0]), first[1] + ratio * (second[1] - first[1]))
        travelled += length
    return points[-1]


def generate_crossover_coordinates(
    geometry: CrossoverGeometry,
    from_points: Sequence[Point],
    to_points: Sequence[Point],
    center_chainage_m: float | None = None,
    from_center_chainage_m: float | None = None,
    to_center_chainage_m: float | None = None,
    from_endpoint_chainage_m: float | None = None,
    to_endpoint_chainage_m: float | None = None,
) -> list[Point]:
    """Build an ESP crossover as two mirror turnouts with a connecting element."""
    direction = _track_frame(from_points)[1]
    target_direction = _track_frame(to_points)[1]
    alignment = (
        direction
        if direction[0] * target_direction[0] + direction[1] * target_direction[1] >= 0
        else (-direction[0], -direction[1])
    )
    normal = (-direction[1], direction[0])
    from_mid = _midpoint(from_points)
    to_mid = _nearest_point(to_points, from_mid)
    signed_distance = (
        (to_mid[0] - from_mid[0]) * normal[0] + (to_mid[1] - from_mid[1]) * normal[1]
    ) * MM_PER_UNIT
    if signed_distance < 0:
        normal = (-normal[0], -normal[1])
    common_length_m = min(_polyline_length(from_points), _polyline_length(to_points))
    half_x = geometry.horizontal_distance_mm / 2
    center_m = common_length_m / 2 if center_chainage_m is None else center_chainage_m
    from_center = center_m if from_center_chainage_m is None else from_center_chainage_m
    to_center = center_m if to_center_chainage_m is None else to_center_chainage_m
    start = _point_at_chainage(
        from_points,
        from_endpoint_chainage_m if from_endpoint_chainage_m is not None else from_center - half_x / MM_PER_UNIT,
    )
    end = _point_at_chainage(
        to_points,
        to_endpoint_chainage_m if to_endpoint_chainage_m is not None else to_center + half_x / MM_PER_UNIT,
    )

    crossing_angle = geometry.turnout.crossing_angle_rad
    assert crossing_angle is not None
    f = crossing_angle
    half_x_m = half_x / MM_PER_UNIT

    if geometry.crossover_type == "large_spacing_reverse_curves":
        theta = geometry.theta_rad or 0.0
        radius_m = (geometry.turnout.radius_mm or 0.0) / MM_PER_UNIT
        tangent_m = (geometry.tangent_mm or 0.0) / MM_PER_UNIT
        b_m = geometry.turnout.b_mm / MM_PER_UNIT
        a_m = geometry.turnout.a_mm / MM_PER_UNIT
        return _build_reverse_curve_crossover(
            start, end, alignment, normal,
            a_m=a_m, b_m=b_m, radius_m=radius_m, theta=theta, tangent_m=tangent_m,
        )

    default_r_mm = (
        BG_1_8_5_LEAD_RADIUS_MM
        if getattr(geometry.turnout, "designation", "") == "1:8.5"
        else BG_1_12_LEAD_RADIUS_MM
    )
    radius_m = (geometry.turnout.radius_mm or default_r_mm) / MM_PER_UNIT
    b_m = geometry.turnout.b_mm / MM_PER_UNIT
    a_m = geometry.turnout.a_mm / MM_PER_UNIT
    return _build_normal_crossover(
        start, end, alignment, normal,
        half_x_m=half_x_m, radius_m=radius_m, b_m=b_m, a_m=a_m, f=f,
    )


def _build_normal_crossover(
    start: Point,
    end: Point,
    alignment: Point,
    normal: Point,
    half_x_m: float,
    radius_m: float,
    b_m: float,
    a_m: float,
    f: float,
) -> list[Point]:
    """Build a normal-spacing ESP crossover from two mirror turnouts."""
    points: list[Point] = [start]
    pts_a1 = _sample_tangent(start, alignment, a_m)
    points.extend(pts_a1[1:])
    toe1 = pts_a1[-1]

    curve_target_dir = _rotate(alignment, f)
    arc1_samples = _sample_spline(toe1, alignment, curve_target_dir, radius_m, f, samples=128)
    points.extend(arc1_samples[1:])
    heel1 = arc1_samples[-1]
    heel1_dir = curve_target_dir

    pts_b1 = _sample_tangent(heel1, heel1_dir, b_m)
    points.extend(pts_b1[1:])
    mid_in = pts_b1[-1]

    offset_across = 2.0 * b_m * math.sin(f)
    mid_out = (mid_in[0] + normal[0] * offset_across, mid_in[1] + normal[1] * offset_across)
    heel2 = (mid_out[0] - curve_target_dir[0] * b_m, mid_out[1] - curve_target_dir[1] * b_m)
    heel2_dir = curve_target_dir

    arc2_samples = _sample_spline(heel2, heel2_dir, alignment, radius_m, f, samples=128)
    points.extend(arc2_samples[1:])
    toe2 = arc2_samples[-1]

    pts_a2 = _sample_tangent(toe2, alignment, a_m)
    points.extend(pts_a2[1:])

    if points:
        points[-1] = end
    return points


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


def local_track_spacing_mm(
    from_pt: Point,
    from_tangent: Point,
    to_points: Sequence[Point],
) -> dict:
    """Measure the actual centre-to-centre spacing at a track point."""
    proj = nearest_point_on_alignment(to_points, from_pt)
    tc_m = proj.distance
    if not math.isfinite(tc_m) or tc_m <= 1e-9:
        raise ValueError("FROM and TO tracks coincide at the START SRJ - need two distinct parallel tracks.")
    tx, ty = from_tangent
    n = math.hypot(tx, ty) or 1.0
    tx, ty = tx / n, ty / n
    vx, vy = proj.point[0] - from_pt[0], proj.point[1] - from_pt[1]
    side = "LEFT" if tx * vy - ty * vx > 0 else "RIGHT"
    return {
        "tc_mm": tc_m * MM_PER_UNIT,
        "nearest_pt": proj.point,
        "nearest_chainage_m": proj.chainage,
        "side": side,
    }



__all__ = [
    "CrossoverGeometry",
    "STANDARD_F_DIAG_TOLERANCE_DEG",
    "STANDARD_MAX_VERTEX_GAP_M",
    "STANDARD_PARALLEL_TOLERANCE_DEG",
    "_build_normal_crossover",
    "_build_reverse_curve_crossover",
    "build_standard_crossover",
    "calculate_crossover",
    "centerline_distance_mm",
    "generate_crossover_coordinates",
    "local_track_spacing_mm",
    "standard_crossover_lengths",
]