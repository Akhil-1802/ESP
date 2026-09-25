"""Foot-over-bridge decks."""

from __future__ import annotations

import re

import ezdxf

from common.chainage import StationDatum
from common.geometry import polyline_length
from fob.config import DEFAULT_FOB_OFFSET_M, normalize_fob_direction
from fob.deck import generate_fob as _generate_fob_deck
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
        doc = ezdxf.readfile(self.config.output_dxf)
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
                cx = sum(p[0] for p in station_geom) / len(station_geom)
                cy = sum(p[1] for p in station_geom) / len(station_geom)
                st_center = (cx, cy)
            else:
                plat_polys = [polygons[p] for p in cfg.platforms if p in polygons]
                if plat_polys:
                    station_geom = plat_polys
                    all_pts = [pt for p in plat_polys for pt in p]
                    st_center = (
                        sum(pt[0] for pt in all_pts) / len(all_pts),
                        sum(pt[1] for pt in all_pts) / len(all_pts),
                    )
                else:
                    st_center = (ref_pts[len(ref_pts) // 2][0], ref_pts[len(ref_pts) // 2][1])
                    station_geom = None

            datum = StationDatum(st_center, tracks)
            center_ch = datum.station_chainage_on(cfg.reference_track)
            if center_ch is None or center_ch <= 0.0:
                center_ch = total_len / 2.0

            if is_main_center:
                ref_chainage = float(center_ch)
            else:
                ref_chainage = float(cfg.reference_chainage)

            offset = float(cfg.offset) if cfg.offset is not None else DEFAULT_FOB_OFFSET_M
            direction = normalize_fob_direction(cfg.direction)

            station_edge_ch = None
            edge_geom = station_geom
            if edge_geom is not None:
                try:
                    station_edge_ch = determine_station_edge(ref_pts, edge_geom, direction)
                except Exception:
                    station_edge_ch = None

            arm_towards_station = 0.0
            towards_side = "LEFT" if direction == "INCREASING" else "RIGHT"
            for arm_spec in (cfg.arms or {}).values():
                if isinstance(arm_spec, dict) and str(arm_spec.get("side", "")).upper() == towards_side:
                    arm_towards_station = max(arm_towards_station, float(arm_spec.get("length", 0.0)))
            extra_to_center = (float(cfg.width) / 2.0) + arm_towards_station

            is_at_center = is_main_center or abs(ref_chainage - center_ch) < 2.0
            if is_at_center:
                base_ch = station_edge_ch if station_edge_ch is not None else ref_chainage
                if direction == "INCREASING":
                    fob_ch = base_ch + offset + extra_to_center
                else:
                    fob_ch = base_ch - (offset + extra_to_center)
            else:
                fob_ch = ref_chainage

            print(
                f"    Reference chainage: {ref_chainage:.3f} m\n"
                f"    Station edge: {station_edge_ch:.3f} m\n" if station_edge_ch is not None else
                f"    Reference chainage: {ref_chainage:.3f} m\n"
                f"    Station edge: (not found, using reference)\n"
            )
            print(
                f"    Offset: {offset:.3f} m\n"
                f"    Direction: {direction}\n"
                f"    Calculated FOB chainage: {fob_ch:.3f} m"
            )

            restrictions = []
            try:
                restrictions.extend(platforms_to_restricted_regions(self.config.platforms, tracks, extents))
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
        doc.saveas(self.config.output_dxf)


class FobMixin(FobStep):
    """Mixin for backward compatibility."""
    pass
