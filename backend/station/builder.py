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
    if not edges:
        raise ValueError("Platform must have at least 3 vertices")

    # Longitudinal platform direction from longest edge, consistently pointing forward (+X)
    longest_edge = max(edges, key=lambda pair: _distance(*pair))
    dx = longest_edge[1][0] - longest_edge[0][0]
    dy = longest_edge[1][1] - longest_edge[0][1]
    tl = math.hypot(dx, dy) or 1.0
    tx, ty = dx / tl, dy / tl
    if tx < 0 or (abs(tx) < 1e-6 and ty < 0):
        tx, ty = -tx, -ty

    along = (tx, ty)
    want_left = platform_side.upper() == "LEFT"
    across = (-ty, tx) if want_left else (ty, -tx)

    platform_center = _center(platform)
    p_proj_s = [p[0] * tx + p[1] * ty for p in platform]
    s_min, s_max = min(p_proj_s), max(p_proj_s)
    total_plat_len = s_max - s_min
    if length > total_plat_len + 1e-3:
        raise ValueError(
            f"Building ({length:g}m x {width:g}m) must fit inside the platform "
            f"length ({total_plat_len:.2f}m)"
        )

    s_center = (s_min + s_max) / 2.0

    # Collect edges on the requested platform_side that run parallel to the platform axis
    outer_edges = []
    for p1, p2 in edges:
        edx = p2[0] - p1[0]
        edy = p2[1] - p1[1]
        el = math.hypot(edx, edy)
        if el < 0.1:
            continue
        if abs(edx * tx + edy * ty) / el > 0.8:
            emx = (p1[0] + p2[0]) / 2.0
            emy = (p1[1] + p2[1]) / 2.0
            rx = emx - platform_center[0]
            ry = emy - platform_center[1]
            if (rx * across[0] + ry * across[1]) > 0:
                s1 = p1[0] * tx + p1[1] * ty
                s2 = p2[0] * tx + p2[1] * ty
                trans = emx * across[0] + emy * across[1]
                outer_edges.append((min(s1, s2), max(s1, s2), trans, el))

    covering = [e for e in outer_edges if e[0] - 1.0 <= s_center <= e[1] + 1.0]
    if covering:
        best_edge = max(covering, key=lambda e: e[3])
    elif outer_edges:
        best_edge = min(outer_edges, key=lambda e: min(abs(e[0] - s_center), abs(e[1] - s_center)))
    else:
        best_edge = (s_min, s_max, platform_center[0] * across[0] + platform_center[1] * across[1], total_plat_len)

    edge_transverse = best_edge[2]
    center_transverse = edge_transverse + width / 2.0

    center = (
        tx * s_center + across[0] * center_transverse,
        ty * s_center + across[1] * center_transverse,
    )
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
    return StationBuilding(corners, center, _readable_angle(math.degrees(math.atan2(ty, tx))))
