"""Shared absolute railway chainage parsing and alignment datum conversion."""
import math
import re


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
    if km is not None and str(km).strip():
        sign = -1 if str(km).strip().startswith("-") else 1
        result = sign * (abs(float(km)) * 1000 + abs(float(metres or 0)))
    else:
        raw = str(getattr(config, "start_chainage", None) or "0").strip()
        result = parse_absolute_chainage(raw)
        if re.fullmatch(r"[+-]?\d+", raw) and abs(result) <= 50:
            result *= 1000
    if not math.isfinite(result):
        raise ValueError("Alignment start chainage must be finite.")
    return result


