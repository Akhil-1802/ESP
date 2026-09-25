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

from .base import PipelineStep
from .chainage_collect import (
    collect_dead_ends,
    collect_fm,
    collect_fob,
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
    "GRADIENT": 0.0,
}

_STUB_GAP_M = 2.0
_DEDUPE_M = 2.0


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

    def _collect_optional_layers(self, doc, tracks_for_datum, datum) -> list:
        return collect_optional_layers(
            doc, tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None)
        )

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

        def _dedupe_side_group(items):
            kept_group: list = []
            for base, tan, rel, tag, side in items:
                dup = False
                for kb, _kt, kr, ktag, _kside in kept_group:
                    if ktag != tag:
                        continue
                    if math.hypot(base[0] - kb[0], base[1] - kb[1]) < _DEDUPE_M:
                        dup = True
                        break
                    try:
                        if abs(float(rel) - float(kr)) < parallel_tol:
                            dup = True
                            break
                    except (TypeError, ValueError):
                        pass
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

        try:
            projs: list = []
            for (a, b) in edges:
                projs.append(a[0] * ref_n[0] + a[1] * ref_n[1])
                projs.append(b[0] * ref_n[0] + b[1] * ref_n[1])
            for (cx, cy, r) in circles:
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
                    drawn += draw_chainage_annotation(
                        doc,
                        start,
                        pseudo_tan,
                        float(rel),
                        str(tag),
                        leader_len=float(leader_len),
                        lift=float(_TEXT_LIFT.get(str(tag), 0.0)),
                        side="LEFT",
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
                    drawn += draw_chainage_annotation(
                        doc,
                        start,
                        pseudo_tan,
                        float(rel),
                        str(tag),
                        leader_len=float(leader_len),
                        lift=float(_TEXT_LIFT.get(str(tag), 0.0)),
                        side="RIGHT",
                    )
                except Exception:
                    continue

        try:
            doc.saveas(self.config.output_dxf)
        except Exception as exc:
            print(f"   ! Station chainage labels save skipped ({exc})")
            return
        print(f"   ✓ Station chainage labels: {drawn} (datum C/L {center[0]:.2f},{center[1]:.2f} = 0.000)")


class ChainageMixin(ChainageStep):
    """Mixin for backward compatibility."""
    pass
