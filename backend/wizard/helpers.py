"""Validation and parsing helpers for the wizard."""

from __future__ import annotations

from typing import Tuple

from common.constants import (
    DEFAULT_FOB_DIRECTION,
    DEFAULT_FOB_OFFSET_M,
    DEFAULT_FOB_WIDTH_M,
    LOOP_HALF_LENGTH_M,
    MIN_TRACK_SPACING_M,
)

DEFAULT_TURNOUT = "1:12"
DEFAULT_EXTENSION = {"length": 120.0, "side": "BOTH"}

_KNOWN_TOP_LEVEL = {
    "output_dxf",
    "track_source_layer",
    "main_lines",
    "loops",
    "proposed_lines",
    "proposed_loops",
    "crossovers",
    "platforms",
    "stations",
    "fobs",
    "sidings",
    "robs",
    "gradients",
}

__all__ = [
    "DEFAULT_TURNOUT",
    "DEFAULT_EXTENSION",
    "_KNOWN_TOP_LEVEL",
    "_count",
    "_choice",
    "_parallel_list",
    "_spacing",
    "_turnout",
    "_extensions",
    "_centered_chainages",
    "_fob_chainage",
]


def _count(value: object, name: str) -> int:
    try:
        count = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"'{name}.count' must be a whole number, got {value!r}.") from None
    if count < 0:
        raise ValueError(f"'{name}.count' must be >= 0, got {count}.")
    return count


def _choice(value: object, allowed: tuple[str, ...], name: str) -> str:
    text = str(value or "").strip().upper()
    if text not in allowed:
        raise ValueError(f"'{name}' must be one of {list(allowed)}, got {value!r}.")
    return text


def _parallel_list(values: object, count: int, name: str) -> list:
    if values is None:
        return [None] * count
    if not isinstance(values, list) or len(values) != count:
        raise ValueError(f"'{name}' must be a list of {count} item(s) to match count.")
    return values


def _spacing(value: object, name: str) -> float:
    try:
        spacing = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"'{name}' must be a number (metres), got {value!r}.") from None
    if spacing < MIN_TRACK_SPACING_M:
        raise ValueError(
            f"'{name}' must be >= {MIN_TRACK_SPACING_M:g} m (ESP minimum), got {spacing:g}."
        )
    return spacing


def _turnout(item: dict, shared: object = None) -> Tuple[str, str]:
    raw = item.get("turnout", shared if shared is not None else DEFAULT_TURNOUT)
    if isinstance(raw, dict):
        designation = str(raw.get("designation", DEFAULT_TURNOUT))
        variant = str(raw.get("variant", "standard"))
        return designation, variant
    return str(raw or DEFAULT_TURNOUT), str(item.get("turnout_variant", "standard"))


def _extensions(item: dict, shared: object = None) -> Tuple[float, float]:
    """(extend_start_m, extend_end_m) like the interactive overrun prompt."""
    if "extend_start_m" in item or "extend_end_m" in item:
        return float(item.get("extend_start_m", 0.0) or 0.0), float(
            item.get("extend_end_m", 0.0) or 0.0
        )
    raw = item.get(
        "extensions",
        item.get("extension", shared if shared is not None else DEFAULT_EXTENSION),
    )
    if not isinstance(raw, dict):
        raise ValueError(
            f"'extensions' must be {{\"length\": m, \"side\": START|END|BOTH}}, got {raw!r}."
        )
    length = float(raw.get("length", 0.0) or 0.0)
    if length < 0:
        raise ValueError(f"extension length must be >= 0, got {length:g}.")
    if length == 0:
        return 0.0, 0.0
    side = _choice(raw.get("side", "BOTH"), ("START", "END", "BOTH"), "extensions.side")
    return (
        length if side in ("START", "BOTH") else 0.0,
        length if side in ("END", "BOTH") else 0.0,
    )


def _centered_chainages(main_center: float | None, name: str) -> Tuple[float, float]:
    if main_center is None:
        raise ValueError(
            f"'{name}' needs the MAIN midpoint (750 m centred loops), "
            "which could not be determined from the uploaded KML."
        )
    return main_center - LOOP_HALF_LENGTH_M, main_center + LOOP_HALF_LENGTH_M


def _fob_chainage(value: object, main_center: float | None, number: int) -> float:
    """FOB reference chainage: blank/None/"AUTO"/"MAIN_CENTER" means the MAIN centre."""
    if value is None or (
        isinstance(value, str)
        and value.strip() in ("", "AUTO", "auto", "MAIN_CENTER", "main_center")
    ):
        if main_center is None:
            raise ValueError(
                f"fobs[{number - 1}] needs 'reference_chainage' (MAIN m) "
                "or a determinable MAIN centre (blank = MAIN centre)."
            )
        return float(main_center)
    try:
        chainage = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(
            f"fobs[{number - 1}] 'reference_chainage' must be a number "
            f"(MAIN m) or blank for MAIN centre, got {value!r}."
        ) from None
    if chainage < 0:
        raise ValueError(f"fobs[{number - 1}] 'reference_chainage' must be >= 0.")
    return chainage
