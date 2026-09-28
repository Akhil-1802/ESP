"""ROB (Road Over Bridge) configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ROBConfig:
    """Configuration for one Road Over Bridge (ROB)."""

    id: str = "ROB_1"
    platform: str = "PLATFORM_1"
    reference_end: str = "START"  # "START" or "END"
    offset: float = 50.0
    width: float = 10.0
    reference_track: str = "MAIN_LINE"
    block_name: str = "SGFD"
    output_layer: Optional[str] = "SGFD"
    color: int = 1  # Standard AutoCAD red (matching reference CAD)
    deck_margin: float = 3.5  # Transverse clearance beyond outermost tracks (m)
    wing_extension: float = 2.5  # Abutment extension beyond deck top/bottom (m)
    wing_length: float = 8.0  # Horizontal wing wall return length (m)
    tracks: list[str] = field(default_factory=list)  # Specific tracks to cross, empty = all yard tracks
    add_text: bool = False  # Omit text ROB by default
    add_dimension: bool = True  # Show width of the ROB by default
    chainage: Optional[str] = None  # Explicit chainage override (e.g. "7983." or 7983.5)
    add_chainage: bool = False  # Omit duplicate BR.CH- text on bridge by default (shown on CHAINAGE layer as BR AT CH ...)
    add_centerline: bool = False  # Omit dotted centerline inside bridge by default

    def __post_init__(self):
        try:
            self.width = float(self.width)
        except (TypeError, ValueError):
            raise ValueError(f"ROB width must be a number, got {self.width!r}.")
        if self.width <= 0:
            raise ValueError(f"ROB width must be > 0, got {self.width}.")

        try:
            self.offset = float(self.offset)
        except (TypeError, ValueError):
            raise ValueError(f"ROB offset must be a number, got {self.offset!r}.")
        if self.offset < 0:
            raise ValueError(f"ROB offset must be >= 0, got {self.offset}.")

        ref_end = str(self.reference_end).strip().upper()
        if ref_end not in ("START", "END"):
            raise ValueError(
                f"ROB reference_end must be 'START' or 'END', got {self.reference_end!r}."
            )
        self.reference_end = ref_end

        if not self.block_name:
            self.block_name = "SGFD"

        if not self.output_layer:
            self.output_layer = self.block_name or "SGFD"

        if not self.platform:
            self.platform = "PLATFORM_1"

        if not self.reference_track:
            self.reference_track = "MAIN_LINE"

        self.deck_margin = max(0.5, float(self.deck_margin))
        self.wing_extension = max(0.5, float(self.wing_extension))
        self.wing_length = max(1.0, float(self.wing_length))

        if isinstance(self.tracks, str):
            self.tracks = [t.strip() for t in self.tracks.split(",") if t.strip()]
        elif isinstance(self.tracks, (list, tuple, set)):
            self.tracks = [
                str(t).strip()
                for t in self.tracks
                if str(t).strip() and str(t).strip().upper() != "ALL"
            ]
        else:
            self.tracks = []

        if self.chainage is not None:
            self.chainage = str(self.chainage).strip()
            if not self.chainage:
                self.chainage = None
