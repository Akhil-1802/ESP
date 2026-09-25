"""Generation context: shared mutable state for pipeline steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class GenerationContext:
    """Mutable state threaded through the pipeline steps.

    Mirrors the attributes historically kept on ``ESPGenerator``
    (``config``, ``source_dxf``, ``platform_layers``, ...).
    """

    config: Any
    source_dxf: str = ""
    platform_layers: List[str] = field(default_factory=list)
    fencing_jobs: List[Any] = field(default_factory=list)
    crossover_results: List[Any] = field(default_factory=list)
    siding_results: List[Any] = field(default_factory=list)
    fouling_marks: List[Any] = field(default_factory=list)
    tracks: Dict[str, Any] = field(default_factory=dict)
    loop_cuts: Dict[str, Tuple[float | None, float | None]] = field(default_factory=dict)
    loop_trim_extents: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    loop_full_lines: Dict[str, list] = field(default_factory=dict)
    main_line_trim_range: Tuple[float, float] | None = None
