"""Crossover preset expansion + generation via the N-engine."""

from __future__ import annotations

import math
from typing import Dict, Tuple

import ezdxf

from common.constants import DEFAULT_OVERRUN_M

from common.dxf import ensure_bold_text_style as _ensure_bold_text_style
from common.dxf import resolve_text_insert as _resolve_text_insert
from common.geometry import polyline_length, readable_angle_deg
from platform_gen.geometry import point_at_chainage as _pac
from track.crossover import (
    CrossoverPlanner,
    compute_default_chainages,
    crossover_track_intervals,
    find_restriction_conflicts,
    format_debug_block,
    normalize_direction as _nd,
    platforms_to_restricted_regions,
    requests_from_specs,
    stations_to_restricted_regions,
)
from track.drawing import _add_spline as _add_crossover_spline
from track.drawing import _draw_srj_post
from track.specs import CrossoverSpec as _CrossoverSpec
from track.turnouts import select_turnout as _select_turnout

from .base import PipelineStep
from .crossover_cuts import apply_loop_overrun_cuts, count_outer_loops

__all__ = ["CrossoverStep", "CrossoverMixin"]


class CrossoverStep(PipelineStep):
    """Pipeline step: Crossover preset expansion and generation."""

    def _loop_main_extents(self) -> Dict[str, Tuple[float, float]]:
        """Map bounded-loop track name -> effective (C1, C2) MAIN chainages."""
        trim = getattr(self, "_loop_trim_extents", None) or {}
        extents: Dict[str, Tuple[float, float]] = {}
        specs_by_name = {
            getattr(loop, "name", None): loop
            for loop in list(self.config.loops) + list(self.config.additional_lines)
            if getattr(loop, "name", None)
        }
        for loop in list(self.config.loops) + list(self.config.additional_lines):
            c1 = getattr(loop, "first_crossover_chainage", None)
            if c1 is None:
                continue
            c2 = getattr(loop, "second_crossover_chainage", None)
            if c2 is None:
                c2 = c1 + getattr(loop, "crossover_distance_m", 750.0)
            if trim:
                ext_s = getattr(loop, "extend_start_m", 0.0) or 0.0
                ext_e = getattr(loop, "extend_end_m", 0.0) or 0.0
            else:
                num_outer = count_outer_loops(loop.name, specs_by_name)
                ext_s = max(float(getattr(loop, "extend_start_m", 0.0) or 0.0), DEFAULT_OVERRUN_M) + num_outer * 150.0
                ext_e = max(float(getattr(loop, "extend_end_m", 0.0) or 0.0), DEFAULT_OVERRUN_M) + num_outer * 150.0
                for xo in getattr(self.config, "crossovers", None) or []:
                    if getattr(xo, "from_track", None) == loop.name or getattr(xo, "to_track", None) == loop.name:
                        ch_val = getattr(xo, "from_chainage_m", None)
                        try:
                            ch_f = float(ch_val)
                            if ch_f < c1:
                                ext_s = max(ext_s, float(c1) - ch_f + float(DEFAULT_OVERRUN_M))
                            if ch_f > c2:
                                ext_e = max(ext_e, ch_f - float(c2) + float(DEFAULT_OVERRUN_M))
                        except (TypeError, ValueError):
                            pass
            eff = (max(0.0, float(c1) - ext_s), float(c2) + ext_e)
            extents[loop.name] = tuple(trim.get(loop.name, eff))  # type: ignore[assignment]
        return extents

    def _bounded_loop_defined_ranges(self) -> Dict[str, Tuple[float, float, float, float]]:
        """Bounded-loop name -> (C1, C2, eff_start, eff_end) MAIN chainages."""
        ranges: Dict[str, Tuple[float, float, float, float]] = {}
        specs_by_name = {
            getattr(loop, "name", None): loop
            for loop in list(self.config.loops) + list(self.config.additional_lines)
            if getattr(loop, "name", None)
        }
        for loop in list(self.config.loops) + list(self.config.additional_lines):
            c1 = getattr(loop, "first_crossover_chainage", None)
            if c1 is None or not hasattr(loop, "spacing"):
                continue
            c2 = getattr(loop, "second_crossover_chainage", None)
            if c2 is None:
                c2 = c1 + getattr(loop, "crossover_distance_m", 750.0)
            num_outer = count_outer_loops(loop.name, specs_by_name)
            ext_s = max(float(getattr(loop, "extend_start_m", 0.0) or 0.0), DEFAULT_OVERRUN_M) + num_outer * 150.0
            ext_e = max(float(getattr(loop, "extend_end_m", 0.0) or 0.0), DEFAULT_OVERRUN_M) + num_outer * 150.0
            for xo in getattr(self.config, "crossovers", None) or []:
                if getattr(xo, "from_track", None) == loop.name or getattr(xo, "to_track", None) == loop.name:
                    ch_val = getattr(xo, "from_chainage_m", None)
                    try:
                        ch_f = float(ch_val)
                        if ch_f < c1:
                            ext_s = max(ext_s, float(c1) - ch_f + float(DEFAULT_OVERRUN_M))
                        if ch_f > c2:
                            ext_e = max(ext_e, ch_f - float(c2) + float(DEFAULT_OVERRUN_M))
                    except (TypeError, ValueError):
                        pass
            ranges[loop.name] = (
                float(c1),
                float(c2),
                max(0.0, float(c1) - float(ext_s)),
                float(c2) + float(ext_e),
            )
        return ranges

    def _expand_default_preset(self, tracks: dict, extents: dict) -> None:
        """Expand crossover_preset DEFAULT into 4 FIXED CrossoverSpecs."""
        preset = (getattr(self.config, "crossover_preset", None) or "").upper()
        if preset != "DEFAULT":
            return
        if getattr(self.config, "crossovers", None):
            return
        if "LOOP_1" not in tracks or "LOOP_2" not in tracks or "MAIN_LINE" not in tracks:
            raise ValueError("crossover_preset DEFAULT needs LOOP_1, LOOP_2 and MAIN_LINE tracks.")

        defined_c1 = defined_c2 = None
        for loop in list(getattr(self.config, "loops", []) or []) + list(
            getattr(self.config, "additional_lines", []) or []
        ):
            if getattr(loop, "name", None) == "LOOP_1" and getattr(loop, "first_crossover_chainage", None) is not None:
                defined_c1 = float(loop.first_crossover_chainage)
                c2 = getattr(loop, "second_crossover_chainage", None)
                defined_c2 = (
                    float(c2)
                    if c2 is not None
                    else defined_c1 + float(getattr(loop, "crossover_distance_m", 750.0))
                )
                break
        if defined_c1 is None or defined_c2 is None:
            raise ValueError("crossover_preset DEFAULT needs LOOP_1 defined [C1, C2] (overrun ignored).")

        turnout = _select_turnout(getattr(self.config, "crossover_preset_turnout", None) or "1:12")
        try:
            dd = compute_default_chainages(
                defined_c1,
                defined_c2,
                turnout,
                tracks,
                loop1="LOOP_1",
                loop2="LOOP_2",
                main="MAIN_LINE",
                extents=extents,
            )
        except ValueError as exc:
            raise ValueError(f"crossover_preset DEFAULT does not fit: {exc}") from exc

        plan = [
            ("C1", "LOOP_1", "MAIN_LINE", dd["c1"], "REVERSE", "BEHIND"),
            ("C2", "LOOP_1", "MAIN_LINE", dd["c2"], "FORWARD", "AHEAD"),
            ("C3", "MAIN_LINE", "LOOP_2", dd["c3"], "FORWARD", "AHEAD"),
            ("C4", "MAIN_LINE", "LOOP_2", dd["c4"], "REVERSE", "BEHIND"),
        ]
        specs = [
            _CrossoverSpec(
                from_track=fr,
                to_track=to,
                from_chainage_m=float(ch),
                to_chainage_m=None,
                turnout=turnout,
                placement=pl,
                id=cid,
                direction=dr,
                position_mode="FIXED",
            )
            for cid, fr, to, ch, dr, pl in plan
        ]

        try:
            restrictions = platforms_to_restricted_regions(
                getattr(self.config, "platforms", []) or [], tracks, extents
            )
            restrictions += stations_to_restricted_regions(
                getattr(self.config, "stations", []) or [],
                getattr(self.config, "platforms", []) or [],
                tracks,
                extents,
            )
        except Exception:
            restrictions = []

        try:
            a_m = float(getattr(turnout, "a_mm", 0.0) or 0.0) / 1000.0
        except (TypeError, ValueError):
            a_m = 0.0

        for spec in specs:
            second = (
                float(spec.from_chainage_m) + dd[f"ol{spec.id[1:]}_m"]
                if spec.placement == "AHEAD"
                else float(spec.from_chainage_m) - dd[f"ol{spec.id[1:]}_m"]
            )
            intervals = crossover_track_intervals(
                spec.from_track,
                spec.to_track,
                float(spec.from_chainage_m),
                float(second),
                spec.placement,
                spec.direction,
                a_m,
            )
            conflicts = find_restriction_conflicts(intervals, restrictions)
            if conflicts:
                cf = conflicts[0]
                raise ValueError(
                    f"crossover_preset DEFAULT {spec.id} crosses "
                    f"{cf.region.reason} on {cf.track} "
                    f"([{min(cf.region.start_chainage, cf.region.end_chainage):.1f}, "
                    f"{max(cf.region.start_chainage, cf.region.end_chainage):.1f}] MAIN m). "
                    f"Move the platform/station or use explicit crossovers."
                )
        self.config.crossovers = specs
        print(
            f"   DEFAULT preset ({turnout.designation}): LOOP_1 "
            f"[{defined_c1:.2f}, {defined_c2:.2f}] (defined, overrun ignored); "
            f"C1 {dd['c1']:.2f}->E1 {dd['e1']:.2f}, "
            f"C2 {dd['c2']:.2f}->E2 {dd['e2']:.2f}, "
            f"C3 MAIN {dd['c3']:.2f} (E1+54) FORWARD, "
            f"C4 MAIN {dd['c4']:.2f} (E2-54) REVERSE."
        )

    def _generate_crossovers(self, tracks: dict) -> None:
        """Generate an arbitrary number of crossovers via the generic engine."""
        extents = self._loop_main_extents()
        if getattr(self.config, "crossover_preset", None) and not getattr(self.config, "crossovers", None):
            self._expand_default_preset(tracks, extents)
        if not self.config.crossovers:
            return

        for number, spec in enumerate(self.config.crossovers, 1):
            if not getattr(spec, "id", None):
                spec.id = f"C{number}"
            if getattr(spec, "direction", None) is None:
                spec.direction = "FORWARD"
            if getattr(spec, "placement", None) is None:
                try:
                    _d = _nd(getattr(spec, "direction", "FORWARD"))
                except ValueError:
                    _d = "FORWARD"
                spec.placement = "BEHIND" if _d == "REVERSE" else "AHEAD"
            if getattr(spec, "position_mode", None) is None:
                ch = getattr(spec, "from_chainage_m", None)
                auto = ch is None or (isinstance(ch, str) and ch.strip().upper() == "AUTO")
                spec.position_mode = "AUTO" if auto else "FIXED"

        requests = requests_from_specs(self.config.crossovers)
        for req in requests:
            if req.turnout is None:
                raise ValueError(
                    f"Crossover {req.id}: no turnout selected - select "
                    f"1:8.5 or 1:12 from the verified turnout library. "
                    f"Marker-only (Bezier/spline) crossovers are not permitted."
                )

        extents = self._loop_main_extents()
        main_pts = tracks.get("MAIN_LINE")
        main_length = polyline_length(main_pts) if main_pts else None

        planner = CrossoverPlanner(tracks, extents, main_length)
        try:
            results, report = planner.plan(requests)
            self._crossover_results = list(results)
        except ValueError as exc:
            raise ValueError(
                f"CROSSOVER LAYOUT INVALID\n{exc}\n"
                f"Note: {self.config.output_dxf} currently holds "
                f"tracks/platforms only - no crossover geometry or SRJ "
                f"markers were drawn."
            ) from exc

        print("")
        print(report.format())
        print("")
        for note in report.warnings:
            print(f"     Note: {note}")
        if report.warnings:
            print("")
        for res in results:
            print(f"   {format_debug_block(res)}")
            print(f"     From Track: {res.from_track}  To Track: {res.to_track}")
            tc_txt = f"{res.track_centre_m:.3f} m" if res.track_centre_m is not None else "unknown"
            print(f"     Track Centre: {tc_txt}")
            for warning in res.warnings:
                print(f"     ! {warning}")

        if not report.overall_valid:
            raise ValueError(
                "CROSSOVER LAYOUT INVALID\n"
                + report.format()
                + f"\nNo crossover geometry was generated until the conflict is resolved ({self.config.output_dxf} holds tracks/platforms only)."
            )

        doc = ezdxf.readfile(self.config.output_dxf)

        for entity in list(doc.modelspace()):
            if entity.dxf.layer in ("CROSSOVERS", "CROSSOVER_FROM_MARKER", "CROSSOVER_TO_MARKER", "SRJ"):
                doc.modelspace().delete_entity(entity)

        if "CROSSOVERS" not in doc.layers:
            doc.layers.add("CROSSOVERS", color=1)
        if "SRJ" not in doc.layers:
            doc.layers.add("SRJ", color=1)

        spec_by_id = {
            getattr(s, "id", f"C{i+1}"): s for i, s in enumerate(self.config.crossovers)
        }

        for res in results:
            spec = spec_by_id.get(res.id)
            if spec is not None and getattr(spec, "to_chainage_m", None) is not None:
                computed = res.end_chainage if res.placement == "AHEAD" else res.start_chainage
                if abs(float(spec.to_chainage_m) - computed) > 0.05:
                    print(
                        f"   ! Crossover {res.id}: configured to_chainage "
                        f"{float(spec.to_chainage_m):.3f}m ignored - standard "
                        f"position is {computed:.3f}m (START +/- OL)."
                    )
            _add_crossover_spline(doc, res.geometry, "CROSSOVERS", 1)

            def _local(name: str, main_ch: float) -> float:
                ext = extents.get(name)
                return main_ch if ext is None else main_ch - ext[0]

            sp_from = _pac(tracks[res.from_track], _local(res.from_track, res.chainage))
            second_main = res.end_chainage if res.placement == "AHEAD" else res.start_chainage
            sp_to = _pac(tracks[res.to_track], _local(res.to_track, second_main))
            _draw_srj_post(doc, sp_from.point, sp_from.tangent, False)
            _draw_srj_post(doc, sp_to.point, sp_to.tangent, False)

            tlabel = (res.turnout_type or "").replace(":", " in ")
            if tlabel:
                try:
                    mpts = tracks.get("MAIN_LINE")
                    mt = _pac(mpts, res.chainage).tangent if mpts else None
                except Exception:
                    mt = None
                tan = mt if mt is not None else sp_from.tangent
                tn = math.hypot(tan[0], tan[1]) or 1.0
                tx, ty = tan[0] / tn, tan[1] / tn
                tang = readable_angle_deg(math.degrees(math.atan2(ty, tx)))
                ft = sp_from.tangent
                fn = math.hypot(ft[0], ft[1]) or 1.0
                ox, oy = ft[1] / fn, -ft[0] / fn
                dcx = sp_from.point[0] + ox * 3.0
                dcy = sp_from.point[1] + oy * 3.0
                tdx = math.cos(math.radians(tang))
                tdy = math.sin(math.radians(tang))
                tag_insert = _resolve_text_insert(
                    doc,
                    tlabel,
                    0.8,
                    tang,
                    (
                        dcx + ox * 2.0 + tdx * 0.5,
                        dcy + oy * 2.0 + tdy * 0.5,
                        0,
                    ),
                )
                doc.modelspace().add_text(
                    tlabel,
                    dxfattribs={
                        "layer": "CROSSOVERS",
                        "color": 1,
                        "style": _ensure_bold_text_style(doc),
                        "height": 0.8,
                        "rotation": tang,
                        "insert": (tag_insert[0], tag_insert[1], 0),
                    },
                )
            print(
                f"   OK Crossover {res.id} ({res.from_track}->{res.to_track}) "
                f"SRJ1@{res.chainage:.3f}m -> SRJ2@{second_main:.3f}m "
                f"[{res.turnout_type}] OL={res.ol_mm:.0f}mm"
            )

        doc.saveas(self.config.output_dxf)
        self._apply_loop_overrun_cuts(tracks)

    def _apply_loop_overrun_cuts(self, tracks: dict) -> dict[str, tuple]:
        """Trim bounded loops at crossover SRJs into running + overrun."""
        ranges = self._bounded_loop_defined_ranges()
        results = list(getattr(self, "_crossover_results", None) or [])
        cuts, trim_extents, full_lines, splits = apply_loop_overrun_cuts(
            doc_path=self.config.output_dxf,
            tracks=tracks,
            crossover_results=results,
            loops_spec=self.config.loops,
            additional_lines_spec=self.config.additional_lines,
            ranges=ranges,
        )
        self._loop_cuts = cuts
        self._loop_trim_extents = trim_extents
        self._loop_full_lines = full_lines
        return cuts


class CrossoverMixin(CrossoverStep):
    """Mixin for backward compatibility."""
    pass
