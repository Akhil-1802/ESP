"""Base class for pipeline execution steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import ezdxf

if TYPE_CHECKING:
    from ..context import GenerationContext


class PipelineStep:
    """Shared document access, layer cleanup, and polygon caching for drawing stages."""

    def __init__(self, context: "GenerationContext" | None = None) -> None:
        self.context = context

    def _active_document(self):
        context = getattr(self, "context", None)
        if context is not None and context.in_memory:
            return context.document
        return None

    def _load_document(self):
        """Share one request-local drawing; retain disk-based standalone steps."""
        doc = self._active_document()
        if doc is None:
            return ezdxf.readfile(self.config.output_dxf)
        # A logical load used to reconstruct these transient registries from
        # saved entities. Invalidate them after earlier stages moved/deleted text
        # or tracks, preserving the original annotation placement behavior.
        for name in ("_esp_text_boxes", "_esp_track_segments"):
            if hasattr(doc, name):
                delattr(doc, name)
        return doc

    def _save_document(self, doc):
        if self._active_document() is None:
            doc.saveas(self.config.output_dxf)

    def _cached_polygons(self, doc, layer, extract):
        context = getattr(self, "context", None)
        if context is None or not context.in_memory or context.document is not doc:
            return extract()
        if layer not in context.polygon_cache:
            context.polygon_cache[layer] = tuple(tuple(poly) for poly in extract())
        return [list(poly) for poly in context.polygon_cache[layer]]

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
