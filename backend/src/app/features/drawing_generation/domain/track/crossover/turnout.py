"""Turnout geometry: sampling helpers + standalone turnout builder.

Builds one turnout from real ESP pieces (tangent straights + R arcs at F)
and samples centrelines; crossover/loop/siding builders compose these.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

from ...constants import MM_PER_UNIT
from ...geometry.operations import Point
from ...geometry.operations import rotate as _rotate
from ..turnouts import (
    BG_1_8_5_LEAD_RADIUS_MM,
    BG_1_12_LEAD_RADIUS_MM,
    TurnoutParameters,
    require_geometry_parameters,
)

__all__ = [
    "TurnoutGeometry",
    "TurnoutResult",
    "_sample_arc",
    "_sample_spline",
    "_sample_tangent",
    "generate_turnout",
    "transform_turnout_to_global",
    "turnout_ratio_n",
]

SPLINE_FULLNESS: float = 1.0


def _sample_spline(
    start: Point,
    start_dir: Point,
    end_dir: Point,
    radius: float,
    sweep: float,
    samples: int = 128,
    end: Point | None = None,
    fullness: float | None = None,
) -> list[Point]:
    """Sample a smooth transition spline curve with gradually changing curvature."""
    sweep = abs(sweep)
    if radius <= 0 or sweep <= 1e-9 or samples < 2:
        return [start, end] if end is not None else [start]

    if fullness is None:
        fullness = SPLINE_FULLNESS
    fullness = max(1.0, min(float(fullness), 1.6))

    tan_half = math.tan(sweep / 2.0)
    T = radius * tan_half
    C = (start[0] + start_dir[0] * T, start[1] + start_dir[1] * T)
    P1 = end if end is not None else (C[0] + end_dir[0] * T, C[1] + end_dir[1] * T)

    d_arc = radius * (1.0 / math.cos(sweep / 2.0) - 1.0)
    sin_half = math.sin(sweep / 2.0)
    K = 16.0 * d_arc / sin_half if sin_half > 1e-9 else 8.0 * T
    w1 = (16.0 * T - K) / 25.0 * fullness
    w2 = 2.0 * w1
    if T > 1e-9:
        w2 = min(w2, 0.95 * T)
        w1 = w2 / 2.0

    B0 = start
    B1 = (start[0] + w1 * start_dir[0], start[1] + w1 * start_dir[1])
    B2 = (start[0] + w2 * start_dir[0], start[1] + w2 * start_dir[1])
    B3 = (P1[0] - w2 * end_dir[0], P1[1] - w2 * end_dir[1])
    B4 = (P1[0] - w1 * end_dir[0], P1[1] - w1 * end_dir[1])
    B5 = P1

    pts: list[Point] = []
    for i in range(samples + 1):
        t = i / float(samples)
        p = [B0, B1, B2, B3, B4, B5]
        for r in range(1, 6):
            p = [
                (
                    (1.0 - t) * p[j][0] + t * p[j + 1][0],
                    (1.0 - t) * p[j][1] + t * p[j + 1][1],
                )
                for j in range(6 - r)
            ]
        pts.append(p[0])
    pts[0] = start
    pts[-1] = P1
    return pts


def _sample_tangent(
    start: Point, direction: Point, length: float, samples: int = 4
) -> list[Point]:
    """Sample points along a straight tangent starting at `start` along `direction`."""
    if length <= 0:
        return [start]
    return [
        (
            start[0] + direction[0] * length * i / samples,
            start[1] + direction[1] * length * i / samples,
        )
        for i in range(samples + 1)
    ]


def _sample_arc(
    start: Point,
    start_dir: Point,
    end_dir: Point,
    radius: float,
    sweep: float,
    samples: int,
) -> list[Point]:
    """Sample a circular arc from `start` (tangent `start_dir`) to a point whose tangent is `end_dir`."""
    if radius <= 0 or samples < 2:
        return [start]
    nx, ny = -start_dir[1], start_dir[0]
    cross = start_dir[0] * end_dir[1] - start_dir[1] * end_dir[0]
    sign = 1.0 if cross >= 0 else -1.0
    cx = start[0] + sign * nx * radius
    cy = start[1] + sign * ny * radius
    start_angle = math.atan2(start[1] - cy, start[0] - cx)
    return [
        (
            cx + radius * math.cos(start_angle + sweep * sign * i / samples),
            cy + radius * math.sin(start_angle + sweep * sign * i / samples),
        )
        for i in range(samples + 1)
    ]


@dataclass(frozen=True)
class TurnoutGeometry:
    """A single piece of railway geometry: tangent or arc."""

    kind: str  # "tangent" or "arc"
    start: Point
    end: Point
    start_tangent: Point
    end_tangent: Point
    length_m: float
    radius_m: float = 0.0  # 0 for straight tangent


@dataclass(frozen=True)
class TurnoutResult:
    """Structured result of generate_turnout()."""

    spec: TurnoutParameters
    origin: Point
    tangent: Point
    side: str  # "LEFT" or "RIGHT"
    orientation: str  # "forward" (turns toward side) or "reverse"
    pieces: List[TurnoutGeometry] = field(default_factory=list)
    centreline: List[Point] = field(default_factory=list)
    switch_geometry: List[TurnoutGeometry] = field(default_factory=list)
    crossing_geometry: List[TurnoutGeometry] = field(default_factory=list)
    toe: Point = (0.0, 0.0)
    heel: Point = (0.0, 0.0)
    metadata: dict = field(default_factory=dict)


def generate_turnout(
    spec: TurnoutParameters,
    origin: Point,
    tangent: Point,
    side: str,
    orientation: str = "forward",
) -> TurnoutResult:
    """Build a single ESP turnout in local coordinates."""
    require_geometry_parameters(spec)

    tx, ty = tangent

    if orientation == "forward":
        a_vec = (tx, ty)
        f = spec.crossing_angle_rad
    else:
        a_vec = (-tx, -ty)
        f = -spec.crossing_angle_rad

    a_m = spec.a_mm / MM_PER_UNIT
    b_m = spec.b_mm / MM_PER_UNIT
    default_r_mm = (
        BG_1_8_5_LEAD_RADIUS_MM
        if getattr(spec, "designation", "") == "1:8.5"
        else BG_1_12_LEAD_RADIUS_MM
    )
    r_m = (spec.radius_mm or default_r_mm) / MM_PER_UNIT

    pieces: List[TurnoutGeometry] = []
    switch_geometry: List[TurnoutGeometry] = []
    crossing_geometry: List[TurnoutGeometry] = []

    p_toe = origin
    p_after_a = (p_toe[0] + a_vec[0] * a_m, p_toe[1] + a_vec[1] * a_m)
    piece_a = TurnoutGeometry(
        kind="tangent",
        start=p_toe,
        end=p_after_a,
        start_tangent=(tx, ty),
        end_tangent=(tx, ty),
        length_m=a_m,
    )
    pieces.append(piece_a)
    switch_geometry.append(piece_a)

    diag_dir = _rotate((tx, ty), f)
    arc = _sample_spline(p_after_a, (tx, ty), diag_dir, r_m, f, samples=128)
    p_after_arc = arc[-1]
    piece_arc = TurnoutGeometry(
        kind="arc",
        start=p_after_a,
        end=p_after_arc,
        start_tangent=(tx, ty),
        end_tangent=diag_dir,
        length_m=r_m * abs(f),
        radius_m=r_m,
    )
    pieces.append(piece_arc)
    crossing_geometry.append(piece_arc)

    p_heel = (p_after_arc[0] + diag_dir[0] * b_m, p_after_arc[1] + diag_dir[1] * b_m)
    piece_b = TurnoutGeometry(
        kind="tangent",
        start=p_after_arc,
        end=p_heel,
        start_tangent=diag_dir,
        end_tangent=diag_dir,
        length_m=b_m,
    )
    pieces.append(piece_b)
    crossing_geometry.append(piece_b)

    centreline: List[Point] = [p_toe]
    centreline.extend(_sample_tangent(p_toe, a_vec, a_m)[1:])
    centreline.extend(arc[1:])
    centreline.extend(_sample_tangent(p_after_arc, diag_dir, b_m)[1:])

    return TurnoutResult(
        spec=spec,
        origin=origin,
        tangent=tangent,
        side=side.upper(),
        orientation=orientation,
        pieces=pieces,
        centreline=centreline,
        switch_geometry=switch_geometry,
        crossing_geometry=crossing_geometry,
        toe=p_toe,
        heel=p_heel,
        metadata={
            "A_mm": spec.a_mm,
            "B_mm": spec.b_mm,
            "F_deg": math.degrees(spec.crossing_angle_rad or 0.0),
            "beta_deg": math.degrees(spec.switch_angle_rad or 0.0),
            "R_mm": spec.radius_mm,
        },
    )


def transform_turnout_to_global(
    turnout: TurnoutResult,
    frame_origin: Point,
    frame_tangent: Point,
    frame_normal: Point,
) -> TurnoutResult:
    """Transform a turnout built in local coordinates back to global coordinates."""
    def translated(p: Point) -> Point:
        return (p[0] + frame_origin[0], p[1] + frame_origin[1])

    new_centreline = [translated(p) for p in turnout.centreline]
    new_pieces: List[TurnoutGeometry] = []
    for piece in turnout.pieces:
        new_pieces.append(
            TurnoutGeometry(
                kind=piece.kind,
                start=translated(piece.start),
                end=translated(piece.end),
                start_tangent=piece.start_tangent,
                end_tangent=piece.end_tangent,
                length_m=piece.length_m,
                radius_m=piece.radius_m,
            )
        )
    return TurnoutResult(
        spec=turnout.spec,
        origin=translated(turnout.origin),
        tangent=turnout.tangent,
        side=turnout.side,
        orientation=turnout.orientation,
        pieces=new_pieces,
        centreline=new_centreline,
        switch_geometry=[p for p in new_pieces if p in turnout.switch_geometry],
        crossing_geometry=[p for p in new_pieces if p in turnout.crossing_geometry],
        toe=translated(turnout.toe),
        heel=translated(turnout.heel),
        metadata=turnout.metadata,
    )


def turnout_ratio_n(turnout: TurnoutParameters) -> float:
    """Parse the turnout ratio denominator N from the designation."""
    for text in (turnout.designation, turnout.ratio):
        s = (text or "").strip()
        if not s:
            continue
        if ":" in s:
            head, _, tail = s.partition(":")
            try:
                n = float(tail)
            except ValueError:
                continue
        else:
            try:
                n = float(s)
            except ValueError:
                continue
        if n > 0:
            return n
    raise ValueError(
        f"Turnout {turnout.designation!r} has no parseable ratio N "
        f"(designation={turnout.designation!r}, ratio={turnout.ratio!r})."
    )
