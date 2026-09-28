"""Perpendicular offset geometry calculations for straight and curved alignments."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Point = Tuple[float, float]


def compute_perpendicular_offset(
    points: Sequence[Point],
    spacing: float,
    side: str = "LEFT",
) -> List[Point]:
    """Compute a parallel track alignment offset perpendicularly along local tangents.

    Works accurately on both straight and curved alignments by computing the
    local tangent and perpendicular normal vector at each vertex, avoiding
    naive fixed X/Y coordinate shifts.

    Args:
        points: Source track centerline coordinates [(x, y), ...].
        spacing: Perpendicular distance in metres (> 0).
        side: "LEFT" or "RIGHT" relative to direction of travel.

    Returns:
        Offset polyline coordinates [(x, y), ...].
    """
    if spacing <= 0:
        raise ValueError(f"Spacing must be greater than zero, got {spacing}.")
    if len(points) < 2:
        raise ValueError("The reference track must contain at least two points.")

    sign = 1.0 if side.upper() == "LEFT" else -1.0
    result: List[Point] = []
    n = len(points)

    for index in range(n):
        point = points[index]
        if index == 0:
            tangent = (points[1][0] - point[0], points[1][1] - point[1])
        elif index == n - 1:
            tangent = (point[0] - points[index - 1][0], point[1] - points[index - 1][1])
        else:
            tangent = (points[index + 1][0] - points[index - 1][0], points[index + 1][1] - points[index - 1][1])

        length = math.hypot(tangent[0], tangent[1]) or 1.0
        # Normal vector: 90 deg left is (-ty, tx), 90 deg right is (ty, -tx)
        nx = -sign * tangent[1] / length
        ny = sign * tangent[0] / length

        result.append((
            point[0] + nx * spacing,
            point[1] + ny * spacing,
        ))

    return result
