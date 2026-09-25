"""Crossover direction/placement normalisation (single definition)."""

from __future__ import annotations


def normalize_direction(value: str | None) -> str:
    """Normalise a crossover direction to ``FORWARD`` or ``REVERSE``."""
    if value is None:
        return "FORWARD"
    s = str(value).strip().upper()
    if s in ("FORWARD", "FWD", "AHEAD", "F"):
        return "FORWARD"
    if s in ("REVERSE", "REV", "BEHIND", "R"):
        return "REVERSE"
    raise ValueError(
        f"Unknown crossover direction {value!r} - use FORWARD or REVERSE."
    )


def normalize_placement(value: str | None, direction: str | None = None) -> str:
    """Normalise placement to ``AHEAD`` or ``BEHIND``."""
    if value is None or (isinstance(value, str) and not value.strip()):
        try:
            d = (
                normalize_direction(direction)
                if direction is not None
                else "FORWARD"
            )
        except ValueError:
            d = "FORWARD"
        return "BEHIND" if d == "REVERSE" else "AHEAD"
    s = str(value).strip().upper()
    if s in ("AHEAD", "FORWARD", "FWD"):
        return "AHEAD"
    if s in ("BEHIND", "REVERSE", "REV"):
        return "BEHIND"
    raise ValueError(
        f"Unknown crossover placement {value!r} - use AHEAD or BEHIND."
    )


def normalize_position_mode(value: str | None, chainage) -> str:
    """Normalise position mode to ``FIXED`` or ``AUTO``."""
    if chainage is None:
        return "AUTO"
    if isinstance(chainage, str) and chainage.strip().upper() == "AUTO":
        return "AUTO"
    if value is None:
        return "FIXED"
    s = str(value).strip().upper()
    if s in ("FIXED", "MANUAL"):
        return "FIXED"
    if s in ("AUTO", "AUTOMATIC"):
        return "AUTO"
    raise ValueError(f"Unknown position mode {value!r} - use FIXED or AUTO.")


def is_auto_chainage(chainage) -> bool:
    """True when the requested chainage means AUTO placement."""
    if chainage is None:
        return True
    return isinstance(chainage, str) and chainage.strip().upper() == "AUTO"
