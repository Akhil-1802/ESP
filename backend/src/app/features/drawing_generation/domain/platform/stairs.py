"""Platform stair and arm generation."""

from __future__ import annotations

from typing import List, Tuple

from ..geometry.operations import Point
from .models import StairSpec


def generate_stair(
    platform_start: Point,
    platform_end: Point,
    platform_width: float,
    stair_length: float,
    stair_width: float,
    side: int,
) -> StairSpec:
    """Generate a platform stair at one end of the platform.

    platform_start / platform_end define the longitudinal platform direction.
    side: +1 -> extends forward, -1 -> extends backward.
    """
    if stair_length <= 0:
        raise ValueError("stair_length must be greater than zero")
    if stair_width <= 0:
        raise ValueError("stair_width must be greater than zero")

    dx = platform_end[0] - platform_start[0]
    dy = platform_end[1] - platform_start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        raise ValueError("Platform start and end cannot be identical")

    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux

    if side > 0:
        origin = platform_end
        direction = 1.0
    else:
        origin = platform_start
        direction = -1.0

    ex = ux * stair_length * direction
    ey = uy * stair_length * direction
    hw = stair_width / 2.0

    p1 = (origin[0] - nx * hw, origin[1] - ny * hw)
    p2 = (origin[0] + nx * hw, origin[1] + ny * hw)
    p3 = (p2[0] + ex, p2[1] + ey)
    p4 = (p1[0] + ex, p1[1] + ey)
    outline = [p1, p2, p3, p4, p1]

    tread_spacing = 1.0
    tread_lines: List[Tuple[Point, Point]] = []

    if stair_length > tread_spacing:
        number_of_treads = int(stair_length // tread_spacing)
        for i in range(1, number_of_treads + 1):
            distance = min(i * tread_spacing, stair_length)
            tx = ux * distance * direction
            ty = uy * distance * direction
            left = (origin[0] - nx * hw + tx, origin[1] - ny * hw + ty)
            right = (origin[0] + nx * hw + tx, origin[1] + ny * hw + ty)
            tread_lines.append((left, right))

    return StairSpec(outline=outline, tread_lines=tread_lines)
