"""FOB (Foot Over Bridge) configuration (single definition)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from common.constants import (
    DEFAULT_FOB_DIRECTION,
    DEFAULT_FOB_OFFSET_M,
    DEFAULT_FOB_WIDTH_M,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
    MAX_FOB_OFFSET_M,
    MIN_FOB_OFFSET_M,
)


def validate_fob_clearance(clearance_m: float) -> float:
    """Raise when a vertical clearance is below 6.25 m above rail."""
    try:
        clearance = float(clearance_m)
    except (TypeError, ValueError):
        raise ValueError(
            f"FOB vertical clearance must be a number, got {clearance_m!r}.")
    if clearance < FOB_VERTICAL_CLEARANCE_M:
        raise ValueError(
            f"FOB vertical clearance must be >= "
            f"{FOB_VERTICAL_CLEARANCE_M:g} m above rail, got {clearance:g}.")
    return clearance


def validate_fob_offset(offset_m: float) -> float:
    """Validate that the FOB offset is within the allowed 40 m to 60 m range."""
    try:
        offset = float(offset_m)
    except (TypeError, ValueError):
        raise ValueError(f"FOB offset must be a number, got {offset_m!r}.")
    if offset < MIN_FOB_OFFSET_M - 1e-6 or offset > MAX_FOB_OFFSET_M + 1e-6:
        raise ValueError(
            f"FOB offset {offset:.3f} m is out of allowed range "
            f"[{MIN_FOB_OFFSET_M:g} m, {MAX_FOB_OFFSET_M:g} m]."
        )
    return offset


def normalize_fob_direction(direction: str | int) -> str:
    """Normalize direction input to 'INCREASING' or 'DECREASING'."""
    if direction in (1, "+1", "1", True):
        return "INCREASING"
    if direction in (-1, "-1", False):
        return "DECREASING"
    clean = str(direction).strip().upper()
    if clean in ("INCREASING", "FORWARD", "AHEAD", "UP"):
        return "INCREASING"
    if clean in ("DECREASING", "BACKWARD", "REVERSE", "DN", "DOWN"):
        return "DECREASING"
    raise ValueError(
        f"Invalid FOB direction {direction!r}. Must be 'INCREASING' or 'DECREASING'."
    )


@dataclass
class FOBConfig:
    """Configuration for one Foot Over Bridge deck."""
    reference_track: str = "MAIN_LINE"
    reference_chainage: Optional[float | str] = "MAIN_CENTER"
    platforms: list[str] = field(default_factory=list)
    width: float = DEFAULT_FOB_WIDTH_M
    extend_start_m: float = 0.0
    extend_end_m: float = 0.0
    output_layer: str = "FOB"
    color: int = 1
    vertical_clearance_m: float = FOB_VERTICAL_CLEARANCE_M
    offset: Optional[float] = None
    direction: str = DEFAULT_FOB_DIRECTION
    arms: dict = field(default_factory=dict)
    fob_chainage: Optional[float] = None
    dimension_layer: Optional[str] = None
    position_mode: Optional[str] = None

    def __post_init__(self):
        if self.width <= 0:
            raise ValueError(f"FOB width must be > 0, got {self.width}.")
        if self.extend_start_m < 0 or self.extend_end_m < 0:
            raise ValueError("FOB extensions must be >= 0.")
        if self.offset is not None:
            self.offset = validate_fob_offset(self.offset)
        self.direction = normalize_fob_direction(self.direction)
        # Validate vertical clearance at construction time
        validate_fob_clearance(self.vertical_clearance_m)
        if self.arms:
            for plat, arm in self.arms.items():
                if not isinstance(arm, dict):
                    raise ValueError(f"Arm for platform {plat!r} must be a dict.")
                if "length" not in arm:
                    raise ValueError(f"Arm for platform {plat!r} missing required 'length'.")
                if float(arm["length"]) <= 0:
                    raise ValueError(f"Arm length for platform {plat!r} must be > 0.")
                side = str(arm.get("side", "LEFT")).strip().upper()
                if side not in ("LEFT", "RIGHT"):
                    raise ValueError(f"Arm side for platform {plat!r} must be 'LEFT' or 'RIGHT'.")
                arm["side"] = side
                arm["length"] = float(arm["length"])
