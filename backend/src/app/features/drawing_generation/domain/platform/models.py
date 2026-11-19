"""Data structures and types for platform geometry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..geometry.operations import Point


@dataclass
class DimensionSpec:
    """One linear dimension to draw: from p1 to p2, offset sideways by dim_offset."""
    p1: Point
    p2: Point
    dim_offset: float
    text: Optional[str] = None


@dataclass
class LabelSpec:
    """Platform text label."""
    position: Point
    text: str
    height: float
    rotation: float = 0.0


@dataclass
class StairSpec:
    """Platform stair geometry."""
    outline: List[Point]
    tread_lines: List[Tuple[Point, Point]]


@dataclass
class PlatformResult:
    """Concrete 2D platform geometry."""
    outline: List[Point]                  # closed polygon, platform outline
    near_edge: List[Point]                # edge(s) touching the track(s)
    far_edge: List[Point]                 # outer edge (SIDE) / other near edge (ISLAND)

    dimensions: List[DimensionSpec] = field(default_factory=list)
    labels: List[LabelSpec] = field(default_factory=list)
    stairs: List[StairSpec] = field(default_factory=list)

    computed_width: float = 0.0
    computed_length: float = 0.0


def _order_outward(a: Point, b: Point, ox: float, oy: float) -> Tuple[Point, Point]:
    """Order segment (a, b) so that its left-normal (-dy, dx) points in direction (ox, oy)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    if (-dy / length) * ox + (dx / length) * oy < 0:
        return b, a
    return a, b
