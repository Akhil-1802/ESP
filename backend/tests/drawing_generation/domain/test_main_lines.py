"""Regression coverage for clean, independent MAIN_LINE_N rendering."""

from __future__ import annotations

import ezdxf
import pytest
from app.features.drawing_generation.domain.track.generator import (
    TrackGenerationConfig,
    TrackGenerator,
)
from app.features.drawing_generation.domain.track.specs import LineSpec, LoopSpec


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


def test_main_line_can_reference_another_main_line(tmp_path):
    source = tmp_path / "source.dxf"
    output = tmp_path / "result.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0)], dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)

    config = TrackGenerationConfig(
        source_dxf=str(source),
        output_dxf=str(output),
        source_layer="MAIN_TRACK",
        additional_lines=[
            LineSpec("MAIN_LINE_1", 5.3, "LEFT", "DN", "MAIN_LINE"),
            LineSpec("MAIN_LINE_2", 5.3, "LEFT", "DN", "MAIN_LINE_1"),
        ],
    )
    tracks = TrackGenerator(config).build_tracks(quiet=True).tracks
    assert tracks["MAIN_LINE"] == [(0.0, 0.0), (100.0, 0.0)]
    assert tracks["MAIN_LINE_1"] == [(0.0, 5.3), (100.0, 5.3)]
    # MAIN_LINE_2 is 5.3 LEFT from MAIN_LINE_1 => Y = 10.6
    assert tracks["MAIN_LINE_2"] == [(0.0, 10.6), (100.0, 10.6)]


def test_main_line_with_invalid_reference_raises_error(tmp_path):
    source = tmp_path / "source.dxf"
    output = tmp_path / "result.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0)], dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)

    config = TrackGenerationConfig(
        source_dxf=str(source),
        output_dxf=str(output),
        source_layer="MAIN_TRACK",
        additional_lines=[
            LineSpec("MAIN_LINE_1", 5.3, "LEFT", "DN", "NON_EXISTENT_TRACK"),
        ],
    )
    with pytest.raises(ValueError, match="must be created before this line"):
        TrackGenerator(config).build_tracks(quiet=True)


def test_load_config_parses_frontend_main_lines_with_reference_track(tmp_path):
    import json

    from app.features.drawing_generation.config import load_config_from_json

    cfg_file = tmp_path / "inputconfig.json"
    kml_file = tmp_path / "test.kml"
    kml_file.write_text("<kml></kml>", encoding="utf-8")

    payload = {
        "source_path": str(kml_file),
        "output_dxf": str(tmp_path / "out.dxf"),
        "track_source_layer": "MAIN_TRACK",
        "additional_lines": [
            {
                "name": "MAIN_LINE_1",
                "spacing": 5.3,
                "side": "LEFT",
                "direction": "DN",
                "reference_track": "MAIN_LINE",
            },
            {
                "name": "MAIN_LINE_2",
                "spacing": 5.3,
                "side": "LEFT",
                "direction": "DN",
                "reference_track": "MAIN_LINE_1",
            },
        ],
    }
    cfg_file.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_config_from_json(str(cfg_file))
    assert len(loaded.additional_lines) == 2
    assert loaded.additional_lines[0].reference_track == "MAIN_LINE"
    assert loaded.additional_lines[1].reference_track == "MAIN_LINE_1"
