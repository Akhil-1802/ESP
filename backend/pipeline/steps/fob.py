"""Foot-over-bridge decks."""

from __future__ import annotations

import re

import ezdxf

from common.chainage import StationDatum
from common.geometry import polyline_length
from fob.config import DEFAULT_FOB_OFFSET_M, normalize_fob_direction
from fob.deck import generate_fob as _generate_fob_deck, resolve_fob_chainage
from fob.placement import determine_station_edge, validate_fob_conflicts
from track.crossover import platforms_to_restricted_regions, stations_to_restricted_regions

from .base import PipelineStep

__all__ = ["FobStep", "FobMixin"]


class FobStep(PipelineStep):
    """Pipeline step: Foot-over-bridge decks."""

    def _generate_fobs(self, tracks: dict) -> None:
        """Generate basic FOB decks (needs platforms already in place)."""
        if not getattr(self.config, "fobs", None):
            return
        doc = self._load_document()
        targets = {cfg.output_layer for cfg in self.config.fobs}
        targets.update(
            getattr(cfg, "dimension_layer", "") or f"{cfg.output_layer}-DIM"
            for cfg in self.config.fobs
        )
        targets.update(
            layer.dxf.name
            for layer in doc.layers
            if re.fullmatch(r"FOB_\d+(-DIM)?", layer.dxf.name or "") or layer.dxf.name == "FOB-DIM"
        )
        self._wipe_layers(doc, targets)
        extents = self._loop_main_extents()
        polygons: dict[str, list] = {}
        for request in self.config.platforms:
            layer = request.config.output_layer
            found = self._platform_polygons(doc, layer)
            if found:
                polygons[layer] = found[0]

        for number, cfg in enumerate(self.config.fobs, 1):
            ref_pts = tracks.get(cfg.reference_track)
            if ref_pts is None:
                raise ValueError(f"FOB reference track {cfg.reference_track!r} not found in tracks.")

            total_len = polyline_length([(float(p[0]), float(p[1])) for p in ref_pts])

            is_main_center = (
                cfg.reference_chainage is None
                or (
                    isinstance(cfg.reference_chainage, str)
                    and cfg.reference_chainage.strip().upper() in ("MAIN_CENTER", "AUTO", "")
                )
            )
            station_buildings = self._platform_polygons(doc, "STATION-BUILDING")

            station_geom = None
            if station_buildings:
                station_geom = station_buildings[0]

            fob_ch = resolve_fob_chainage(
                cfg,
                tracks,
                polygons_by_layer=polygons,
                doc=doc,
                station_requests=getattr(self.config, "stations", None),
                station_markers=getattr(self.config, "station_markers", None),
            )

            offset = float(cfg.offset) if cfg.offset is not None else DEFAULT_FOB_OFFSET_M
            direction = normalize_fob_direction(cfg.direction)

            print(
                f"    Calculated FOB chainage: {fob_ch:.3f} m\n"
                f"    Offset: {offset:.3f} m\n"
                f"    Direction: {direction}"
            )

            restrictions = []
            try:
                unconnected = []
                for p in (self.config.platforms or []):
                    layer = getattr(p, "output_layer", None)
                    if layer is None and hasattr(p, "config"):
                        layer = getattr(p.config, "output_layer", None)
                    if layer not in cfg.platforms:
                        unconnected.append(p)
                restrictions.extend(platforms_to_restricted_regions(unconnected, tracks, extents))
            except Exception:
                pass
            try:
                restrictions.extend(
                    stations_to_restricted_regions(self.config.stations, self.config.platforms, tracks, extents)
                )
            except Exception:
                pass

            validate_fob_conflicts(
                fob_ch,
                cfg.width,
                cfg.reference_track,
                tracks,
                polygons,
                cfg.platforms,
                station_polygons=station_buildings,
                restricted_regions=restrictions,
                arm_specs=getattr(cfg, "arms", None),
            )

            cfg.reference_chainage = fob_ch
            cfg.fob_chainage = fob_ch

            _generate_fob_deck(doc, tracks, extents, polygons, cfg)
            print(
                f"   OK FOB {number} ({cfg.reference_track}@"
                f"{fob_ch:.3f}m -> "
                f"{', '.join(cfg.platforms)}) width={cfg.width:g}m "
                f"[{cfg.output_layer}]"
            )
        self._save_document(doc)


class FobMixin(FobStep):
    """Mixin for backward compatibility."""
    pass
