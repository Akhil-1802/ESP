"""Platform generator orchestration."""

from __future__ import annotations

from typing import Tuple

import ezdxf

from platform_gen.config import PlatformConfig, PlatformType
from platform_gen.island import island_platform
from platform_gen.models import PlatformResult
from platform_gen.side import side_platform
from platform_gen.track import Track


class PlatformGenerator:
    """Orchestrates: load track(s) from source DXF -> build platform geometry -> write to output DXF."""

    def __init__(self, cfg: PlatformConfig):
        self.cfg = cfg

    def build(self) -> Tuple[PlatformResult, "ezdxf.document.Drawing"]:
        doc = ezdxf.readfile(self.cfg.source_dxf)
        track1 = Track.from_dxf(
            doc, layer_name=self.cfg.track_layer, handle=self.cfg.track_handle, name="track1"
        )

        if self.cfg.platform_type == PlatformType.SIDE:
            result = side_platform(track1, self.cfg) #for side platform
        else: #for island platform
            track2 = Track.from_dxf(
                doc,
                layer_name=self.cfg.second_track_layer,
                handle=self.cfg.second_track_handle,
                name="track2",
            )
            result = island_platform(track1, track2, self.cfg)

        return result, doc

    def run(self) -> PlatformResult:
        from platform_gen.dxf_io import write_platform

        result, doc = self.build()
        write_platform(doc, result, self.cfg)
        doc.saveas(self.cfg.output_dxf)
        return result
