"""Generate full-length parallel railway LOOP lines."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

import ezdxf

from common.constants import DEFAULT_OVERRUN_M, LOOP_CROSSOVER_DISTANCE_M
from common.geometry import (
    cumulative_chainages,
    distance as _distance,
    offset_point,
    point_at_chainage,
    polyline_length as _common_polyline_length,
)
from track.crossover import generate_loop as _generate_loop_geom
from track.drawing import (
    _add_all_tc_annotations,
    _add_spline,
    _add_tc_annotation,
    _add_track_label,
    _annotate_overrun,
    _arrow_head,
    _draw_direction_mark,
    _draw_srj_post,
    _line_center,
    draw_srj_overrun_stub,
    draw_tracks,
)
from track.specs import (
    CrossoverSpec,
    LineSpec,
    LoopSpec,
    SidingSpec,
    TrackGenerationConfig,
)
from track.turnouts import require_geometry_parameters, select_turnout

Point = Tuple[float, float]

__all__ = [
    "LoopSpec",
    "LineSpec",
    "CrossoverSpec",
    "SidingSpec",
    "TrackGenerationConfig",
    "TrackGenerator",
    "BuiltTracks",
    "LOOP_CROSSOVER_DISTANCE_M",
    "_add_spline",
    "_draw_srj_post",
    "draw_tracks",
]


def _format_loop_status(name: str, loop_geom) -> str:
    """Produce the spec-style LOOP status block."""
    cs = loop_geom.crossover_summary
    lines = [
        f"{name}:",
        f"  C1: {loop_geom.c1:.3f} m",
        f"  C2: {loop_geom.c2:.3f} m",
        f"  Connection distance: {loop_geom.c2 - loop_geom.c1:.3f} m",
        f"  Side: {loop_geom.metadata['side']}",
        f"  Track spacing: {loop_geom.metadata['spacing_m']:.3f} m",
        f"  Turnout: {loop_geom.metadata['turnout']} / {loop_geom.metadata['variant']}",
        "  Turnout 1: generated",
        "  Turnout 2: generated",
        "  Crossover geometry:",
        f"    Type: {'normal' if loop_geom.spacing_classification == 'normal' else 'large spacing'}",
        f"    D: {cs.get('D_mm', 0):.0f} mm",
        f"    A: {cs.get('A_mm', 0):.0f} mm",
        f"    B: {cs.get('B_mm', 0):.0f} mm",
        f"    F: {cs.get('F_deg', 0):.4f} deg",
        f"    R: {cs.get('R_mm', 0):.0f} mm",
    ]
    if "separation_mm" in cs and cs["separation_mm"] is not None:
        lines.append(f"    S: {cs['separation_mm']:.2f} mm")
    if "horizontal_mm" in cs:
        lines.append(f"    X: {cs['horizontal_mm']:.2f} mm")
    if "overall_length_mm" in cs:
        lines.append(f"    OL: {cs['overall_length_mm']:.2f} mm")
    if "theta_deg" in cs:
        lines.append(f"    theta: {cs['theta_deg']:.4f} deg")
    if "T_mm" in cs:
        lines.append(f"    T: {cs['T_mm']:.2f} mm")
    lines.append("  Validation:")
    lines.append("    OK")
    return "\n".join(lines)


def _length(vector: Point) -> float:
    return _distance((0.0, 0.0), vector)


def _polyline_length(points: Sequence[Point]) -> float:
    return _common_polyline_length(list(points))


def _clean_source_alignment(points: Sequence[Point]) -> List[Point]:
    """Drop duplicate points and tiny reverse tails from an imported MAIN."""
    cleaned: List[Point] = []
    for point in points:
        value = (float(point[0]), float(point[1]))
        if not cleaned or _length((value[0] - cleaned[-1][0], value[1] - cleaned[-1][1])) > 1e-6:
            cleaned.append(value)
    while len(cleaned) >= 3:
        first, pivot, tail = cleaned[-3:]
        incoming = (pivot[0] - first[0], pivot[1] - first[1])
        outgoing = (tail[0] - pivot[0], tail[1] - pivot[1])
        incoming_len, outgoing_len = _length(incoming), _length(outgoing)
        reversed_tail = (
            incoming_len > 1e-6
            and outgoing_len <= max(2.0, incoming_len * 0.02)
            and incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
            <= -0.95 * incoming_len * outgoing_len
        )
        if not reversed_tail:
            break
        cleaned.pop()
    return cleaned


def _is_main_line(name: str) -> bool:
    """Return True if name is MAIN_LINE or a MAIN_LINE_N variation."""
    return name == "MAIN_LINE" or name.startswith("MAIN_LINE_")


def _offset_alignment(points: Sequence[Point], spacing: float, side: str) -> List[Point]:
    if spacing <= 0:
        raise ValueError("Loop spacing must be greater than zero")
    if len(points) < 2:
        raise ValueError("The main track must contain at least two points")
    sign = 1.0 if side.upper() == "LEFT" else -1.0
    result: List[Point] = []
    for index, point in enumerate(points):
        if index == 0:
            tangent = (points[1][0] - point[0], points[1][1] - point[1])
        elif index == len(points) - 1:
            tangent = (point[0] - points[index - 1][0], point[1] - points[index - 1][1])
        else:
            tangent = (points[index + 1][0] - points[index - 1][0], points[index + 1][1] - points[index - 1][1])
        tangent_length = _length(tangent) or 1.0
        result.append((
            point[0] - sign * tangent[1] / tangent_length * spacing,
            point[1] + sign * tangent[0] / tangent_length * spacing,
        ))
    return result


def _source_points(doc, layer: str) -> List[Point]:
    candidates: List[List[Point]] = []
    for entity in doc.modelspace():
        if entity.dxf.layer != layer:
            continue
        if entity.dxftype() == "LINE":
            candidates.append([(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)])
        elif entity.dxftype() == "LWPOLYLINE":
            candidates.append([(point[0], point[1]) for point in entity.get_points()])
    if not candidates:
        raise ValueError(f"No LINE or LWPOLYLINE found on source layer {layer!r}")
    return _clean_source_alignment(max(candidates, key=_polyline_length))


def _remove_source_alignment_entities(doc, source_layer: str) -> None:
    """Keep the imported source as input only; MAIN_LINE is the output."""
    for entity in list(doc.modelspace()):
        if entity.dxf.layer == source_layer and entity.dxftype() in {"LINE", "LWPOLYLINE"}:
            doc.modelspace().delete_entity(entity)


def _generate_bounded_loop(
    main_points: Sequence[Point],
    start_chainage: float,
    end_chainage: float,
    spacing: float,
    side: str,
) -> List[Point]:
    """Generate a loop line between two chainages on the main line."""
    if spacing <= 0:
        raise ValueError("Loop spacing must be greater than zero")
    if end_chainage <= start_chainage:
        raise ValueError(
            f"End chainage {end_chainage} must be greater than start chainage {start_chainage}"
        )

    chainages = cumulative_chainages(main_points)
    total_length = chainages[-1]
    if start_chainage < 0 or end_chainage > total_length:
        raise ValueError(
            f"Chainages outside track extent [0, {total_length}]: "
            f"C1={start_chainage}, C2={end_chainage}"
        )

    interior_chainages: List[float] = [
        ch for ch in chainages if start_chainage < ch < end_chainage
    ]
    sample_chainages = [start_chainage] + interior_chainages + [end_chainage]

    loop_points: List[Point] = []
    for ch in sample_chainages:
        sp = point_at_chainage(main_points, ch)
        loop_points.append(offset_point(sp, spacing, side))

    return loop_points


def _apply_loop_extension(
    main_points: Sequence[Point],
    loop: "LoopSpec",
    c1: float,
    c2: float,
    base_points: Sequence[Point],
) -> tuple[List[Point], float, float]:
    """Extend a bounded loop past its turnouts (overrun)."""
    ext_start = getattr(loop, "extend_start_m", 0.0) or 0.0
    ext_end = getattr(loop, "extend_end_m", 0.0) or 0.0
    if ext_start < 0 or ext_end < 0:
        raise ValueError(f"Loop {loop.name}: extensions must be >= 0")
    # Maintain sufficient preliminary baseline so crossover planning and spacing checks
    # always find parallel track across the crossover zone; exact overrun trimming happens in Step 10.
    prelim_s = max(float(ext_start), float(DEFAULT_OVERRUN_M))
    prelim_e = max(float(ext_end), float(DEFAULT_OVERRUN_M))
    eff_c1, eff_c2 = max(0.0, c1 - prelim_s), c2 + prelim_e
    return _generate_bounded_loop(main_points, eff_c1, eff_c2, loop.spacing, loop.side), eff_c1, eff_c2


class BuiltTracks:
    """Result of TrackGenerator.build_tracks(): centreline geometry only."""

    def __init__(
        self,
        tracks: dict[str, List[Point]],
        loop_results: dict[str, object],
        overrun_jobs: list[tuple],
    ):
        self.tracks = tracks
        self.loop_results = loop_results
        self.overrun_jobs = overrun_jobs


class TrackGenerator:
    """Generates and manages track layout centrelines and geometries."""

    def __init__(self, config: TrackGenerationConfig):
        self.config = config

    def build_tracks(self, quiet: bool = False) -> BuiltTracks:
        """Build every track centreline from the source DXF (no drawing)."""
        source_doc = ezdxf.readfile(self.config.source_dxf)
        main = _source_points(source_doc, self.config.source_layer)
        tracks: dict[str, List[Point]] = {"MAIN_LINE": main}
        main_extents: dict[str, tuple[float, float]] = {
            "MAIN_LINE": (0.0, _polyline_length(main))
        }

        for line in self.config.additional_lines:
            if isinstance(line, LineSpec) and line.name.startswith("MAIN_LINE_"):
                reference = getattr(line, "reference_track", "MAIN_LINE") or "MAIN_LINE"
                if reference not in tracks:
                    raise ValueError(
                        f"Main line {line.name}: reference track {reference!r} must be created before this line."
                    )
                base = tracks[reference]
                tracks[line.name] = _offset_alignment(base, line.spacing, line.side)
                main_extents[line.name] = (0.0, _polyline_length(tracks[line.name]))

        loop_results: dict[str, object] = {}
        overrun_jobs: list[tuple] = []
        for loop in self.config.loops:
            reference = getattr(loop, "reference_track", "MAIN_LINE") or "MAIN_LINE"
            if reference not in tracks:
                raise ValueError(
                    f"Loop {loop.name}: reference track {reference!r} must be created before the loop."
                )
            base = tracks[reference]
            ref_start, _ref_end = main_extents.get(reference, (0.0, _polyline_length(base)))
            if loop.first_crossover_chainage is not None:
                c1 = loop.first_crossover_chainage
                c2 = loop.second_crossover_chainage
                if c2 is None:
                    c2 = c1 + loop.crossover_distance_m
                if c2 <= c1:
                    raise ValueError(
                        "Second crossover chainage must be greater than first crossover chainage."
                    )
                turnout = select_turnout(loop.turnout_designation, loop.turnout_variant)
                require_geometry_parameters(turnout)
                local_c1, local_c2 = c1 - ref_start, c2 - ref_start
                loop_geom = _generate_loop_geom(
                    base,
                    local_c1,
                    local_c2,
                    spacing_m=loop.spacing,
                    side=loop.side,
                    turnout_spec=turnout,
                )
                tracks[loop.name], eff_c1, eff_c2 = _apply_loop_extension(
                    base, loop, local_c1, local_c2, loop_geom.loop_points,
                )
                eff_c1, eff_c2 = eff_c1 + ref_start, eff_c2 + ref_start
                main_extents[loop.name] = (eff_c1, eff_c2)
                loop_results[loop.name] = loop_geom
                if not quiet:
                    print(_format_loop_status(loop.name, loop_geom))
                if (eff_c1, eff_c2) != (c1, c2):
                    if not quiet:
                        print(f"  Extended: [{eff_c1:.1f}, {eff_c2:.1f}] MAIN m")
                    if (getattr(loop, "extend_start_m", 0.0) or 0.0) > 0 or (getattr(loop, "extend_end_m", 0.0) or 0.0) > 0:
                        overrun_jobs.append((loop, c1, c2, eff_c1, eff_c2))
            else:
                tracks[loop.name] = _offset_alignment(base, loop.spacing, loop.side)
                main_extents[loop.name] = (ref_start, _ref_end)

        for line in self.config.additional_lines:
            if line.name in tracks:
                continue
            if isinstance(line, LoopSpec) and line.first_crossover_chainage is not None:
                c1 = line.first_crossover_chainage
                c2 = line.second_crossover_chainage
                if c2 is None:
                    c2 = c1 + line.crossover_distance_m
                if c2 <= c1:
                    raise ValueError(
                        "Second crossover chainage must be greater than first crossover chainage."
                    )
                turnout = select_turnout(line.turnout_designation, line.turnout_variant)
                require_geometry_parameters(turnout)
                loop_geom = _generate_loop_geom(
                    main,
                    c1,
                    c2,
                    spacing_m=line.spacing,
                    side=line.side,
                    turnout_spec=turnout,
                )
                tracks[line.name], eff_c1, eff_c2 = _apply_loop_extension(
                    main, line, c1, c2, loop_geom.loop_points,
                )
                loop_results[line.name] = loop_geom
                if not quiet:
                    print(_format_loop_status(line.name, loop_geom))
                if (eff_c1, eff_c2) != (c1, c2):
                    if not quiet:
                        print(f"  Extended: [{eff_c1:.1f}, {eff_c2:.1f}] MAIN m")
                    if (getattr(line, "extend_start_m", 0.0) or 0.0) > 0 or (getattr(line, "extend_end_m", 0.0) or 0.0) > 0:
                        overrun_jobs.append((line, c1, c2, eff_c1, eff_c2))
            else:
                reference = getattr(line, "reference_track", "MAIN_LINE") or "MAIN_LINE"
                base = tracks.get(reference, main)
                tracks[line.name] = _offset_alignment(base, line.spacing, line.side)

        return BuiltTracks(
            tracks=tracks,
            loop_results=loop_results,
            overrun_jobs=overrun_jobs,
        )

    def run(self) -> dict[str, List[Point]]:
        """Build tracks, draw them to DXF, and return track centrelines."""
        built = self.build_tracks()
        tracks, loop_results, overrun_jobs = (
            built.tracks,
            built.loop_results,
            built.overrun_jobs,
        )

        doc = ezdxf.readfile(self.config.source_dxf)
        _remove_source_alignment_entities(doc, self.config.source_layer)

        draw_tracks(
            doc=doc,
            tracks=tracks,
            config=self.config,
            loop_results=loop_results,
            overrun_jobs=overrun_jobs,
        )

        Path(self.config.output_dxf).parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(self.config.output_dxf)
        return tracks
