"""Regression coverage for clean, independent MAIN_LINE_N rendering."""

from __future__ import annotations

import ezdxf
import pytest

from track.generator import TrackGenerationConfig, TrackGenerator
from track.specs import LineSpec, LoopSpec


def _entities_on(doc, layer: str):
    return [entity for entity in doc.modelspace() if entity.dxf.layer == layer]


def test_added_main_lines_are_clean_parallels_with_own_directions(tmp_path):
    source = tmp_path / "source.dxf"
    output = tmp_path / "result.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_lwpolyline(
        [(0, 0), (100, 0), (98.6, 0)], dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)

    config = TrackGenerationConfig(
        source_dxf=str(source),
        output_dxf=str(output),
        source_layer="MAIN_TRACK",
        additional_lines=[LineSpec("MAIN_LINE_1", 5.3, "LEFT", "DN")],
        main_directions={"MAIN_LINE": "UP", "MAIN_LINE_1": "DN"},
    )
    tracks = TrackGenerator(config).run()

    assert tracks["MAIN_LINE"] == [(0.0, 0.0), (100.0, 0.0)]
    assert tracks["MAIN_LINE_1"] == [(0.0, 5.3), (100.0, 5.3)]

    rendered = ezdxf.readfile(output)
    assert _entities_on(rendered, "MAIN_TRACK") == []
    tc_entities = [e for e in _entities_on(rendered, "TRACK_CENTERS")
                   if e.dxftype() in ("TEXT", "DIMENSION")]
    assert len(tc_entities) == 2
    for e in tc_entities:
        if e.dxftype() == "DIMENSION":
            assert e.dxf.text in ("T.C=<>M", "T.C=5.3M")
        else:
            assert e.dxf.text == "T.C=5.3M"
            assert e.dxf.rotation == 0.0
    assert _entities_on(rendered, "OVER_RUN") == []

    direction_texts = {
        entity.dxf.text: entity.dxf.insert.y
        for entity in _entities_on(rendered, "DIRECTION")
        if entity.dxftype() == "TEXT"
    }
    assert direction_texts["UP"] == pytest.approx(2.0)
    assert direction_texts["DN"] == pytest.approx(7.3)


def test_loop_can_reference_an_added_main_line(tmp_path):
    source = tmp_path / "source.dxf"
    output = tmp_path / "result.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_lwpolyline([(0, 0), (1000, 0)], dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)
    config = TrackGenerationConfig(
        str(source), str(output), "MAIN_TRACK",
        loops=[LoopSpec("LOOP_1", 5.3, "LEFT", 100, 850, extend_start_m=0, extend_end_m=0,
                        reference_track="MAIN_LINE_1")],
        additional_lines=[LineSpec("MAIN_LINE_1", 5.3, "LEFT", "DN")],
    )
    tracks = TrackGenerator(config).build_tracks(quiet=True).tracks
    assert "MAIN_LINE_1" in tracks
    assert "LOOP_1" in tracks
