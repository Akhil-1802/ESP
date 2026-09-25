"""Restricted regions (platforms/stations) vs crossover footprint conflicts."""

from __future__ import annotations

from typing import Sequence

from common.geometry import Point, find_straight_window, polyline_length
from track.crossover.models import RestrictedConflict, RestrictedRegion
from track.crossover.normalize import normalize_placement

RESTRICT_TOL_M = 1e-9


def crossover_track_intervals(
    from_track: str,
    to_track: str,
    start_chainage: float,
    second_chainage: float,
    placement: str | None,
    direction: str | None = None,
    a_m: float = 0.0,
) -> dict[str, tuple[float, float]]:
    """Actual occupied chainage interval (MAIN datum) per affected track."""
    sign = (
        1.0
        if normalize_placement(placement, direction) == "AHEAD"
        else -1.0
    )
    start = float(start_chainage)
    second = float(second_chainage)
    a = max(0.0, float(a_m))
    from_lo, from_hi = (start, start + sign * a)
    to_lo, to_hi = (second - sign * a, second)
    return {
        from_track: (min(from_lo, from_hi), max(from_lo, from_hi)),
        to_track: (min(to_lo, to_hi), max(to_lo, to_hi)),
    }


def find_restriction_conflicts(
    intervals: dict[str, tuple[float, float]],
    regions: Sequence[RestrictedRegion] | None,
) -> list[RestrictedConflict]:
    """Overlaps between per-track crossover footprints and restricted regions."""
    out: list[RestrictedConflict] = []
    for track, (a0, a1) in (intervals or {}).items():
        lo_a, hi_a = min(a0, a1), max(a0, a1)
        for region in regions or []:
            if region.track != track:
                continue
            lo_r = min(region.start_chainage, region.end_chainage)
            hi_r = max(region.start_chainage, region.end_chainage)
            lo, hi = max(lo_a, lo_r), min(hi_a, hi_r)
            if hi > lo + RESTRICT_TOL_M:
                out.append(
                    RestrictedConflict(
                        track=track,
                        footprint_start=lo_a,
                        footprint_end=hi_a,
                        region=region,
                        overlap_start=lo,
                        overlap_end=hi,
                    )
                )
    return out


def _local_platform_body_interval(cfg, points) -> tuple[float, float]:
    """Platform body chainage interval in the track's LOCAL datum."""
    total = polyline_length(list(points))
    start = cfg.resolved_start_chainage(total)
    end = cfg.resolved_end_chainage(total)
    if getattr(cfg, "center_on_track", False):
        start = find_straight_window(
            list(points),
            end - start,
            start,
            getattr(cfg, "straight_tolerance_degrees", 1.0),
        )
        length = getattr(cfg, "platform_length", None)
        end = start + (length if length is not None else end - start)
    return min(start, end), max(start, end)


def _main_offset(track: str, extents) -> float:
    """Local-to-MAIN datum offset."""
    ext = (extents or {}).get(track)
    return float(ext[0]) if ext is not None else 0.0


def platforms_to_restricted_regions(
    platform_requests,
    tracks_points: dict[str, Sequence[Point]],
    extents: dict[str, tuple[float, float]] | None = None,
) -> list[RestrictedRegion]:
    """One restricted region per served track per platform (MAIN datum)."""
    regions: list[RestrictedRegion] = []
    for number, preq in enumerate(platform_requests or [], 1):
        cfg = preq.config
        ptype = getattr(
            getattr(cfg, "platform_type", "SIDE"),
            "value",
            str(getattr(cfg, "platform_type", "SIDE")),
        ).upper()
        served = [preq.track_layer]
        second = getattr(cfg, "second_track_layer", None)
        if ptype == "ISLAND" and second:
            served.append(second)
        primary = served[0]
        primary_pts = (tracks_points or {}).get(primary)
        if primary_pts is None or len(list(primary_pts)) < 2:
            continue
        lo_local, hi_local = _local_platform_body_interval(cfg, primary_pts)
        stair = getattr(cfg, "arm_length", None)
        if stair is None:
            stair = getattr(cfg, "stair_length", None)
        stair = float(stair) if stair is not None else 0.0
        off = _main_offset(primary, extents)
        lo, hi = lo_local - stair + off, hi_local + stair + off
        label = f"Platform {number} [{getattr(cfg, 'output_layer', '')}]"
        for track in served:
            if (tracks_points or {}).get(track) is None:
                continue
            regions.append(RestrictedRegion(track, lo, hi, label))
    return regions


def stations_to_restricted_regions(
    station_requests,
    platform_requests,
    tracks_points: dict[str, Sequence[Point]],
    extents: dict[str, tuple[float, float]] | None = None,
) -> list[RestrictedRegion]:
    """Station-building chainage intervals (MAIN datum)."""
    regions: list[RestrictedRegion] = []
    by_layer = {}
    for preq in platform_requests or []:
        by_layer.setdefault(getattr(preq.config, "output_layer", ""), preq)
    for sreq in station_requests or []:
        preq = by_layer.get(getattr(sreq, "platform_layer", ""))
        if preq is None:
            continue
        pts = (tracks_points or {}).get(preq.track_layer)
        if pts is None or len(list(pts)) < 2:
            continue
        try:
            length = float(getattr(sreq, "building_length", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if length <= 0:
            continue
        lo_local, hi_local = _local_platform_body_interval(preq.config, pts)
        mid = (lo_local + hi_local) / 2.0
        off = _main_offset(preq.track_layer, extents)
        regions.append(
            RestrictedRegion(
                preq.track_layer,
                mid - length / 2.0 + off,
                mid + length / 2.0 + off,
                f"Station building {getattr(sreq, 'building_name', '')!r} "
                f"on {getattr(sreq, 'platform_layer', '')}",
            )
        )
    return regions


__all__ = [
    "RESTRICT_TOL_M",
    "crossover_track_intervals",
    "find_restriction_conflicts",
    "platforms_to_restricted_regions",
    "stations_to_restricted_regions",
]
