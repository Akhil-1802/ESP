"""Loops must run exactly parallel to their reference (like added MAINs)."""

from __future__ import annotations

import ezdxf
import pytest

from common.geometry import nearest_point_on_alignment, point_at_chainage
from track.generator import TrackGenerationConfig, TrackGenerator
from track.specs import LineSpec, LoopSpec


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
