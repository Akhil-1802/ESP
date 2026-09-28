"""Domain models for Brownfield railway layout design and MAIN_LINE specifications."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from typing import Any, Iterator, List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass
class BrownfieldMainLineSpec:
    """Specification for adding a MAIN_LINE in a Brownfield layout.

    Each newly added MAIN_LINE must explicitly mention the reference track
    from which it is offset or constructed.
    """

    name: str
    reference_track: str
    spacing: float = 5.3
    side: str = "LEFT"  # "LEFT" or "RIGHT" relative to reference track's direction of travel
    direction: str = ""  # "UP", "DN", "BOTH", etc.
    is_existing: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Main line name must be a non-empty string.")
        if not self.reference_track or not self.reference_track.strip():
            raise ValueError(
                f"Main line {self.name!r} must specify a reference_track."
            )
        if self.spacing <= 0:
            raise ValueError(
                f"Main line {self.name!r} spacing must be greater than zero, got {self.spacing}."
            )
        side_norm = self.side.strip().upper()
        if side_norm not in ("LEFT", "RIGHT"):
            raise ValueError(
                f"Main line {self.name!r} side must be 'LEFT' or 'RIGHT', got {self.side!r}."
            )
        self.side = side_norm


@dataclass
class TrackRelationship:
    """Represents a geometric reference relationship between two tracks."""

    track_name: str
    reference_track: str
    spacing: float
    side: str


@dataclass
class BrownfieldTrack:
    """A railway track centerline and its brownfield reference metadata."""

    name: str
    points: List[Point] = field(default_factory=list)
    reference_track: Optional[str] = None
    spacing_from_reference: Optional[float] = None
    side: str = "LEFT"
    direction: str = ""
    is_existing: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> float:
        """Total length along track polyline in metres."""
        if not self.points or len(self.points) < 2:
            return 0.0
        return sum(
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.points, self.points[1:])
        )

    @property
    def is_main(self) -> bool:
        s = self.name.upper()
        return s == "MAIN_LINE" or s.startswith("MAIN_LINE_") or s.startswith("MAIN")

    # Sequence protocol implementation for compatibility with point sequences
    def __iter__(self) -> Iterator[Point]:
        return iter(self.points)

    def __len__(self) -> int:
        return len(self.points)

    def __getitem__(self, idx: Any) -> Any:
        return self.points[idx]


@dataclass
class BrownfieldLayout(Mapping):
    """Container holding Brownfield tracks and their reference relationships."""

    tracks: dict[str, BrownfieldTrack] = field(default_factory=dict)
    relationships: list[TrackRelationship] = field(default_factory=list)
    crossovers: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_track(self, track: BrownfieldTrack) -> None:
        self.tracks[track.name] = track

    def get_track(self, name: str) -> Optional[BrownfieldTrack]:
        return self.tracks.get(name)

    def add_crossover(self, crossover: Any) -> None:
        """Register a Brownfield crossover result."""
        self.crossovers.append(crossover)

    def get_crossovers_for_track(self, track_name: str) -> list[Any]:
        """Return all crossovers connecting to or from track_name."""
        target = track_name.strip()
        return [
            co for co in self.crossovers
            if getattr(co, "from_track", "") == target or getattr(co, "to_track", "") == target
        ]

    def crossover_srjs_for_track(self, track_name: str) -> list[float]:
        """Return all SRJ chainages located on track_name."""
        target = track_name.strip()
        chainages: list[float] = []
        for co in self.crossovers:
            if getattr(co, "from_track", "") == target:
                chainages.append(float(getattr(co, "from_srj_chainage", co.chainage)))
            if getattr(co, "to_track", "") == target:
                chainages.append(float(getattr(co, "to_srj_chainage", co.chainage)))
        return sorted(chainages)

    @property
    def tracks_by_id(self) -> dict[str, BrownfieldTrack]:
        return self.tracks

    @property
    def main_tracks(self) -> list[BrownfieldTrack]:
        return [t for t in self.tracks.values() if t.is_main]

    @property
    def main_track_names(self) -> list[str]:
        return [t.name for t in self.main_tracks]

    def to_dict(self) -> dict[str, list[Point]]:
        """Return raw track points dictionary {name: [(x, y), ...]}."""
        return {name: list(track.points) for name, track in self.tracks.items()}

    # Mapping protocol methods
    def __getitem__(self, key: str) -> BrownfieldTrack:
        return self.tracks[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.tracks)

    def __len__(self) -> int:
        return len(self.tracks)

    def __contains__(self, key: object) -> bool:
        return key in self.tracks

    def get(self, key: str, default: Any = None) -> Any:
        return self.tracks.get(key, default)

    def keys(self):
        return self.tracks.keys()

    def values(self):
        return self.tracks.values()

    def items(self):
        return self.tracks.items()
