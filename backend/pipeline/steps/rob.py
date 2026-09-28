"""Road-over-bridge (ROB) pipeline step."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

import ezdxf

from common.alignment import point_at_chainage
from common.geometry import Point, nearest_point_on_alignment, polyline_length
from rob.config import ROBConfig
from rob.geometry import generate_rob_geometry, write_rob

from .base import PipelineStep
from .chainage_collect import station_centres_from_dxf

__all__ = ["RobStep", "RobMixin"]


class RobStep(PipelineStep):
    """Pipeline step: Road-over-bridge (ROB) structures."""

    def _generate_robs(self, tracks: Dict[str, Sequence[Point]]) -> None:
        """Generate Road Over Bridge decks positioned relative to platform ends."""
        if not getattr(self.config, "robs", None):
            return

        doc = ezdxf.readfile(self.config.output_dxf)

        # Wipe existing layers for ROBs
        targets = {cfg.output_layer for cfg in self.config.robs}
        targets.update({"ROB", "SGFD"})
        targets.update(f"{t}-DIM" for t in list(targets))
        targets.update(f"{t}-CENTER" for t in list(targets))
        targets.update(
            layer.dxf.name
            for layer in doc.layers
            if re.fullmatch(r"(ROB|SGFD)(_\d+)?(-DIM|-CENTER)?", layer.dxf.name or "")
        )
        self._wipe_layers(doc, targets)

        # Collect available platform polygons from DXF
        polygons: Dict[str, List[Point]] = {}
        for request in getattr(self.config, "platforms", []):
            layer = request.config.output_layer
            found = self._platform_polygons(doc, layer)
            if found:
                polygons[layer] = found[0]

        centres = station_centres_from_dxf(doc)

        for number, cfg in enumerate(self.config.robs, 1):
            if number == 1:
                cfg.block_name = getattr(cfg, "block_name", "") or "SGFD"
            else:
                cfg.block_name = (
                    getattr(cfg, "block_name", "")
                    if getattr(cfg, "block_name", "") != "SGFD"
                    else f"SGFD_{number}"
                )
            ref_track = cfg.reference_track or "MAIN_LINE"
            ref_pts = tracks.get(ref_track) or tracks.get("MAIN_LINE")
            if ref_pts is None:
                raise ValueError(
                    f"ROB reference track {ref_track!r} not found in tracks."
                )

            total_len = polyline_length([(float(p[0]), float(p[1])) for p in ref_pts])

            # Resolve platform boundaries (start and end chainage)
            plat_start, plat_end = self._resolve_platform_bounds(
                cfg, doc, polygons, ref_pts, total_len
            )

            # Apply user rule:
            # If user choose platform start: platform start - offset
            # If user choose platform end: platform end + offset
            ref_end = cfg.reference_end.upper()
            offset = float(cfg.offset)
            if ref_end == "START":
                rob_ch = plat_start - offset
            else:
                rob_ch = plat_end + offset

            # Check alignment boundary
            if rob_ch < 0.0 or rob_ch > total_len:
                print(
                    f"    ! Warning: ROB {cfg.id} calculated chainage {rob_ch:.2f} m "
                    f"is outside track bounds [0.0, {total_len:.2f} m]. Clamping."
                )
                rob_ch = max(0.0, min(total_len, rob_ch))

            # Resolve chainage text (station-relative if station is present)
            cfg._calculated_chainage = rob_ch
            station_datum_ch = None
            if centres:
                try:
                    st_proj = nearest_point_on_alignment([(float(p[0]), float(p[1])) for p in ref_pts], centres[0])
                    station_datum_ch = float(st_proj.chainage)
                except Exception:
                    station_datum_ch = None

            if getattr(cfg, "chainage", None):
                raw_ch = str(cfg.chainage).strip()
                ch_text = raw_ch if raw_ch.upper().startswith("BR.CH") else f"BR.CH- {raw_ch}"
            elif station_datum_ch is not None:
                rel_ch = rob_ch - station_datum_ch
                cfg._station_relative_chainage = rel_ch
                if rel_ch > 0:
                    rel_str = f"+{rel_ch:.2f}"
                elif rel_ch < 0:
                    rel_str = f"{rel_ch:.2f}"
                else:
                    rel_str = "0.00"
                ch_text = f"BR.CH- {rel_str}"
            else:
                ch_text = f"BR.CH- {rob_ch:.2f}"

            print(
                f"    [ROB] {number} ({cfg.id}): Platform {cfg.platform} "
                f"[{plat_start:.2f} m – {plat_end:.2f} m], "
                f"reference_end={ref_end}, offset={offset:g} m -> "
                f"chainage={rob_ch:.2f} m ({ch_text}), width={cfg.width:g} m"
            )

            sp = point_at_chainage(ref_pts, rob_ch)
            geom = generate_rob_geometry(
                sp.point,
                sp.tangent,
                tracks,
                cfg,
                chainage=rob_ch,
                chainage_text=ch_text,
            )
            write_rob(doc, geom, cfg)
            cfg._geom = geom
            cfg._normal = geom.normal
            # Top offset: deck span + flared wings + width dimension clearance (if enabled)
            top_span = geom.wing_span[1] + (2.5 if getattr(cfg, "add_dimension", True) else 0.5)
            bot_span = geom.wing_span[0] - 0.5
            cfg._top_offset = top_span
            cfg._bottom_offset = bot_span

        doc.saveas(self.config.output_dxf)

    def _resolve_platform_bounds(
        self,
        cfg: ROBConfig,
        doc,
        polygons: Dict[str, List[Point]],
        ref_pts: Sequence[Point],
        total_len: float,
    ) -> tuple[float, float]:
        """Find start and end chainage of the referenced platform."""
        target_name = (cfg.platform or "").strip().upper()

        # 1. Try polygon from DXF
        matched_poly = None
        for name, poly in polygons.items():
            if name.upper() == target_name:
                matched_poly = poly
                break

        if not matched_poly:
            # Try to query doc directly
            found = self._platform_polygons(doc, cfg.platform)
            if found:
                matched_poly = found[0]

        if matched_poly:
            ch_list = [
                float(nearest_point_on_alignment(ref_pts, pt).chainage)
                for pt in matched_poly
            ]
            if ch_list:
                return min(ch_list), max(ch_list)

        # 2. Try platform config request
        for req in getattr(self.config, "platforms", []):
            pcfg = req.config
            if (
                pcfg.output_layer.upper() == target_name
                or pcfg.platform_name.upper() == target_name
            ):
                start = pcfg.resolved_start_chainage(total_len)
                end = pcfg.resolved_end_chainage(total_len)
                return start, end

        if getattr(self.config, "platforms", None):
            first_pcfg = self.config.platforms[0].config
            start = first_pcfg.resolved_start_chainage(total_len)
            end = first_pcfg.resolved_end_chainage(total_len)
            return start, end

        start = max(0.0, (total_len - 550.0) / 2.0)
        return start, start + 550.0

    def _platform_polygons(self, doc, layer: str) -> List[List[Point]]:
        """Extract platform polygons from a DXF layer."""
        polygons: List[List[Point]] = []
        for entity in doc.modelspace():
            if entity.dxf.layer != layer or entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            if hasattr(entity, "get_points"):
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            elif hasattr(entity, "vertices"):
                pts = [(float(v.dxf.location[0]), float(v.dxf.location[1])) for v in entity.vertices]
            else:
                pts = []
            if len(pts) >= 3:
                polygons.append(pts)
        return polygons


class RobMixin(RobStep):
    """Mixin for backward compatibility and orchestrator composition."""
    pass

