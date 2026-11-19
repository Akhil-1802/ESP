"""Bridge placement, shared symbol rendering, and resolved engineering results."""
from ...domain.bridges.bridge.geometry import generate_bridge_geometry, write_bridge
from ...domain.bridges.bridge.placement import resolve_bridge_placement
from .base import PipelineStep


class BridgeStep(PipelineStep):
    def _generate_bridges(self, tracks):
        if not self.config.bridges:
            return
        doc = self._load_document()
        targets = {cfg.output_layer for cfg in self.config.bridges}
        targets |= {f"{layer}-{suffix}" for layer in list(targets) for suffix in ("DIM", "CENTER")}
        self._wipe_layers(doc, targets)
        for number, cfg in enumerate(self.config.bridges, 1):
            placement = resolve_bridge_placement(cfg, self.config, tracks)
            # Each instance owns a block: dimensions must not redefine earlier bridges.
            cfg.block_name = f"BRIDGE_{number}"
            geom = generate_bridge_geometry(
                placement.point, placement.tangent, tracks, cfg,
                chainage=placement.distance,
                chainage_text=f"CH {placement.absolute_chainage:.3f} M",
            )
            write_bridge(doc, geom, cfg)
            cfg._geom = geom
            cfg._calculated_chainage = placement.distance
            cfg._absolute_chainage = placement.absolute_chainage
            cfg._normal = geom.normal
            cfg._top_offset = geom.wing_span[1] + (2.5 if cfg.add_dimension else 0.5)
            cfg._bottom_offset = geom.wing_span[0] - 0.5
        self._save_document(doc)
