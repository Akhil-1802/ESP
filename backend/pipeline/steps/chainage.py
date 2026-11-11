"""Station-relative chainage labels (final annotation pass)."""

from __future__ import annotations

import math

import ezdxf

from common.chainage import (
    CHAINAGE_LAYER,
    CHAINAGE_OUTER_MARGIN_M,
    CHAINAGE_PARALLEL_TOL_M,
    StationDatum,
    draw_chainage_annotation,
)
from common.geometry import point_at_chainage, polyline_length
from platform_gen.track import _extract_points as _xpts
from station.station_flag import draw_station_flag

from .base import PipelineStep
from .chainage_collect import (
    collect_dead_ends,
    collect_fm,
    collect_fob,
    collect_robs,
    collect_optional_layers,
    collect_platform_ends,
    collect_siding,
    collect_srj_turnout_crossover,
    determine_side,
    determine_track_side,
    station_centres_from_dxf,
)

__all__ = ["ChainageStep", "ChainageMixin"]

_TEXT_LIFT = {
    "SRJ": 0.0,
    "FM": 0.0,
    "DE": 0.0,
    "SIDING": 0.0,
    "PF END": 0.0,
    "RAMP END": 0.0,
    "LC": 0.0,
    "BRIDGE": 0.0,
    "BR": 0.0,
}

_STUB_GAP_M = 2.0
_DEDUPE_M = 2.0


def _calc_text_insert(p_base, normal, tangent, dist_start, text_len, rot_deg, side_offset=0.0):
    """Calculate DXF text insertion point along a given normal ray.

    Ensures that regardless of whether rot_deg is parallel (+1) or antiparallel (-1)
    to the normal direction, the text occupies the region [dist_start, dist_start + text_len]
    away from p_base along normal, preventing it from extending back towards or crossing the track.
    """
    nx, ny = normal
    tx, ty = tangent
    vx = math.cos(math.radians(rot_deg))
    vy = math.sin(math.radians(rot_deg))
    dot = vx * nx + vy * ny
    if dot >= 0:
        d_ins = dist_start
    else:
        d_ins = dist_start + text_len
    return (
        p_base[0] + nx * d_ins + tx * side_offset,
        p_base[1] + ny * d_ins + ty * side_offset,
    )


class ChainageStep(PipelineStep):
    """Pipeline step: station-relative chainage labels."""

    def _station_centres_from_dxf(self, doc) -> list:
        return station_centres_from_dxf(doc)

    def _track_side(self, track_name: str | None, default_to: str | None = None, configured_side: str | None = None, pt=None) -> str:
        return determine_track_side(
            track_name,
            self.config,
            default_to=default_to,
            configured_side=configured_side,
            pt=pt,
            main_line_points=getattr(self, "_main_line_points", None),
        )

    def _determine_side(self, pt, host_track: str | None = None, configured_side: str | None = None) -> str:
        return determine_side(
            pt,
            main_line_points=getattr(self, "_main_line_points", None),
            config=self.config,
            host_track=host_track,
            configured_side=configured_side,
        )

    def _collect_platform_ends(self, doc, tracks, datum) -> list:
        return collect_platform_ends(
            doc, tracks, datum, self.config, getattr(self, "_main_line_points", None)
        )

    def _collect_srj_turnout_crossover(self, tracks, extents, datum) -> list:
        return collect_srj_turnout_crossover(
            tracks,
            extents,
            datum,
            getattr(self, "_crossover_results", None) or [],
            getattr(self, "_siding_results", None) or [],
            self.config,
            getattr(self, "_main_line_points", None),
        )

    def _collect_siding(self, tracks, extents, datum, tracks_for_datum) -> list:
        return collect_siding(
            tracks,
            extents,
            datum,
            getattr(self, "_siding_results", None) or [],
            self.config,
            getattr(self, "_main_line_points", None),
        )

    def _collect_fm(self, datum) -> list:
        return collect_fm(
            datum,
            getattr(self, "_fouling_marks", None) or [],
            self.config,
            getattr(self, "_main_line_points", None),
        )

    def _collect_dead_ends(self, doc, tracks_for_datum, datum) -> list:
        return collect_dead_ends(
            doc, tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None)
        )

    def _collect_fob(self, tracks, extents, datum) -> list:
        return collect_fob(tracks, extents, datum)

    def _collect_robs(self, tracks_for_datum, datum) -> list:
        return collect_robs(tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None))

    def _collect_optional_layers(self, doc, tracks_for_datum, datum) -> list:
        return collect_optional_layers(doc, tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None))

    def _generate_station_chainage_labels(self, tracks: dict) -> None:
        """Add station-relative chainage leaders + labels (additive only)."""
        try:
            doc = ezdxf.readfile(self.config.output_dxf)
        except Exception as exc:
            print(f"   ! Station chainage labels skipped ({exc})")
            return
        centres = self._station_centres_from_dxf(doc)
        if not centres:
            print("   ! Station chainage labels skipped (no STATION-BUILDING found)")
            return
        center = centres[0]

        tracks_for_datum: dict = {
            k: list(v) for k, v in (tracks or {}).items() if v is not None and len(list(v)) >= 2
        }
        for number, item in enumerate(list(getattr(self, "_siding_results", None) or []), 1):
            try:
                _spec, result = item
                pts = list(getattr(result, "points", None) or [])
                if len(pts) >= 2:
                    tracks_for_datum.setdefault(f"SIDING_{number}", pts)
            except Exception:
                continue

        main_raw = tracks_for_datum.get("MAIN_LINE")
        if main_raw is None:
            for k in sorted(tracks_for_datum):
                if "MAIN" in str(k).upper():
                    main_raw = tracks_for_datum[k]
                    break
        if main_raw is None and tracks_for_datum:
            main_raw = next(iter(tracks_for_datum.values()))
        self._main_line_points = [(float(p[0]), float(p[1])) for p in (main_raw or [])]

        try:
            extents = self._loop_main_extents()
        except Exception:
            extents = {}
        try:
            datum = StationDatum(center, tracks_for_datum)
        except Exception as exc:
            print(f"   ! Station chainage labels skipped ({exc})")
            return
        if not datum.has_datum:
            print("   ! Station chainage labels skipped (no track datum)")
            return

        markers: list = []
        markers += self._collect_platform_ends(doc, tracks_for_datum, datum)
        markers += self._collect_srj_turnout_crossover(tracks_for_datum, extents, datum)
        markers += self._collect_siding(tracks_for_datum, extents, datum, tracks_for_datum)
        markers += self._collect_fm(datum)
        markers += self._collect_dead_ends(doc, tracks_for_datum, datum)
        markers += self._collect_fob(tracks_for_datum, extents, datum)
        markers += self._collect_robs(tracks_for_datum, datum)
        markers += self._collect_optional_layers(doc, tracks_for_datum, datum)
        if not markers:
            print("   ! Station chainage labels: no markers found")
            return

        try:
            for entity in list(doc.modelspace()):
                try:
                    if entity.dxf.layer == CHAINAGE_LAYER:
                        doc.modelspace().delete_entity(entity)
                except Exception:
                    continue
        except Exception:
            pass

        norm_markers = []
        for m in markers:
            if len(m) >= 5:
                norm_markers.append((m[0], m[1], m[2], m[3], m[4]))
            else:
                s = self._determine_side(m[0])
                norm_markers.append((m[0], m[1], m[2], m[3], s))

        try:
            parallel_tol = float(CHAINAGE_PARALLEL_TOL_M)
        except (TypeError, ValueError):
            parallel_tol = 1.0

        # When an FM is coincident with an SRJ (same chainage within parallel_tol),
        # suppress the standalone FM marker so a redundant second leader line is not drawn,
        # but keep track of fm_rels so the SRJ line can display FM on the opposite side of the line.
        srj_rels = [float(m[2]) for m in norm_markers if str(m[3]).upper() == "SRJ"]
        fm_rels = [float(m[2]) for m in norm_markers if str(m[3]).upper() == "FM"]
        filtered_markers = []
        for m in norm_markers:
            tag = str(m[3]).upper()
            if tag == "FM":
                rel = float(m[2])
                if any(abs(rel - srj_ch) < parallel_tol for srj_ch in srj_rels):
                    continue
            filtered_markers.append(m)
        norm_markers = filtered_markers

        def _dedupe_side_group(items):
            kept_group: list = []
            for base, tan, rel, tag, side in items:
                dup = False
                for i, (kb, _kt, kr, ktag, _kside) in enumerate(kept_group):
                    is_close = math.hypot(base[0] - kb[0], base[1] - kb[1]) < _DEDUPE_M
                    if not is_close:
                        try:
                            if abs(float(rel) - float(kr)) < parallel_tol:
                                is_close = True
                        except (TypeError, ValueError):
                            pass
                    if is_close:
                        if ktag == tag:
                            dup = True
                            break
                        if {ktag, tag} == {"SRJ", "FM"}:
                            dup = True
                            if tag == "SRJ":
                                kept_group[i] = (base, tan, rel, tag, side)
                            break
                if not dup:
                    kept_group.append((base, tan, rel, tag, side))
            return kept_group

        left_markers = _dedupe_side_group([m for m in norm_markers if m[4] == "LEFT"])
        right_markers = _dedupe_side_group([m for m in norm_markers if m[4] == "RIGHT"])

        ref_n = None
        try:
            main_pts = self._main_line_points
            main_datum_ch = datum.station_chainage_on("MAIN_LINE")
            if main_pts is not None and len(main_pts) >= 2:
                total = polyline_length(main_pts)
                ch = float(main_datum_ch) if main_datum_ch is not None else 0.0
                st = point_at_chainage(main_pts, min(max(ch, 0.0), total))
                tx, ty = float(st.tangent[0]), float(st.tangent[1])
                an = math.hypot(tx, ty) or 1.0
                ref_n = (-ty / an, tx / an)
        except Exception:
            ref_n = None
        if ref_n is None:
            try:
                tx, ty = (left_markers or right_markers)[0][1]
                an = math.hypot(float(tx), float(ty)) or 1.0
                ref_n = (-float(ty) / an, float(tx) / an)
            except Exception:
                ref_n = (0.0, 1.0)
        try:
            margin = float(CHAINAGE_OUTER_MARGIN_M)
        except (TypeError, ValueError):
            margin = 12.0
        gap = float(_STUB_GAP_M)
        pseudo_tan = (float(ref_n[1]), float(-ref_n[0]))

        _EXCLUDED = ("TEXT", "DIM", "CENTER", "CHAINAGE", "DEFPOINTS", "FLAG")
        edges: list = []
        circles: list = []
        try:
            for pts in tracks_for_datum.values():
                cleaned = [(float(p[0]), float(p[1])) for p in pts]
                for a, b in zip(cleaned, cleaned[1:]):
                    edges.append((a, b))
        except Exception:
            pass
        try:
            for entity in doc.modelspace():
                try:
                    upper = str(entity.dxf.layer or "").upper()
                except Exception:
                    continue
                if any(key in upper for key in _EXCLUDED):
                    continue
                kind = entity.dxftype()
                try:
                    if kind in ("LWPOLYLINE", "POLYLINE"):
                        raw = None
                        if _xpts is not None:
                            try:
                                raw = [(float(p[0]), float(p[1])) for p in _xpts(entity)]
                            except Exception:
                                raw = None
                        if raw is None:
                            try:
                                raw = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                            except Exception:
                                continue
                        if len(raw) >= 2 and raw[0] == raw[-1]:
                            raw = raw[:-1]
                        if len(raw) < 2:
                            continue
                        try:
                            closed = bool(getattr(entity, "is_closed", False))
                        except Exception:
                            closed = False
                        try:
                            if not closed and (int(entity.dxf.get("flags", 0)) & 1):
                                closed = True
                        except Exception:
                            pass
                        for a, b in zip(raw, raw[1:]):
                            edges.append((a, b))
                        if closed and len(raw) >= 3:
                            edges.append((raw[-1], raw[0]))
                    elif kind == "LINE":
                        s, e = entity.dxf.start, entity.dxf.end
                        edges.append((((float(s.x), float(s.y))), ((float(e.x), float(e.y)))))
                    elif kind == "SPLINE":
                        seq = None
                        try:
                            fp = getattr(entity, "fit_points", None)
                            if fp is not None and len(list(fp)) >= 2:
                                seq = [(float(p.x), float(p.y)) for p in fp]
                        except Exception:
                            seq = None
                        if seq is None:
                            try:
                                cp = getattr(entity, "control_points", None)
                                if cp is not None and len(list(cp)) >= 2:
                                    seq = [(float(p.x), float(p.y)) for p in cp]
                            except Exception:
                                seq = None
                        if seq is not None:
                            for a, b in zip(seq, seq[1:]):
                                edges.append((a, b))
                    elif kind == "CIRCLE":
                        c, r = entity.dxf.center, float(entity.dxf.radius)
                        circles.append((float(c.x), float(c.y), float(r)))
                    elif kind == "ARC":
                        c, r = entity.dxf.center, float(entity.dxf.radius)
                        circles.append((float(c.x), float(c.y), float(r)))
                except Exception:
                    continue
        except Exception:
            pass

        center_along = float(center[0]) * pseudo_tan[0] + float(center[1]) * pseudo_tan[1]
        center_proj = float(center[0]) * ref_n[0] + float(center[1]) * ref_n[1]

        # Determine reference projection of the MAIN track datum
        main_datum_proj = center_proj
        try:
            main_pts = self._main_line_points
            main_datum_ch = datum.station_chainage_on("MAIN_LINE")
            if main_pts is not None and len(main_pts) >= 2:
                total_len = polyline_length(main_pts)
                ch = float(main_datum_ch) if main_datum_ch is not None else 0.0
                st = point_at_chainage(main_pts, min(max(ch, 0.0), total_len))
                main_datum_proj = float(st.point[0]) * ref_n[0] + float(st.point[1]) * ref_n[1]
        except Exception:
            main_datum_proj = center_proj

        # Station flag axis is at ~25.0m from the station reference on UP (LEFT)
        flag_axis_left = center_proj + 25.0
        # Symmetrical axis on DOWN (RIGHT) uses the same distance from MAIN track datum in opposite direction
        flag_dist_from_main = flag_axis_left - main_datum_proj
        flag_axis_right = main_datum_proj - flag_dist_from_main

        try:
            projs: list = []
            for (a, b) in edges:
                along_a = a[0] * pseudo_tan[0] + a[1] * pseudo_tan[1]
                along_b = b[0] * pseudo_tan[0] + b[1] * pseudo_tan[1]
                # Only consider entities in the station yard vicinity (within ±850m)
                if abs(along_a - center_along) <= 850.0 or abs(along_b - center_along) <= 850.0:
                    projs.append(a[0] * ref_n[0] + a[1] * ref_n[1])
                    projs.append(b[0] * ref_n[0] + b[1] * ref_n[1])
            for (cx, cy, r) in circles:
                along_c = cx * pseudo_tan[0] + cy * pseudo_tan[1]
                if abs(along_c - center_along) <= 850.0:
                    projs.append(cx * ref_n[0] + cy * ref_n[1] + abs(r))
                    projs.append(cx * ref_n[0] + cy * ref_n[1] - abs(r))
            for base, _tan, _rel, _tag, _side in norm_markers:
                projs.append(float(base[0]) * ref_n[0] + float(base[1]) * ref_n[1])
            try:
                projs.append(float(center[0]) * ref_n[0] + float(center[1]) * ref_n[1])
            except Exception:
                pass
            if projs:
                outer_left = max(projs) + margin
                outer_right = min(projs) - margin
            else:
                outer_left, outer_right = None, None
        except Exception:
            outer_left, outer_right = None, None

        if outer_left is None or not math.isfinite(outer_left):
            print("   ! Station chainage labels skipped (no outer line)")
            return

        _common_end_left = float(outer_left) + float(gap)
        _common_end_right = float(outer_right) - float(gap)

        # Cap leader extension at the axis of the station flag so labels max. reach the flag
        if _common_end_left > flag_axis_left:
            _common_end_left = flag_axis_left

        # Symmetrically align DOWN labels to match the same distance logic in the opposite direction
        up_dist_from_main = abs(_common_end_left - main_datum_proj)
        sym_down_axis = main_datum_proj - up_dist_from_main

        # Ensure DOWN labels reach the symmetrical distance in the opposite direction,
        # while clearing all lower tracks/elements
        _common_end_right = min(sym_down_axis, _common_end_right)
        drawn = 0

        if left_markers and _common_end_left is not None:
            for base, _tan, rel, tag, _side in left_markers:
                try:
                    along = float(base[0]) * pseudo_tan[0] + float(base[1]) * pseudo_tan[1]
                    local_max = None
                    try:
                        for (a, b) in edges:
                            sa = a[0] * pseudo_tan[0] + a[1] * pseudo_tan[1]
                            sb = b[0] * pseudo_tan[0] + b[1] * pseudo_tan[1]
                            lo, hi = (sa, sb) if sa <= sb else (sb, sa)
                            if not (lo - 0.5 <= along <= hi + 0.5):
                                continue
                            denom = sb - sa
                            if abs(denom) < 1e-9:
                                cand = max(a[0] * ref_n[0] + a[1] * ref_n[1], b[0] * ref_n[0] + b[1] * ref_n[1])
                            else:
                                t = (along - sa) / denom
                                t = min(max(t, 0.0), 1.0)
                                cand = (a[0] + t * (b[0] - a[0])) * ref_n[0] + (a[1] + t * (b[1] - a[1])) * ref_n[1]
                            if local_max is None or cand > local_max:
                                local_max = cand
                        for (cx, cy, r) in circles:
                            sc = cx * pseudo_tan[0] + cy * pseudo_tan[1]
                            if abs(sc - along) <= abs(r) + 0.5:
                                cand = cx * ref_n[0] + cy * ref_n[1] + abs(r)
                                if local_max is None or cand > local_max:
                                    local_max = cand
                    except Exception:
                        local_max = None
                    base_proj = float(base[0]) * ref_n[0] + float(base[1]) * ref_n[1]
                    if local_max is None or not math.isfinite(local_max):
                        local_max = float(base_proj)
                    else:
                        local_max = max(float(local_max), float(base_proj))
                    start_proj = float(local_max) + float(gap)
                    if start_proj >= _common_end_left - 1.0:
                        start_proj = _common_end_left - 4.0
                    start = (
                        pseudo_tan[0] * along + ref_n[0] * start_proj,
                        pseudo_tan[1] * along + ref_n[1] * start_proj,
                    )
                    leader_len = float(_common_end_left - start_proj)
                    if not math.isfinite(leader_len) or leader_len < 3.0:
                        leader_len = 3.0
                    other_tag = (
                        "FM"
                        if str(tag).upper() == "SRJ" and any(abs(float(rel) - fm_ch) < parallel_tol for fm_ch in fm_rels)
                        else None
                    )
                    drawn += draw_chainage_annotation(
                        doc,
                        start,
                        pseudo_tan,
                        float(rel),
                        str(tag),
                        leader_len=float(leader_len),
                        lift=float(_TEXT_LIFT.get(str(tag), 0.0)),
                        side="LEFT",
                        other_side_tag=other_tag,
                    )
                except Exception:
                    continue

        if right_markers and _common_end_right is not None:
            for base, _tan, rel, tag, _side in right_markers:
                try:
                    along = float(base[0]) * pseudo_tan[0] + float(base[1]) * pseudo_tan[1]
                    local_min = None
                    try:
                        for (a, b) in edges:
                            sa = a[0] * pseudo_tan[0] + a[1] * pseudo_tan[1]
                            sb = b[0] * pseudo_tan[0] + b[1] * pseudo_tan[1]
                            lo, hi = (sa, sb) if sa <= sb else (sb, sa)
                            if not (lo - 0.5 <= along <= hi + 0.5):
                                continue
                            denom = sb - sa
                            if abs(denom) < 1e-9:
                                cand = min(a[0] * ref_n[0] + a[1] * ref_n[1], b[0] * ref_n[0] + b[1] * ref_n[1])
                            else:
                                t = (along - sa) / denom
                                t = min(max(t, 0.0), 1.0)
                                cand = (a[0] + t * (b[0] - a[0])) * ref_n[0] + (a[1] + t * (b[1] - a[1])) * ref_n[1]
                            if local_min is None or cand < local_min:
                                local_min = cand
                        for (cx, cy, r) in circles:
                            sc = cx * pseudo_tan[0] + cy * pseudo_tan[1]
                            if abs(sc - along) <= abs(r) + 0.5:
                                cand = cx * ref_n[0] + cy * ref_n[1] - abs(r)
                                if local_min is None or cand < local_min:
                                    local_min = cand
                    except Exception:
                        local_min = None
                    base_proj = float(base[0]) * ref_n[0] + float(base[1]) * ref_n[1]
                    if local_min is None or not math.isfinite(local_min):
                        local_min = float(base_proj)
                    else:
                        local_min = min(float(local_min), float(base_proj))
                    start_proj = float(local_min) - float(gap)
                    if start_proj <= _common_end_right + 1.0:
                        start_proj = _common_end_right + 4.0
                    start = (
                        pseudo_tan[0] * along + ref_n[0] * start_proj,
                        pseudo_tan[1] * along + ref_n[1] * start_proj,
                    )
                    leader_len = float(start_proj - _common_end_right)
                    if not math.isfinite(leader_len) or leader_len < 3.0:
                        leader_len = 3.0
                    other_tag = (
                        "FM"
                        if str(tag).upper() == "SRJ" and any(abs(float(rel) - fm_ch) < parallel_tol for fm_ch in fm_rels)
                        else None
                    )
                    drawn += draw_chainage_annotation(
                        doc,
                        start,
                        pseudo_tan,
                        float(rel),
                        str(tag),
                        leader_len=float(leader_len),
                        lift=float(_TEXT_LIFT.get(str(tag), 0.0)),
                        side="RIGHT",
                        other_side_tag=other_tag,
                    )
                except Exception:
                    continue

        try:
            doc.saveas(self.config.output_dxf)
        except Exception as exc:
            print(f"   ! Station chainage labels save skipped ({exc})")
            return
        print(f"   ✓ Station chainage labels: {drawn} (datum C/L {center[0]:.2f},{center[1]:.2f} = 0.000)")

    def _generate_alignment_interval_chainages(self, tracks: dict) -> None:
        """Draw regular alignment interval chainage tick marks along MAIN track.

        Places ticks every 100m (plus start and end points) with:
          - Top text: CH-1+900 (or CH-4 if only KM was specified and m is 0)
          - Bottom text: Ch. 1900 M
        """
        if not tracks:
            return

        # Hide interval chainages over KML file when loop lines, additional tracks, or other features are configured
        explicit_show = getattr(self.config, "show_alignment_chainages", None)
        if explicit_show is False:
            return
        if explicit_show is None:
            loops = getattr(self.config, "loops", None) or []
            additional_lines = getattr(self.config, "additional_lines", None) or []
            platforms = getattr(self.config, "platforms", None) or []
            if len(loops) > 0 or len(additional_lines) > 0 or len(platforms) > 0:
                return

        try:
            doc = ezdxf.readfile(self.config.output_dxf)
        except Exception:
            return

        from common.dxf import ensure_layer, ensure_text_style
        layer_name = "CHAINAGE"
        ensure_layer(doc, layer_name, color=1)
        style_name = ensure_text_style(doc)

        main_pts = tracks.get("MAIN_LINE") or next(iter(tracks.values()), None)
        if not main_pts or len(main_pts) < 2:
            return
        cleaned = [(float(p[0]), float(p[1])) for p in main_pts]
        total_len = polyline_length(cleaned)
        if total_len <= 0:
            return

        start_km_raw = getattr(self.config, "start_km", None)
        start_m_raw = getattr(self.config, "start_m", None)

        has_explicit_m = False
        start_ch_m = 0.0

        if start_km_raw is not None and str(start_km_raw).strip() != "":
            try:
                start_km = float(start_km_raw)
            except ValueError:
                start_km = 0.0
            if start_m_raw is not None and str(start_m_raw).strip() != "":
                try:
                    start_m = float(start_m_raw)
                    has_explicit_m = True
                except ValueError:
                    start_m = 0.0
            else:
                has_explicit_m = False
                start_m = 0.0
            sign = -1.0 if (start_km < 0 or str(start_km_raw).strip().startswith("-")) else 1.0
            start_ch_m = sign * (abs(start_km) * 1000.0 + abs(start_m))
        elif getattr(self.config, "start_chainage", None) is not None:
            s = str(self.config.start_chainage).strip()
            if "+" in s:
                parts = s.split("+")
                try:
                    sk = float(parts[0].strip() or 0)
                    sm = float(parts[1].strip() or 0)
                    has_explicit_m = True
                    sign = -1.0 if (sk < 0 or parts[0].strip().startswith("-")) else 1.0
                    start_ch_m = sign * (abs(sk) * 1000.0 + abs(sm))
                except ValueError:
                    start_ch_m = 0.0
            else:
                try:
                    num = float(s)
                    if abs(num) <= 50.0 and "." not in s:
                        start_ch_m = num * 1000.0
                        has_explicit_m = False
                    else:
                        start_ch_m = num
                        has_explicit_m = (abs(num) % 1000 > 0)
                except ValueError:
                    start_ch_m = 0.0

        # Parse station markers in advance to coordinate placement and avoid duplicate interval ticks
        parsed_stations = self._parse_alignment_station_markers(cleaned, start_ch_m, total_len)
        station_dists = [s["d"] for s in parsed_stations]

        step = 100.0
        distances_to_mark = []

        # Only add start chainage (0.0) if not directly on top of a station marker
        if not any(abs(0.0 - sd) < 25.0 for sd in station_dists):
            distances_to_mark.append(0.0)

        first_100 = math.ceil(start_ch_m / step) * step
        curr = first_100
        while (curr - start_ch_m) < total_len - 1e-4:
            d = curr - start_ch_m
            if d > 1.0:
                # Omit interval tick if it falls within 25m of any station marker to prevent collision
                if not any(abs(d - sd) < 25.0 for sd in station_dists):
                    distances_to_mark.append(d)
            curr += step

        # Append end chainage only if separated by at least 25m from previous tick and station markers
        last_d = distances_to_mark[-1] if distances_to_mark else -999.0
        if (total_len - last_d) >= 25.0:
            if not any(abs(total_len - sd) < 25.0 for sd in station_dists):
                distances_to_mark.append(total_len)

        text_h = 1.0
        tick_top_len = 6.0
        tick_bot_len = 14.0

        for d in distances_to_mark:
            ch_m = start_ch_m + d
            if ch_m < -0.005:
                abs_ch = abs(ch_m)
                km_mag = int(abs_ch // 1000)
                m_rem = abs_ch - (km_mag * 1000.0)
                if abs(m_rem) < 0.01:
                    if not has_explicit_m:
                        top_text = f"CH--{km_mag}"
                    else:
                        top_text = f"CH--{km_mag}+000"
                else:
                    top_text = f"CH--{km_mag}+{int(round(m_rem))}"
            else:
                km_val = int(ch_m // 1000)
                m_val = ch_m - (km_val * 1000.0)

                # Top label text:
                # If user filled 4 for KM, and nothing in M, use only 4 when m_val is 0
                if abs(m_val) < 0.01:
                    if not has_explicit_m:
                        top_text = f"CH-{km_val}"
                    else:
                        top_text = f"CH-{km_val}+000"
                else:
                    top_text = f"CH-{km_val}+{int(round(m_val))}"

            # Bottom label text:
            bot_text = f"Ch. {int(round(ch_m))} M"

            st = point_at_chainage(cleaned, d)
            px, py = st.point
            tx, ty = st.tangent
            t_len = math.hypot(tx, ty) or 1.0
            tx, ty = tx / t_len, ty / t_len

            # Normal vector (perpendicular to track)
            nx, ny = -ty, tx

            # Tick line
            p_top = (px + nx * tick_top_len, py + ny * tick_top_len)
            p_bot = (px - nx * tick_bot_len, py - ny * tick_bot_len)
            doc.modelspace().add_line(p_bot, p_top, dxfattribs={"layer": layer_name, "color": 1})

            # Normal angle in degrees: keep in [0, 180) so text always points upwards (along +n)
            norm_deg = math.degrees(math.atan2(ny, nx))
            rot_deg = norm_deg
            while rot_deg >= 180.0:
                rot_deg -= 180.0
            while rot_deg < 0.0:
                rot_deg += 180.0

            # Insert top text (CH-...) along normal at tick_top, offset to left of tick line
            top_len = len(top_text) * (text_h * 0.75)
            ins_top = _calc_text_insert(
                (px, py),
                (nx, ny),
                (tx, ty),
                tick_top_len + 1.5,
                top_len,
                rot_deg,
                side_offset=-0.8,
            )
            doc.modelspace().add_text(
                top_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_h,
                    "rotation": rot_deg,
                    "insert": ins_top,
                },
            )

            # Insert bottom text (Ch. 1900 M) along normal below track, offset to left of tick line
            bot_text_len = len(bot_text) * (text_h * 0.75)
            ins_bot = _calc_text_insert(
                (px, py),
                (-nx, -ny),
                (tx, ty),
                tick_bot_len + 1.5,
                bot_text_len,
                rot_deg,
                side_offset=-0.8,
            )
            doc.modelspace().add_text(
                bot_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_h,
                    "rotation": rot_deg,
                    "insert": ins_bot,
                },
            )

        # Draw station marker lines at specified station chainages
        try:
            self._generate_alignment_station_markers(tracks, doc, cleaned, start_ch_m, total_len, parsed_stations)
        except Exception as exc:
            print(f"   ! Station marker lines skipped ({exc})")

        doc.saveas(self.config.output_dxf)
        print(f"   ✓ Alignment interval chainages: {len(distances_to_mark)} markers (start {start_ch_m:.1f} m to {start_ch_m + total_len:.1f} m)")

    def _parse_alignment_station_markers(
        self,
        cleaned_main_pts: list,
        start_ch_m: float,
        total_len: float,
    ) -> list[dict]:
        """Parse station marker configurations into normalized distance and display structures."""
        station_markers = getattr(self.config, "station_markers", None) or []
        if not station_markers:
            return []

        parsed = []
        for idx, stn in enumerate(station_markers, 1):
            if isinstance(stn, dict):
                stn_name = str(stn.get("name") or f"STATION {idx}").strip()
                km_val = stn.get("km")
                m_val = stn.get("m")
                raw_ch = stn.get("chainage")
                show_flag = stn.get("show_flag", True)
            else:
                stn_name = str(getattr(stn, "name", f"STATION {idx}")).strip()
                km_val = getattr(stn, "km", None)
                m_val = getattr(stn, "m", None)
                raw_ch = getattr(stn, "chainage", None)
                show_flag = getattr(stn, "show_flag", True)

            # Determine absolute chainage in meters
            stn_ch_m = None
            km_has = km_val is not None and str(km_val).strip() != ""
            m_has = m_val is not None and str(m_val).strip() != ""
            if km_has or m_has:
                try:
                    km_f = float(km_val) if km_has else 0.0
                    m_f = float(m_val) if m_has else 0.0
                    sign = -1.0 if (km_f < 0 or (km_has and str(km_val).strip().startswith("-"))) else 1.0
                    stn_ch_m = sign * (abs(km_f) * 1000.0 + abs(m_f))
                except ValueError:
                    stn_ch_m = None

            if stn_ch_m is None and raw_ch is not None and str(raw_ch).strip() != "":
                s_ch = str(raw_ch).strip()
                if "+" in s_ch:
                    parts = s_ch.split("+")
                    try:
                        sk = float(parts[0].strip() or 0)
                        sm = float(parts[1].strip() or 0)
                        sign = -1.0 if (sk < 0 or parts[0].strip().startswith("-")) else 1.0
                        stn_ch_m = sign * (abs(sk) * 1000.0 + abs(sm))
                    except ValueError:
                        stn_ch_m = None
                else:
                    try:
                        num = float(s_ch)
                        stn_ch_m = num * 1000.0 if abs(num) <= 50.0 and "." not in s_ch else num
                    except ValueError:
                        stn_ch_m = None

            if stn_ch_m is None:
                continue

            # Calculate distance d along track alignment and display chainage
            if stn_ch_m >= start_ch_m:
                d = stn_ch_m - start_ch_m
                display_ch_m = stn_ch_m
            elif 0.0 <= stn_ch_m <= total_len:
                d = stn_ch_m
                display_ch_m = start_ch_m + d
            else:
                d = stn_ch_m
                display_ch_m = stn_ch_m

            d = max(0.0, min(d, total_len))

            if display_ch_m < -0.005:
                abs_ch = abs(display_ch_m)
                ch_km_mag = int(abs_ch // 1000)
                ch_rem_m = abs_ch - (ch_km_mag * 1000.0)
                if abs(ch_rem_m) < 0.01:
                    ch_disp = f"-{ch_km_mag}+000" if (m_val is not None and str(m_val).strip() != "") else f"-{ch_km_mag}"
                else:
                    ch_disp = f"-{ch_km_mag}+{int(round(ch_rem_m))}"
            else:
                ch_km = int(display_ch_m // 1000)
                ch_rem_m = display_ch_m - (ch_km * 1000.0)
                if abs(ch_rem_m) < 0.01:
                    ch_disp = f"{ch_km}+000" if (m_val is not None and str(m_val).strip() != "") else f"{ch_km}"
                else:
                    ch_disp = f"{ch_km}+{int(round(ch_rem_m))}"

            parsed.append({
                "idx": idx,
                "name": stn_name,
                "d": d,
                "ch_m": display_ch_m,
                "ch_disp": ch_disp,
                "show_flag": show_flag,
            })

        return parsed

    def _generate_alignment_station_markers(
        self,
        tracks: dict,
        doc,
        cleaned_main_pts: list,
        start_ch_m: float,
        total_len: float,
        parsed_stations: list[dict] | None = None,
    ) -> None:
        """Draw station marker lines and labels at specified chainages along MAIN track."""
        if parsed_stations is None:
            parsed_stations = self._parse_alignment_station_markers(cleaned_main_pts, start_ch_m, total_len)

        if not parsed_stations:
            return

        from common.dxf import ensure_layer, ensure_text_style
        layer_name = "STATION"
        ensure_layer(doc, layer_name, color=1)
        style_name = ensure_text_style(doc)

        drawn_count = 0
        for stn in parsed_stations:
            d = stn["d"]
            stn_name = stn["name"]
            ch_disp = stn["ch_disp"]
            ch_m = stn["ch_m"]
            show_flag = stn["show_flag"]

            st = point_at_chainage(cleaned_main_pts, d)
            px, py = st.point
            tx, ty = st.tangent
            t_len = math.hypot(tx, ty) or 1.0
            tx, ty = tx / t_len, ty / t_len

            # Normal vector
            nx, ny = -ty, tx

            # Stagger height if neighbor station is close (< 35m) to avoid any collision
            is_close_neighbor = any(
                other != stn and abs(other["d"] - d) < 35.0
                for other in parsed_stations
            )
            line_top_len = 28.0 if (is_close_neighbor and (stn["idx"] % 2 == 0)) else 22.0
            line_bot_len = 16.0
            p_top = (px + nx * line_top_len, py + ny * line_top_len)
            p_bot = (px - nx * line_bot_len, py - ny * line_bot_len)

            doc.modelspace().add_line(p_bot, p_top, dxfattribs={"layer": layer_name, "color": 1})

            # Check if station flag is requested (defaults to True)
            if show_flag:
                flag_up = (nx, ny)
                flag_right = (tx, ty)
                pole_base = (p_top[0], p_top[1])
                try:
                    draw_station_flag(doc, pole_base, flag_up, flag_right, color=1)
                except Exception as exc:
                    print(f"   ! Station flag skipped for {stn_name} ({exc})")
            else:
                # Terminal crossbar at top of station line when flag is disabled
                bar_w = 3.5
                doc.modelspace().add_line(
                    (p_top[0] - tx * bar_w, p_top[1] - ty * bar_w),
                    (p_top[0] + tx * bar_w, p_top[1] + ty * bar_w),
                    dxfattribs={"layer": layer_name, "color": 1},
                )

            # Normal angle in degrees for readable text rotation: keep in [0, 180) so text always points upwards (along +n)
            norm_deg = math.degrees(math.atan2(ny, nx))
            rot_deg = norm_deg
            while rot_deg >= 180.0:
                rot_deg -= 180.0
            while rot_deg < 0.0:
                rot_deg += 180.0

            # Separation of text: LEFT and RIGHT of the station line to guarantee zero overlap.
            # - Left of line: STATION: <NAME> sits at side_offset -2.5
            # - Right of line: CH: <KM+M> sits at side_offset +2.5
            # - Bottom of line (below track): Ch. <ch_m> M sits below p_bot
            y_start = line_top_len + 3.5 if show_flag else line_top_len + 1.5
            stn_text = f"STATION: {stn_name.upper()}"
            stn_len = len(stn_text) * (1.4 * 0.75)
            ins_left = _calc_text_insert(
                (px, py),
                (nx, ny),
                (tx, ty),
                y_start,
                stn_len,
                rot_deg,
                side_offset=-2.5,
            )
            doc.modelspace().add_text(
                stn_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": 1.4,
                    "rotation": rot_deg,
                    "insert": ins_left,
                },
            )

            # CH: <KM+M>
            ch_text = f"CH: {ch_disp}"
            ch_len = len(ch_text) * (1.2 * 0.75)
            ins_right = _calc_text_insert(
                (px, py),
                (nx, ny),
                (tx, ty),
                y_start,
                ch_len,
                rot_deg,
                side_offset=+2.5,
            )
            doc.modelspace().add_text(
                ch_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": 1.2,
                    "rotation": rot_deg,
                    "insert": ins_right,
                },
            )

            # Bottom of line (below track): Ch. <ch_m> M on the left of the line
            stn_bot_text = f"Ch. {int(round(ch_m))} M"
            stn_bot_len = len(stn_bot_text) * (1.0 * 0.75)
            ins_bot = _calc_text_insert(
                (px, py),
                (-nx, -ny),
                (tx, ty),
                line_bot_len + 1.5,
                stn_bot_len,
                rot_deg,
                side_offset=-0.8,
            )
            doc.modelspace().add_text(
                stn_bot_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": 1.0,
                    "rotation": rot_deg,
                    "insert": ins_bot,
                },
            )
            drawn_count += 1

        if drawn_count > 0:
            print(f"   ✓ Alignment station markers: {drawn_count} station(s) drawn")



class ChainageMixin(ChainageStep):
    """Mixin for backward compatibility."""
    pass
