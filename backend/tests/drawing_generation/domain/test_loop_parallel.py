"""Loops must run exactly parallel to their reference (like added MAINs)."""

from __future__ import annotations

import ezdxf
from app.features.drawing_generation.domain.geometry.operations import (
    nearest_point_on_alignment,
    point_at_chainage,
)
from app.features.drawing_generation.domain.track.generator import (
    TrackGenerationConfig,
    TrackGenerator,
)
from app.features.drawing_generation.domain.track.specs import LineSpec, LoopSpec


def _kinked_source(path, layer="MAIN_TRACK"):
    doc = ezdxf.new("R2010")
    doc.layers.add(layer, color=1)
    doc.modelspace().add_lwpolyline(
        [(0, 0), (500, 0), (600, 20), (1000, 20)],
        dxfattribs={"layer": layer},
    )
    doc.saveas(path)


def _perp_gap(main_pts, loop_pts, spacing, samples):
    worst = 0.0
    for ch in samples:
        anchor = point_at_chainage(main_pts, ch).point
        gap = nearest_point_on_alignment(loop_pts, anchor).distance
        worst = max(worst, abs(gap - spacing))
    return worst


def test_bounded_loop_stays_parallel_through_kink(tmp_path):
    source = tmp_path / "source.dxf"
    output = tmp_path / "result.dxf"
    _kinked_source(str(source))

    config = TrackGenerationConfig(
        str(source), str(output), "MAIN_TRACK",
        loops=[LoopSpec("LOOP_1", 5.3, "LEFT", 100, 900,
                        extend_start_m=0, extend_end_m=0)],
        additional_lines=[LineSpec("MAIN_LINE_1", 5.3, "LEFT", "DN")],
    )
    tracks = TrackGenerator(config).run()

    main, loop = tracks["MAIN_LINE"], tracks["LOOP_1"]
    assert len(loop) > 2
    samples = [float(ch) for ch in range(200, 801, 50)]
    assert _perp_gap(main, loop, 5.3, samples) <= 0.15
    assert _perp_gap(main, tracks["MAIN_LINE_1"], 5.3, samples) <= 0.15


def test_loop_drawn_as_exact_polyline_not_spline(tmp_path):
    source = tmp_path / "source.dxf"
    output = tmp_path / "result.dxf"
    _kinked_source(str(source))

    config = TrackGenerationConfig(
        str(source), str(output), "MAIN_TRACK",
        loops=[LoopSpec("LOOP_1", 5.3, "LEFT", 100, 900,
                        extend_start_m=0, extend_end_m=0)],
    )
    TrackGenerator(config).run()

    rendered = ezdxf.readfile(str(output))
    drawn = [e for e in rendered.modelspace() if e.dxf.layer == "LOOP_1"]
    assert drawn, "LOOP_1 geometry expected"
    assert all(e.dxftype() in ("LWPOLYLINE", "POLYLINE") for e in drawn)
    assert not [e for e in drawn if e.dxftype() == "SPLINE"]


def test_chained_loop_reference_track_overrun_cuts_and_crossover(tmp_path):
    from app.features.drawing_generation.domain.track.crossover import (
        CrossoverPlanner,
        requests_from_specs,
    )
    from app.features.drawing_generation.domain.track.generator import _offset_alignment
    from app.features.drawing_generation.domain.track.specs import CrossoverSpec
    from app.features.drawing_generation.domain.track.turnouts import select_turnout
    from app.features.drawing_generation.pipeline.steps.crossover_cuts import (
        apply_loop_overrun_cuts,
    )

    main_pts = [(float(x), 0.0) for x in range(0, 1500, 10)]
    l1 = _offset_alignment(main_pts, 5.3, "RIGHT")
    l2 = _offset_alignment(main_pts, 5.3, "LEFT")
    l3 = _offset_alignment(l2, 5.3, "LEFT")

    tracks = {
        "MAIN_LINE": main_pts,
        "LOOP_1": l1,
        "LOOP_2": l2,
        "LOOP_3": l3,
    }

    extents = {
        "LOOP_1": (230.0, 1220.0),
        "LOOP_2": (230.0, 1220.0),
        "LOOP_3": (230.0, 1220.0),
    }

    specs = [
        CrossoverSpec(
            id="C1",
            from_track="LOOP_2",
            to_track="LOOP_3",
            from_chainage_m=500.0,
            direction="FORWARD",
            turnout=select_turnout("1:12"),
        )
    ]

    reqs = requests_from_specs(specs)
    planner = CrossoverPlanner(tracks, extents, 1500.0)
    results, report = planner.plan(reqs)
    assert report.overall_valid

    loop_specs = [
        LoopSpec(name="LOOP_1", side="RIGHT", spacing=5.3, first_crossover_chainage=350.0, second_crossover_chainage=1100.0),
        LoopSpec(name="LOOP_2", side="LEFT", spacing=5.3, first_crossover_chainage=350.0, second_crossover_chainage=1100.0),
        LoopSpec(name="LOOP_3", side="LEFT", spacing=5.3, reference_track="LOOP_2", first_crossover_chainage=350.0, second_crossover_chainage=1100.0),
    ]

    ranges = {
        "LOOP_1": (350.0, 1100.0, 230.0, 1220.0),
        "LOOP_2": (350.0, 1100.0, 230.0, 1220.0),
        "LOOP_3": (350.0, 1100.0, 230.0, 1220.0),
    }

    doc_file = tmp_path / "test_chained_loops.dxf"
    doc = ezdxf.new()
    doc.saveas(str(doc_file))

    cuts, trim_extents, full_lines, splits = apply_loop_overrun_cuts(
        doc_path=str(doc_file),
        tracks=tracks,
        crossover_results=results,
        loops_spec=loop_specs,
        additional_lines_spec=[],
        ranges=ranges,
    )

    assert "LOOP_1" in full_lines
    assert "LOOP_2" in full_lines
    assert "LOOP_3" in full_lines

    # LOOP_1 is at -5.3 on RIGHT
    assert abs(full_lines["LOOP_1"][0][1] - (-5.3)) < 1e-3
    # LOOP_2 is at +5.3 on LEFT
    assert abs(full_lines["LOOP_2"][0][1] - 5.3) < 1e-3
    # LOOP_3 references LOOP_2 (spacing 5.3, side LEFT) -> net offset +10.6 on LEFT
    assert abs(full_lines["LOOP_3"][0][1] - 10.6) < 1e-3

    rendered = ezdxf.readfile(str(doc_file))
    layers_in_doc = {e.dxf.layer for e in rendered.modelspace()}
    assert "LOOP_1" in layers_in_doc
    assert "LOOP_2" in layers_in_doc
    assert "LOOP_3" in layers_in_doc


def test_dynamic_multi_loop_extensions_and_overruns(tmp_path):
    """Verify that multiple loops on left and right sides dynamically extend their running lines

    to the exact touch point of connected crossovers, and overrun lines start at those extended points.
    Farthest loop on each side maintains nominal 750m length.
    """
    from app.features.drawing_generation.config import ESPConfig
    from app.features.drawing_generation.domain.track.specs import (
        CrossoverSpec,
        LoopSpec,
    )
    from app.features.drawing_generation.domain.track.turnouts import select_turnout
    from app.features.drawing_generation.pipeline.generator import ESPGenerator

    src_dxf = tmp_path / "multi_loop_src.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_line((0.0, 0.0), (2500.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src_dxf))

    out_dxf = tmp_path / "multi_loop_out.dxf"

    # 3 loops on LEFT, 1 loop on RIGHT
    loops = [
        LoopSpec(name="LOOP_1", side="LEFT", spacing=5.3, reference_track="MAIN_LINE",
                 first_crossover_chainage=500.0, second_crossover_chainage=1250.0,
                 extend_start_m=120.0, extend_end_m=120.0),
        LoopSpec(name="LOOP_2", side="LEFT", spacing=5.3, reference_track="LOOP_1",
                 first_crossover_chainage=500.0, second_crossover_chainage=1250.0,
                 extend_start_m=120.0, extend_end_m=120.0),
        LoopSpec(name="LOOP_3", side="LEFT", spacing=5.3, reference_track="LOOP_2",
                 first_crossover_chainage=500.0, second_crossover_chainage=1250.0,
                 extend_start_m=120.0, extend_end_m=120.0),
        LoopSpec(name="LOOP_4", side="RIGHT", spacing=5.3, reference_track="MAIN_LINE",
                 first_crossover_chainage=500.0, second_crossover_chainage=1250.0,
                 extend_start_m=120.0, extend_end_m=120.0),
    ]

    t12 = select_turnout("1:12")
    # Crossover 1: from LOOP_2 to LOOP_3, touches LOOP_3 at 500m (farthest line start)
    # Crossover 2: from LOOP_1 to LOOP_2, arrives on LOOP_2 at 389.422m (13m separation before C1's 402.422m SRJ)
    # Crossover 3: from MAIN_LINE to LOOP_4, touches LOOP_4 at 500m (farthest line on right side)
    crossovers = [
        CrossoverSpec(id="C1", from_track="LOOP_2", to_track="LOOP_3",
                      from_chainage_m=402.422, direction="FORWARD", turnout=t12, position_mode="FIXED"),
        CrossoverSpec(id="C2", from_track="LOOP_1", to_track="LOOP_2",
                      from_chainage_m=291.844, direction="FORWARD", turnout=t12, position_mode="FIXED"),
        CrossoverSpec(id="C3", from_track="MAIN_LINE", to_track="LOOP_4",
                      from_chainage_m=402.422, direction="FORWARD", turnout=t12, position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src_dxf),
        output_dxf=str(out_dxf),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        additional_lines=[],
        platforms=[],
        stations=[],
        crossovers=crossovers,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    # Verify trim extents for each loop:
    trim = gen._loop_trim_extents
    # LOOP_3 (farthest on LEFT) starts at 500.0m
    assert abs(trim["LOOP_3"][0] - 500.0) < 0.1
    # LOOP_2 extends to 389.42m where C2 touches it
    assert abs(trim["LOOP_2"][0] - 389.422) < 0.1
    # LOOP_1 extends to 291.84m where C2 starts
    assert abs(trim["LOOP_1"][0] - 291.844) < 0.1
    # LOOP_4 (farthest on RIGHT) starts at 500.0m
    assert abs(trim["LOOP_4"][0] - 500.0) < 0.1

    # Verify in the generated DXF
    rendered = ezdxf.readfile(str(out_dxf))
    layers = {e.dxf.layer for e in rendered.modelspace()}
    assert "LOOP_1" in layers
    assert "LOOP_2" in layers
    assert "LOOP_3" in layers
    assert "LOOP_4" in layers
    assert "OVER_RUN" in layers
    assert "CROSSOVERS" in layers

    # Check loop running lines
    l1_ents = [e for e in rendered.modelspace() if e.dxf.layer == "LOOP_1"]
    assert len(l1_ents) == 1
    l1_pts = list(l1_ents[0].get_points())
    assert abs(l1_pts[0][0] - 291.844) < 0.1

    l2_ents = [e for e in rendered.modelspace() if e.dxf.layer == "LOOP_2"]
    assert len(l2_ents) == 1
    l2_pts = list(l2_ents[0].get_points())
    assert abs(l2_pts[0][0] - 389.422) < 0.1

    l3_ents = [e for e in rendered.modelspace() if e.dxf.layer == "LOOP_3"]
    assert len(l3_ents) == 1
    l3_pts = list(l3_ents[0].get_points())
    assert abs(l3_pts[0][0] - 500.0) < 0.1

    l4_ents = [e for e in rendered.modelspace() if e.dxf.layer == "LOOP_4"]
    assert len(l4_ents) == 1
    l4_pts = list(l4_ents[0].get_points())
    assert abs(l4_pts[0][0] - 500.0) < 0.1
