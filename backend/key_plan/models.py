"""JSON snapshots contain resolved values, never live ezdxf objects."""

from dataclasses import dataclass, field


@dataclass
class Scene:
    width: float
    height: float
    lines: list = field(default_factory=list)
    polygons: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    # Public normalization metadata also makes measurement preservation testable.
    tracks: list = field(default_factory=list)
    platforms: list = field(default_factory=list)
    crossovers: list = field(default_factory=list)

