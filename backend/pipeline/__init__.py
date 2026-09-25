"""ESP generation pipeline.

Stages (each a mixin consumed by :class:`orchestrator.ESPGenerator`):
    context       - shared GenerationContext dataclass
    steps         - modular step classes
    orchestrator  - ESPGenerator tying the stages together
"""

from .context import GenerationContext
from .orchestrator import ESPGenerator
from .steps import (
    CalLabelMixin,
    CalLabelStep,
    ChainageMixin,
    ChainageStep,
    CrossoverMixin,
    CrossoverStep,
    FencingMixin,
    FencingStep,
    FobMixin,
    FobStep,
    FoulingMixin,
    FoulingStep,
    PipelineStep,
    PlatformMixin,
    PlatformStep,
    SidingMixin,
    SidingStep,
    StationMixin,
    StationStep,
    TrackMixin,
    TrackStep,
)

__all__ = [
    "CalLabelMixin",
    "CalLabelStep",
    "ChainageMixin",
    "ChainageStep",
    "CrossoverMixin",
    "CrossoverStep",
    "ESPGenerator",
    "FencingMixin",
    "FencingStep",
    "FobMixin",
    "FobStep",
    "FoulingMixin",
    "FoulingStep",
    "GenerationContext",
    "PipelineStep",
    "PlatformMixin",
    "PlatformStep",
    "SidingMixin",
    "SidingStep",
    "StationMixin",
    "StationStep",
    "TrackMixin",
    "TrackStep",
]
