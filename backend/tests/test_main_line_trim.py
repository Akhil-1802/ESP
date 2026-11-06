"""Unit tests for trimming main lines 50m past outermost SRJs."""

from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from config.loader import ESPConfig
from pipeline.orchestrator import ESPGenerator
from track.specs import CrossoverSpec, LineSpec, LoopSpec
from track.turnouts import select_turnout


def _create_source_dxf(path, length=2000.0, layer="MAIN_TRACK"):
    doc = ezdxf.new("R2010")
    doc.layers.add(layer, color=1)
    doc.modelspace().add_line((0.0, 0.0), (length, 0.0), dxfattribs={"layer": layer})
    doc.saveas(str(path))


def test_main_lines_trimmed_to_50m_past_srjs(tmp_path):
    """Verify that main lines are trimmed to 50m past outermost SRJs."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 500.0, 1250.0, extend_start_m=120.0, extend_end_m=120.0),
        LoopSpec("LOOP_2", 5.3, "RIGHT", 500.0, 1250.0, extend_start_m=120.0, extend_end_m=120.0),
    ]
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("MAIN_LINE", "LOOP_2", 700.0, None,
                      select_turnout("1:12"), "AHEAD", id="C2",
                      direction="FORWARD", position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        additional_lines=[LineSpec("MAIN_LINE_1", 5.3, "LEFT", "DN")],
        platforms=[],
        stations=[],
        crossovers=xspecs,
        main_directions={"MAIN_LINE": "UP", "MAIN_LINE_1": "DN"},
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    assert gen._main_line_trim_range is not None
    start_dist, end_dist = gen._main_line_trim_range

    assert start_dist == pytest.approx(450.0, abs=1e-2)
    assert end_dist == pytest.approx(700.0 + 97.578 + 50.0, abs=0.1)

    doc = ezdxf.readfile(str(out))
    main_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE"]
    assert len(main_entities) == 1
    m_pts = list(main_entities[0].get_points())
    assert m_pts[0][0] == pytest.approx(450.0, abs=1e-2)
    assert m_pts[-1][0] == pytest.approx(end_dist, abs=1e-2)

    m1_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE_1"]
    assert len(m1_entities) == 1
    m1_pts = list(m1_entities[0].get_points())
    assert m1_pts[0][0] == pytest.approx(450.0, abs=1e-2)
    assert m1_pts[-1][0] == pytest.approx(end_dist, abs=1e-2)


def test_user_example_exact_numbers(tmp_path):
    """Verify user's explicit example: left SRJ at 55m, right SRJ at 1050m on 2000m line."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 55.0, 1050.0, extend_start_m=0.0, extend_end_m=0.0),
    ]
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 55.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("MAIN_LINE", "LOOP_1", 1050.0, None,
                      select_turnout("1:12"), "BEHIND", id="C2",
                      direction="REVERSE", position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        additional_lines=[],
        platforms=[],
        stations=[],
        crossovers=xspecs,
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    assert gen._main_line_trim_range is not None
    start_dist, end_dist = gen._main_line_trim_range

    assert start_dist == pytest.approx(5.0, abs=1e-2)
    assert end_dist == pytest.approx(1100.0, abs=1e-2)

    doc = ezdxf.readfile(str(out))
    main_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE"]
    assert len(main_entities) == 1
    pts = list(main_entities[0].get_points())
    assert pts[0][0] == pytest.approx(5.0, abs=1e-2)
    assert pts[-1][0] == pytest.approx(1100.0, abs=1e-2)


def test_no_srj_leaves_main_lines_full_length(tmp_path):
    """When no crossovers or SRJs exist, main lines remain full length."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=[],
        additional_lines=[],
        platforms=[],
        stations=[],
        crossovers=[],
    )

    gen = ESPGenerator(cfg)
    gen.run()

    assert gen._main_line_trim_range is None

    doc = ezdxf.readfile(str(out))
    main_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE"]
    assert len(main_entities) == 1
    pts = list(main_entities[0].get_points())
    assert pts[0][0] == pytest.approx(0.0, abs=1e-2)
    assert pts[-1][0] == pytest.approx(2000.0, abs=1e-2)


def test_single_crossover_on_start_side_preserves_far_end(tmp_path):
    """Guard rule: when only one crossover exists on start side, far end is not truncated."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=1663.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 200.0, 950.0, extend_start_m=0.0, extend_end_m=0.0),
    ]
    # Single crossover at chainage 200m (on start side of 1663m line)
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 200.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        additional_lines=[],
        platforms=[],
        stations=[],
        crossovers=xspecs,
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    assert gen._main_line_trim_range is not None
    start_dist, end_dist = gen._main_line_trim_range

    # Near end is trimmed 50m before SRJ (200 - 50 = 150m)
    assert start_dist == pytest.approx(150.0, abs=1e-2)
    # Far end must NOT be truncated; it must extend all the way to 1663.0m!
    assert end_dist == pytest.approx(1663.0, abs=1e-2)

    doc = ezdxf.readfile(str(out))
    main_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE"]
    assert len(main_entities) == 1
    pts = list(main_entities[0].get_points())
    assert pts[0][0] == pytest.approx(150.0, abs=1e-2)
    assert pts[-1][0] == pytest.approx(1663.0, abs=1e-2)


def test_single_crossover_on_end_side_preserves_start(tmp_path):
    """Guard rule: when only one crossover exists on end side, near start is not truncated."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 1000.0, 1800.0, extend_start_m=0.0, extend_end_m=0.0),
    ]
    # Single crossover at chainage 1500m (on end side of 2000m line)
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 1500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        additional_lines=[],
        platforms=[],
        stations=[],
        crossovers=xspecs,
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    assert gen._main_line_trim_range is not None
    start_dist, end_dist = gen._main_line_trim_range

    # Start must NOT be truncated (remains 0.0m)
    assert start_dist == pytest.approx(0.0, abs=1e-2)
    # End is trimmed 50m past outermost SRJ
    assert end_dist > 1500.0
    assert end_dist < 2000.0

    doc = ezdxf.readfile(str(out))
    main_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE"]
    assert len(main_entities) == 1
    pts = list(main_entities[0].get_points())
    assert pts[0][0] == pytest.approx(0.0, abs=1e-2)
    assert pts[-1][0] == pytest.approx(end_dist, abs=1e-2)


def test_default_leaves_main_lines_full_length_without_50m_srj_trim(tmp_path):
    """By default, 50m SRJ trimming is disabled and main lines remain full surveyed length."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 500.0, 1250.0, extend_start_m=120.0, extend_end_m=120.0),
    ]
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("MAIN_LINE", "LOOP_1", 1200.0, None,
                      select_turnout("1:12"), "AHEAD", id="C2",
                      direction="FORWARD", position_mode="FIXED"),
    ]

    # Default ESPConfig: enable_main_line_trim is False by default
    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        additional_lines=[],
        platforms=[],
        stations=[],
        crossovers=xspecs,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    # Main line trim range must not be set
    assert getattr(gen, "_main_line_trim_range", None) is None

    # Main line in the output DXF spans the entire 2000m length
    doc = ezdxf.readfile(str(out))
    main_entities = [e for e in doc.modelspace() if e.dxf.layer == "MAIN_LINE"]
    assert len(main_entities) == 1
    pts = list(main_entities[0].get_points())
    assert pts[0][0] == pytest.approx(0.0, abs=1e-2)
    assert pts[-1][0] == pytest.approx(2000.0, abs=1e-2)

