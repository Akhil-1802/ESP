"""Track generation: specs, parallel lines, loops, direction marks."""

from .generator import (
    BuiltTracks,
    CrossoverSpec,
    LineSpec,
    LoopSpec,
    SidingSpec,
    TrackGenerationConfig,
    TrackGenerator,
)

__all__ = [
    "TrackGenerationConfig",
    "TrackGenerator",
    "LoopSpec",
    "LineSpec",
    "CrossoverSpec",
    "SidingSpec",
    "BuiltTracks",
]
