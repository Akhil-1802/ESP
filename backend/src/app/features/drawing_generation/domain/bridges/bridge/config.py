"""Bridge inputs, independent of how the bridge is positioned."""
from dataclasses import dataclass, field
import math

BRIDGE_TYPES = {"PSC_SLAB": "PSC SLAB", "RCC_BOX": "RCC BOX", "OTHER": "OTHER"}


@dataclass
class BridgeConfig:
    id: str = "BRIDGE_1"
    bridge_type: str = "PSC_SLAB"
    custom_type: str = ""
    position_mode: str = "OFFSET"
    station_index: int | None = None  # Index into ESPConfig.stations (building requests).
    offset: float = 50.0  # Station edge to bridge centreline, along MAIN.
    direction: str = "INCREASING"
    chainage: str | float | None = None  # Absolute metres or railway km+metres.
    width: float = 10.0
    reference_track: str = "MAIN_LINE"
    block_name: str = "BRIDGE"
    output_layer: str = "BRIDGE"
    color: int = 1
    deck_margin: float = 3.5
    wing_length: float = 8.0
    tracks: list[str] = field(default_factory=list)
    add_text: bool = True
    add_dimension: bool = True
    add_chainage: bool = False
    add_centerline: bool = False

    @property
    def type_label(self) -> str:
        return self.custom_type if self.bridge_type == "OTHER" else BRIDGE_TYPES[self.bridge_type]

    def __post_init__(self):
        self.bridge_type = str(self.bridge_type).strip().upper()
        if self.bridge_type not in BRIDGE_TYPES:
            raise ValueError("Bridge type must be PSC_SLAB, RCC_BOX, or OTHER.")
        self.custom_type = " ".join(str(self.custom_type or "").split())
        if self.bridge_type == "OTHER" and not self.custom_type:
            raise ValueError("Bridge custom type/name is required for Other.")
        if len(self.custom_type) > 80 or any(c in self.custom_type for c in "\\{}"):
            raise ValueError("Bridge custom type must be at most 80 characters without DXF formatting characters.")
        self.position_mode = str(self.position_mode).strip().upper()
        if self.position_mode not in ("OFFSET", "FIXED"):
            raise ValueError("Bridge position_mode must be OFFSET or FIXED.")
        if self.reference_track != "MAIN_LINE":
            raise ValueError("Bridge placement uses the MAIN_LINE chainage datum.")
        for name, inclusive in (("width", False), ("deck_margin", True), ("wing_length", False)):
            try:
                value = float(getattr(self, name))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Bridge {name} must be a finite number.") from exc
            if not math.isfinite(value) or (value < 0 if inclusive else value <= 0):
                raise ValueError(f"Bridge {name} must be finite and {'>=' if inclusive else '>'} 0.")
            setattr(self, name, value)
        if self.position_mode == "OFFSET":
            if isinstance(self.station_index, bool) or not isinstance(self.station_index, int) or self.station_index < 0:
                raise ValueError("Bridge offset placement requires a station building index.")
            self.direction = str(self.direction).strip().upper()
            if self.direction not in ("INCREASING", "DECREASING"):
                raise ValueError("Bridge direction must be INCREASING or DECREASING.")
            try:
                self.offset = float(self.offset)
            except (ValueError, TypeError) as exc:
                raise ValueError("Bridge offset must be a finite number >= 0.") from exc
            if not math.isfinite(self.offset) or self.offset < 0:
                raise ValueError("Bridge offset must be a finite number >= 0.")
        elif self.chainage is None or not str(self.chainage).strip():
            raise ValueError("Bridge absolute chainage is required.")
        self.block_name = str(self.block_name or self.id)
        self.output_layer = str(self.output_layer or self.id)
        if isinstance(self.tracks, str):
            self.tracks = [t.strip() for t in self.tracks.split(",") if t.strip()]
        else:
            self.tracks = [str(t).strip() for t in (self.tracks or []) if str(t).strip()]
