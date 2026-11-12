"""Dead-end sidings."""

from __future__ import annotations

import re

import ezdxf

from common.geometry import polyline_length
from platform_gen.geometry import point_at_chainage as _pac
from track.drawing import _add_spline as _add_crossover_spline, _add_track_label, _draw_srj_post
from track.siding import (
    build_siding_points as _build_siding,
    draw_siding_dead_end as _draw_siding_dead_end,
    portion_from as _siding_portion,
    validate_siding as _validate_siding,
)
from track.turnouts import select_turnout as _select_turnout

from .base import PipelineStep

__all__ = ["SidingStep", "SidingMixin"]


class SidingStep(PipelineStep):
    """Pipeline step: Dead-end sidings."""

    def _siding_srjs_on_track(self, track: str) -> list:
        """(chainage, direction, label) of accepted crossover SRJs on a track."""
        srjs = []
        for res in getattr(self, "_crossover_results", None) or []:
            if getattr(res, "from_track", None) == track:
                srjs.append((
                    float(res.chainage),
                    str(getattr(res, "direction", "FORWARD")),
                    f"crossover {res.id} START",
                ))
            if getattr(res, "to_track", None) == track:
                second = (
                    res.end_chainage
                    if getattr(res, "placement", None) == "AHEAD"
                    else res.start_chainage
                )
                srjs.append((
                    float(second),
                    str(getattr(res, "direction", "FORWARD")),
                    f"crossover {res.id} second SRJ",
                ))
        return srjs

    def _generate_sidings(self, tracks: dict) -> None:
        """Dead-end sidings: fixed turnout geometry, validated, never moved."""
        if not getattr(self.config, "sidings", None):
            self._siding_results = []
            return
        self._siding_results = []
        doc = ezdxf.readfile(self.config.output_dxf)
        targets = {f"SIDING_{number}" for number, _ in enumerate(self.config.sidings, 1)}
        targets.update(
            layer.dxf.name
            for layer in doc.layers
            if re.fullmatch(r"SIDING_\d+", layer.dxf.name or "")
        )
        self._wipe_layers(doc, targets) #it deletes the old entity so that new entity can be easily drawn without any duplication
        extents = self._loop_main_extents()
        platform_outlines = []
        for layer in self.platform_layers:
            found = self._platform_polygons(doc, layer)
            if found:
                platform_outlines.append((layer, found[0]))
        station_outlines = [
            [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
            for box in self._station_footprints(doc)
        ]
        accepted = []
        for number, spec in enumerate(self.config.sidings, 1):
            sid = getattr(spec, "id", None) or f"S{number}"
            layer = f"SIDING_{number}"
            if spec.source_track not in tracks:
                known = ", ".join(sorted(tracks)) or "(none)"
                raise ValueError(
                    f"Siding {sid} references unknown track {spec.source_track!r} - available: {known}."
                )
            src_points = tracks[spec.source_track]
            total = polyline_length(src_points)
            start = float(spec.start_chainage_m)
            if not 0.0 <= start <= total:
                raise ValueError(
                    f"Siding {sid} start chainage {start:.3f} m is outside {spec.source_track} [0, {total:.3f}] MAIN m."
                )
            extent = extents.get(spec.source_track)
            local = start - extent[0] if extent is not None else start
            track_len = polyline_length(src_points)
            if extent is not None and not (-1e-3 <= start - extent[0] <= track_len + 1e-3):
                raise ValueError(
                    f"Siding {sid} start chainage {start:.3f} m is outside "
                    f"{spec.source_track} effective extent "
                    f"[{extent[0]:.3f}, {extent[1]:.3f}] MAIN m - move the "
                    f"siding start. Siding geometry is never moved automatically."
                )
            local = min(max(local, 0.0), track_len)
            turnout = _select_turnout(
                spec.turnout_designation, spec.turnout_variant or "standard"
            )
            result = _build_siding(
                src_points,
                local,
                spec.direction,
                spec.side,
                turnout,
                float(spec.spacing),
                float(spec.standing_length_m),
            )
            _validate_siding(
                sid,
                spec.source_track,
                start,
                spec.direction,
                result,
                tracks,
                self._siding_srjs_on_track(spec.source_track),
                platform_outlines,
                station_outlines,
                accepted,
            )
            if layer not in doc.layers:
                doc.layers.add(layer, color=1)
            _add_crossover_spline(doc, result.points, layer, 1)
            _draw_siding_dead_end(
                doc,
                result.tip,
                result.tip_tangent,
                layer,
                1,
                standing_length_m=float(spec.standing_length_m),
            )
            sp = _pac(src_points, local)
            _draw_srj_post(
                doc,
                sp.point,
                sp.tangent,
                str(spec.side).strip().upper() == "LEFT",
            )
            parallel_pts = _siding_portion(result.points, result.ladder_length_m)
            _add_track_label(
                doc,
                f"Siding {number}",
                parallel_pts if len(parallel_pts) >= 2 else result.points,
                layer,
                1,
                1.0,
            )
            accepted.append((sid, start, str(spec.direction).strip().upper(), result))
            self._siding_results.append((spec, result))
            print(
                f"   OK Siding {sid} ({spec.source_track}@{start:.3f}m "
                f"{spec.direction} {spec.side} [{spec.turnout_designation}]) "
                f"standing={result.standing_length_m:.1f}m "
                f"total={result.total_length_m:.1f}m "
                f"tip=({result.tip[0]:.2f}, {result.tip[1]:.2f})"
            )
        doc.saveas(self.config.output_dxf)


class SidingMixin(SidingStep):
    """Mixin for backward compatibility."""
    pass
