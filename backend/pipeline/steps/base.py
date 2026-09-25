"""Base class for pipeline execution steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from pipeline.context import GenerationContext


class PipelineStep:
    """Base class for pipeline execution steps.

    Provides a uniform interface for executing drawing and geometry steps.
    """

    def __init__(self, context: "GenerationContext" | None = None) -> None:
        self.context = context

    def execute(self, context: "GenerationContext") -> Any:
        """Execute the step with the provided GenerationContext."""
        raise NotImplementedError("Subclasses must implement execute()")

    @staticmethod
    def _wipe_layers(doc, layer_names: Iterable[str]) -> int:
        """Delete every entity on the given layers. Returns the count.

        Keeps reruns idempotent: without this, entities from a previous
        run stay visible underneath the fresh geometry.
        """
        targets = set(layer_names)
        removed = 0
        for entity in list(doc.modelspace()):
            try:
                if entity.dxf.layer in targets:
                    doc.modelspace().delete_entity(entity)
                    removed += 1
            except Exception:
                continue
        return removed
