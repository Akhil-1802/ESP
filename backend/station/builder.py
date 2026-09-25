"""Generate a station-building footprint centered on a platform polygon."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from common.geometry import distance as _distance, readable_angle_deg as _readable_angle

Point = Tuple[float, float]


@dataclass
class StationBuilding:
    outline: List[Point]
    center: Point
    angle: float


def _center(points: Sequence[Point]) -> Point:
    signed_area = sum(first[0] * second[1] - second[0] * first[1]
                      for first, second in zip(points, points[1:] + points[:1]))
    if abs(signed_area) < 1e-9:
        return (sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points))
    x = sum((first[0] + second[0]) * (first[0] * second[1] - second[0] * first[1])
            for first, second in zip(points, points[1:] + points[:1]))
    y = sum((first[1] + second[1]) * (first[0] * second[1] - second[0] * first[1])
            for first, second in zip(points, points[1:] + points[:1]))
    return (x / (3.0 * signed_area), y / (3.0 * signed_area))


def _polygon_area(points: Sequence[Point]) -> float:
    return abs(sum(first[0] * second[1] - second[0] * first[1]
                   for first, second in zip(points, points[1:] + points[:1]))) / 2.0


def _building_from_platform(
    platform: Sequence[Point], length: float, width: float, platform_side: str
) -> StationBuilding:
    if length <= 0 or width <= 0:
        raise ValueError("Building length and width must be greater than zero")
    if platform_side.upper() not in {"LEFT", "RIGHT"}:
        raise ValueError("Platform side must be LEFT or RIGHT")
    edges = list(zip(platform, platform[1:]))
    longest = max(_distance(*pair) for pair in edges)
    long_edges = [pair for pair in edges if _distance(*pair) >= longest * 0.9]
    tx, ty = long_edges[0][1][0] - long_edges[0][0][0], long_edges[0][1][1] - long_edges[0][0][1]
    tl = math.hypot(tx, ty) or 1.0
    tx, ty = tx / tl, ty / tl
    platform_center = _center(platform)

    want_left = platform_side.upper() == "LEFT"

    def _side_score(pair) -> float:
        mx = (pair[0][0] + pair[1][0]) / 2.0 - platform_center[0]
        my = (pair[0][1] + pair[1][1]) / 2.0 - platform_center[1]
        return tx * my - ty * mx

    left_edges = [pair for pair in long_edges if _side_score(pair) > 0]
    right_edges = [pair for pair in long_edges if _side_score(pair) <= 0]
    pool = left_edges if want_left else right_edges
    edge = pool[0] if pool else long_edges[0]
    dx, dy = edge[1][0] - edge[0][0], edge[1][1] - edge[0][1]
    edge_length = math.hypot(dx, dy) or 1.0
    along = (dx / edge_length, dy / edge_length)
    across = (-along[1], along[0])
    edge_center = ((edge[0][0] + edge[1][0]) / 2.0, (edge[0][1] + edge[1][1]) / 2.0)
    if ((platform_center[0] - edge_center[0]) * across[0] +
            (platform_center[1] - edge_center[1]) * across[1]) > 0:
        across = (-across[0], -across[1])
    if length > edge_length:
        raise ValueError(
            f"Building ({length:g}m x {width:g}m) must fit inside the platform "
            f"length ({edge_length:.2f}m)"
        )
    center = (edge_center[0] + across[0] * width / 2.0,
              edge_center[1] + across[1] * width / 2.0)
    half_length, half_width = length / 2.0, width / 2.0
    corners = [
        (center[0] - along[0] * half_length - across[0] * half_width,
         center[1] - along[1] * half_length - across[1] * half_width),
        (center[0] + along[0] * half_length - across[0] * half_width,
         center[1] + along[1] * half_length - across[1] * half_width),
        (center[0] + along[0] * half_length + across[0] * half_width,
         center[1] + along[1] * half_length + across[1] * half_width),
        (center[0] - along[0] * half_length + across[0] * half_width,
         center[1] - along[1] * half_length + across[1] * half_width),
    ]
    return StationBuilding(corners, center, _readable_angle(math.degrees(math.atan2(dy, dx))))
