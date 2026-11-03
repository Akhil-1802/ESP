"""Configuration dataclass for platform generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from common.constants import DEFAULT_PLATFORM_ARM_LENGTH_M


class PlatformType(str, Enum):
    SIDE = "SIDE"      # platform along ONE side of ONE track
    ISLAND = "ISLAND"  # platform between TWO tracks, serving both


class PlatformSide(str, Enum):
    LEFT = "LEFT"    # relative to direction of increasing chainage
    RIGHT = "RIGHT"


@dataclass
class PlatformConfig:
    # --- I/O ---------------------------------------------------------
    source_dxf: str
    output_dxf: str

    # --- which track(s) to build against ------------------------------
    track_layer: str
    second_track_layer: Optional[str] = None
    track_handle: Optional[str] = None
    second_track_handle: Optional[str] = None

    # --- platform shape ------------------------------------------------
    platform_type: PlatformType = PlatformType.SIDE
    side: PlatformSide = PlatformSide.LEFT
    center_on_track: bool = True
    clearance: float = 1.68
    platform_width: float = 8.50
    start_chainage: float = 0.0
    end_chainage: Optional[float] = None
    platform_length: Optional[float] = 550.0

    curve_samples: int = 2
    straight_tolerance_degrees: float = 1.0

    # --- labeling / annotation ------------------------------------------
    platform_height: Optional[float] = 0.840
    platform_name: str = "HIGH LEVEL PASSENGER PLATFORM"
    tag: Optional[str] = None

    # --- drawing/output styling -----------------------------------------
    output_layer: str = "PLATFORM"
    dimension_layer: str = "PLATFORM-DIM"
    text_layer: str = "PLATFORM-TEXT"
    text_height: float = 1.2
    dim_text_height: float = 1.0
    platform_color: int = 1
    dimension_color: int = 3
    add_hatch: bool = False
    hatch_pattern: str = "ANSI31"

    # --- stairs / platform arms ---------------------------------------
    arm_length: Optional[float] = None
    stair_length: Optional[float] = None
    stair_width: Optional[float] = None
    stair_layer: str = "PLATFORM-STAIRS"
    stair_color: int = 1

    # --- station referencing --------------------------------------------
    station_index: Optional[int] = None
    center_chainage: Optional[float] = None

    @property
    def effective_arm_length(self) -> float:
        """Centralized platform arm length (defaults to 16.999 m if unspecified)."""
        if self.arm_length is not None:
            return float(self.arm_length)
        if self.stair_length is not None:
            return float(self.stair_length)
        return DEFAULT_PLATFORM_ARM_LENGTH_M

    def resolved_end_chainage(self, track_length: float) -> float:
        """Work out the end chainage from whichever inputs were given."""
        start_chainage = self.resolved_start_chainage(track_length)
        if self.center_chainage is not None:
            length = self.platform_length or 550.0
            return min(track_length, start_chainage + length)
        if self.end_chainage is not None:
            return self.end_chainage
        if self.platform_length is not None:
            return start_chainage + self.platform_length
        return track_length

    def resolved_start_chainage(self, track_length: float) -> float:
        """Return the requested start, or center the platform on the track."""
        if self.center_chainage is not None:
            length = self.platform_length or 550.0
            start = self.center_chainage - (length / 2.0)
            return max(0.0, min(start, max(0.0, track_length - length)))
        if self.center_on_track:
            length = self.platform_length
            if length is None and self.end_chainage is not None:
                length = self.end_chainage - self.start_chainage
            if length is None:
                return 0.0
            return (track_length - length) / 2.0
        return self.start_chainage

    def __post_init__(self):
        if isinstance(self.platform_type, str):
            self.platform_type = PlatformType(self.platform_type.upper())
        if isinstance(self.side, str):
            self.side = PlatformSide(self.side.upper())
        if isinstance(self.center_on_track, str):
            self.center_on_track = self.center_on_track.lower() in ("true", "1", "yes", "y")
        if self.clearance < 0:
            raise ValueError("clearance must be >= 0")
        if self.start_chainage < 0:
            raise ValueError("start_chainage must be >= 0")
        if self.end_chainage is not None and self.end_chainage <= self.start_chainage:
            raise ValueError("end_chainage must be greater than start_chainage")
        if self.platform_length is not None and self.platform_length <= 0:
            raise ValueError("platform_length must be > 0")
        if self.platform_width <= 0:
            raise ValueError("platform_width must be > 0")
        if self.straight_tolerance_degrees < 0:
            raise ValueError("straight_tolerance_degrees must be >= 0")
        if self.arm_length is not None and self.arm_length <= 0:
            raise ValueError("arm_length must be > 0")
        if self.stair_length is not None and self.stair_length <= 0:
            raise ValueError("stair_length must be > 0")
        if self.arm_length is not None and self.stair_length is None:
            self.stair_length = self.arm_length
        elif self.stair_length is not None and self.arm_length is None:
            self.arm_length = self.stair_length
        if self.stair_width is not None and self.stair_width <= 0:
            raise ValueError("stair_width must be > 0")
        if self.platform_type == PlatformType.ISLAND and not (
            self.second_track_layer or self.second_track_handle
        ):
            raise ValueError(
                "ISLAND platforms need second_track_layer (or second_track_handle) "
                "- the centerline of the other track it also serves"
            )
