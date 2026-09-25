"""Loop geometry and 2-turnout loop generation math."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import List, Sequence

from common.constants import MM_PER_UNIT
from common.geometry import (
    Point,
    cumulative_chainages,
    offset_point,
    point_at_chainage,
)
from track.crossover.core import calculate_crossover
from track.crossover.turnout import (
    TurnoutResult,
    generate_turnout,
    transform_turnout_to_global,
)
from track.turnouts import NORMAL_SPACING_LIMIT_MM, TurnoutParameters


def _build_crossover_curve(
    *,
    p_main_start: Point,
    tangent_start: Point,
    p_main_end: Point,
    tangent_end: Point,
    p_loop_start: Point,
    p_loop_end: Point,
    spacing_m: float,
    turnout: TurnoutParameters,
    samples: int = 48,
) -> List[Point]:
    """Straight diagonal between the two offset connection points."""
    return [p_loop_start, p_loop_end]


@dataclass(frozen=True)
class LoopGeometry:
    """Result of generate_loop(): two turnouts + connecting loop alignment."""

    c1: float
    c2: float
    main_points: Sequence[Point]
    loop_points: Sequence[Point]
    turnout_1: TurnoutResult
    turnout_2: TurnoutResult
    d_mm: float
    spacing_classification: str
    crossover_summary: dict
    metadata: dict = field(default_factory=dict)
    loop_c1_point: Point = (0.0, 0.0)
    loop_c2_point: Point = (0.0, 0.0)


def generate_loop(
    main_points: Sequence[Point],
    c1: float,
    c2: float,
    spacing_m: float,
    side: str,
    turnout_spec: TurnoutParameters,
) -> LoopGeometry:
    """Build a complete railway loop connected to MAIN_LINE by two turnouts."""
    if spacing_m <= 0:
        raise ValueError("Loop spacing must be greater than zero")
    if c1 <= 0:
        raise ValueError("First crossover chainage must be > 0")
    if c2 <= c1:
        raise ValueError(
            "Second crossover chainage must be greater than first crossover chainage."
        )
    chainages = cumulative_chainages(main_points)
    total = chainages[-1]
    if c2 > total:
        raise ValueError(
            f"Crossover chainage is outside the available main alignment.\n"
            f"C1: {c1:.1f} m\nC2: {c2:.1f} m\n"
            f"Main line length: {total:.1f} m"
        )

    sp1 = point_at_chainage(main_points, c1)
    sp2 = point_at_chainage(main_points, c2)

    p1 = sp1.point
    p2 = sp2.point
    tangent1 = sp1.tangent
    tangent2 = sp2.tangent

    sp1_offset = offset_point(sp1, spacing_m, side)
    sp2_offset = offset_point(sp2, spacing_m, side)

    interior = [ch for ch in chainages if c1 < ch < c2]
    loop_points = [
        offset_point(point_at_chainage(main_points, ch), spacing_m, side)
        for ch in [c1] + interior + [c2]
    ]

    signed_distance = (
        (sp2_offset[0] - p2[0]) * (-tangent1[1])
        + (sp2_offset[1] - p2[1]) * tangent1[0]
    )
    d_mm = abs(signed_distance) * MM_PER_UNIT
    classification = "normal" if d_mm <= NORMAL_SPACING_LIMIT_MM else "large"

    straight_loop = [sp1_offset, sp2_offset]
    cross_geom = calculate_crossover(
        "MAIN_LINE", "LOOP_LINE", main_points, straight_loop, turnout_spec
    )
    summary = {
        "type": cross_geom.crossover_type,
        "D_mm": cross_geom.distance_mm,
        "A_mm": cross_geom.turnout.a_mm,
        "B_mm": cross_geom.turnout.b_mm,
        "F_deg": math.degrees(cross_geom.turnout.crossing_angle_rad or 0.0),
        "R_mm": cross_geom.turnout.radius_mm,
        "separation_mm": cross_geom.separation_mm,
        "horizontal_mm": cross_geom.horizontal_distance_mm,
        "overall_length_mm": cross_geom.overall_length_mm,
    }
    if cross_geom.theta_rad is not None:
        summary["theta_deg"] = math.degrees(cross_geom.theta_rad)
    if cross_geom.tangent_mm is not None:
        summary["T_mm"] = cross_geom.tangent_mm

    side_sign = "LEFT" if side.upper() == "LEFT" else "RIGHT"

    t1_local = generate_turnout(
        turnout_spec,
        origin=(0.0, 0.0),
        tangent=(1.0, 0.0),
        side=side_sign,
        orientation="forward",
    )
    t1_global = transform_turnout_to_global(
        t1_local,
        frame_origin=p1,
        frame_tangent=tangent1,
        frame_normal=(-tangent1[1], tangent1[0]),
    )

    t2_local = generate_turnout(
        turnout_spec,
        origin=(0.0, 0.0),
        tangent=(1.0, 0.0),
        side=side_sign,
        orientation="reverse",
    )
    t2_global = transform_turnout_to_global(
        t2_local,
        frame_origin=p2,
        frame_tangent=tangent2,
        frame_normal=(-tangent2[1], tangent2[0]),
    )

    return LoopGeometry(
        c1=c1,
        c2=c2,
        main_points=list(main_points),
        loop_points=loop_points,
        turnout_1=t1_global,
        turnout_2=t2_global,
        d_mm=d_mm,
        spacing_classification=classification,
        crossover_summary=summary,
        metadata={
            "spacing_m": spacing_m,
            "side": side_sign,
            "turnout": turnout_spec.designation,
            "variant": turnout_spec.variant,
            "connection_distance_m": c2 - c1,
        },
        loop_c1_point=sp1_offset,
        loop_c2_point=sp2_offset,
    )


__all__ = [
    "LoopGeometry",
    "_build_crossover_curve",
    "generate_loop",
]
