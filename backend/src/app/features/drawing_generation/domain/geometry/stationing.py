"""Shared absolute railway chainage parsing and alignment datum conversion."""
import math
import re

from .operations import nearest_point_on_alignment, point_at_chainage, polyline_length, track_axis_hits


def parse_absolute_chainage(value) -> float:
    """Plain numbers are absolute metres; km+metres and explicit KM/M are supported."""
    raw = str(value).strip().upper()
    plus = re.fullmatch(r"(-?\d+)\s*\+\s*(\d+(?:\.\d+)?)", raw)
    if plus:
        km, metres = plus.groups()
        if float(metres) >= 1000:
            raise ValueError("Absolute chainage metre component must be less than 1000.")
        result = (-1 if km.startswith("-") else 1) * (abs(int(km)) * 1000 + float(metres))
    else:
        number = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(KM|M)?", raw)
        if not number:
            raise ValueError("Absolute chainage must be metres or km+metres (for example 12+850).")
        result = float(number[1]) * (1000 if number[2] == "KM" else 1)
    if not math.isfinite(result):
        raise ValueError("Absolute chainage must be finite.")
    return result


def alignment_start_metres(config) -> float:
    """Match the existing alignment datum convention, including explicit KM/M fields."""
    km = getattr(config, "start_km", None)
    metres = getattr(config, "start_m", None)
    if (km is not None and str(km).strip()) or (metres is not None and str(metres).strip()):
        sign = -1 if str(km).strip().startswith("-") else 1
        result = sign * (abs(float(km or 0)) * 1000 + abs(float(metres or 0)))
    else:
        raw = str(getattr(config, "start_chainage", None) or "0").strip()
        result = parse_absolute_chainage(raw)
        if re.fullmatch(r"[+-]?\d+", raw) and abs(result) <= 50:
            result *= 1000
    if not math.isfinite(result):
        raise ValueError("Alignment start chainage must be finite.")
    return result


def absolute_track_distance(config, absolute, tracks, track_name, feature):
    """Locate a MAIN absolute chainage on the selected track's cross-section."""
    main = tracks.get("MAIN_LINE")
    if main is None or len(main) < 2:
        raise ValueError(f"{feature} absolute placement requires MAIN_LINE geometry.")
    distance = absolute - alignment_start_metres(config)
    length = polyline_length(main)
    if not 0 <= distance <= length:
        raise ValueError(f"{feature} absolute chainage resolves outside MAIN alignment [0, {length:.3f}] m.")
    if track_name not in tracks:
        raise ValueError(f"{feature} reference track {track_name!r} not found.")
    if track_name == "MAIN_LINE":
        return distance

    sample = point_at_chainage(main, distance)
    normal = (-sample.tangent[1], sample.tangent[0])
    points = tracks[track_name]
    hits = track_axis_hits(sample.point, normal, {track_name: points})
    if not hits:
        raise ValueError(f"{feature} absolute chainage does not cross the selected reference track.")
    hit = min(hits, key=abs)
    crossing = (sample.point[0] + hit * normal[0], sample.point[1] + hit * normal[1])
    return float(nearest_point_on_alignment(points, crossing).chainage)
