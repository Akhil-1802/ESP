"""Platform generator orchestration."""

from __future__ import annotations

from typing import Mapping, Sequence, Tuple

import ezdxf

from .config import PlatformConfig, PlatformType
from .island import island_platform
from .models import PlatformResult
from .side import side_platform
from .track import Track


class PlatformGenerator:
    """Orchestrates: load track(s) from source DXF -> build platform geometry -> write to output DXF."""

    def __init__(
        self,
        cfg: PlatformConfig,
        track_points: Mapping[str, Sequence[tuple[float, float]]] | None = None,
    ):
        self.cfg = cfg
        self.track_points = track_points or {}

    def _track(self, doc, layer: str | None, handle: str | None, name: str) -> Track:
        """Use canonical pipeline geometry when available; retain DXF fallback for standalone use."""
        if layer and layer in self.track_points:
            points = [
                (float(point[0]), float(point[1]))
                for point in self.track_points[layer]
            ]
            if len(points) < 2:
                raise ValueError(f"Track {layer!r} needs at least 2 canonical points")
            return Track(name=layer, points=points)
        return Track.from_dxf(doc, layer_name=layer, handle=handle, name=name)

    def build(self, document=None) -> Tuple[PlatformResult, "ezdxf.document.Drawing"]:
        doc = document if document is not None else ezdxf.readfile(self.cfg.source_dxf)
        track1 = self._track(
            doc, self.cfg.track_layer, self.cfg.track_handle, "track1"
        )

        if self.cfg.platform_type == PlatformType.SIDE:
            result = side_platform(track1, self.cfg) #for side platform
        else: #for island platform
            track2 = self._track(
                doc,
                self.cfg.second_track_layer,
                self.cfg.second_track_handle,
                "track2",
            )
            result = island_platform(track1, track2, self.cfg)

        return result, doc

    def run(self) -> PlatformResult:
        from ...formats.dxf.platform_io import write_platform

        result, doc = self.build()
        write_platform(doc, result, self.cfg)
        doc.saveas(self.cfg.output_dxf)
        return result
