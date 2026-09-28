"""Track configuration specs (single definition).

``LoopSpec`` / ``LineSpec`` / ``CrossoverSpec`` / ``TrackGenerationConfig``
live here so ``track.generator``, ``config.loader`` and ``cli`` share one
model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from common.constants import LOOP_CROSSOVER_DISTANCE_M, MIN_TRACK_SPACING_M
from track.turnouts import TurnoutParameters


@dataclass
class LoopSpec:
    name: str
    spacing: float
    side: str = "LEFT"
    first_crossover_chainage: float | None = None  # C1
    second_crossover_chainage: float | None = None  # C2 (defaults to C1 + distance)
    turnout_designation: str = "1:12"
    turnout_variant: str = "standard"
    crossover_distance_m: float = LOOP_CROSSOVER_DISTANCE_M
    extend_start_m: float = 0.0  # overrun before C1 (MAIN m, 0 = none)
    extend_end_m: float = 0.0  # overrun past C2 (MAIN m, 0 = none)
    reference_track: str = "MAIN_LINE"  # prior alignment this loop offsets from


@dataclass
class LineSpec:
    name: str
    spacing: float
    side: str = "LEFT"
    direction: str = ""  # UP / DN for MAIN lines ("" = unspecified)
    reference_track: str = "MAIN_LINE"  # Prior track this line offsets from


@dataclass
class SidingSpec:
    """A dead-end siding leaving ``source_track`` through one turnout."""

    source_track: str
    start_chainage_m: float = 0.0
    direction: str = "FORWARD"
    side: str = "LEFT"
    turnout_designation: str = "1:12"
    turnout_variant: str = "standard"
    standing_length_m: float = 200.0
    spacing: float = MIN_TRACK_SPACING_M
    id: str | None = None


@dataclass
class CrossoverSpec:
    """A standard SRJ-to-SRJ crossover between two parallel tracks."""

    from_track: str
    to_track: str
    from_chainage_m: float | str | None = 0.0
    to_chainage_m: float | None = None
    turnout: TurnoutParameters | None = None
    placement: str | None = None
    platform_index: int | None = None
    after_platform: bool = True
    distance_from_platform_m: float = 0.0
    id: str | None = None
    direction: str | None = None
    position_mode: str | None = None
    auto_anchor_id: str | None = None  # prior crossover AUTO is placed from


@dataclass
class TrackGenerationConfig:
    source_dxf: str
    output_dxf: str
    source_layer: str
    loops: List[LoopSpec] = field(default_factory=list)
    additional_lines: List[LoopSpec | LineSpec] = field(default_factory=list)
    crossovers: List[CrossoverSpec] = field(default_factory=list)
    main_directions: dict = field(default_factory=dict)  # track name -> UP / DN


__all__ = [
    "LoopSpec",
    "LineSpec",
    "CrossoverSpec",
    "SidingSpec",
    "TrackGenerationConfig",
    "LOOP_CROSSOVER_DISTANCE_M",
]
