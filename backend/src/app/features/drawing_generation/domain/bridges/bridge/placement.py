"""Resolve both bridge placement modes onto the original MAIN alignment."""
from dataclasses import dataclass
import math

from ...geometry.operations import nearest_point_on_alignment, point_at_chainage, polyline_length


from ...geometry.stationing import alignment_start_metres, parse_absolute_chainage


@dataclass(frozen=True)
class BridgePlacement:
    distance: float
    absolute_chainage: float
    point: tuple
    tangent: tuple


def resolve_bridge_placement(cfg, config, tracks) -> BridgePlacement:
    points = tracks.get("MAIN_LINE")
    if points is None or len(points) < 2:
        raise ValueError("Bridge requires a usable MAIN_LINE alignment.")
    start = alignment_start_metres(config)
    if cfg.position_mode == "FIXED":
        distance = parse_absolute_chainage(cfg.chainage) - start
    else:
        stations = config.stations or []
        if cfg.station_index >= len(stations):
            raise ValueError(f"Bridge {cfg.id}: selected station building is unavailable.")
        outline = getattr(stations[cfg.station_index], "_bridge_outline", None)
        if not outline:
            raise ValueError(f"Bridge {cfg.id}: selected station building has no generated geometry.")
        bounds = [float(nearest_point_on_alignment(points, p).chainage) for p in outline]
        distance = max(bounds) + cfg.offset if cfg.direction == "INCREASING" else min(bounds) - cfg.offset
    total = polyline_length(points)
    if not math.isfinite(distance) or not 0 <= distance <= total:
        raise ValueError(f"Bridge {cfg.id}: position {distance:.3f} m is outside MAIN alignment [0, {total:.3f}] m.")
    sample = point_at_chainage(points, distance)
    return BridgePlacement(distance, start + distance, sample.point, sample.tangent)
