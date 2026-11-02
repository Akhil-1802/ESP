"""Tests for station center chainage input and display."""

from __future__ import annotations

import json
import ezdxf
import pytest

from config.loader import ESPConfig, PlatformRequest, StationRequest, load_config_from_json
from pipeline.orchestrator import ESPGenerator
from pipeline.steps.station import _format_station_chainage
from platform_gen.config import PlatformConfig


def test_format_station_chainage():
    assert _format_station_chainage(None) is None
    assert _format_station_chainage("") is None
    assert _format_station_chainage("   ") is None
    assert _format_station_chainage("125") == "KM: 125.000"
    assert _format_station_chainage(125) == "KM: 125.000"
    assert _format_station_chainage("125 KM") == "KM: 125.000"
    assert _format_station_chainage("CH: 125 KM") == "KM: 125.000"
    assert _format_station_chainage("CH : 125 KM") == "KM: 125.000"
    assert _format_station_chainage("68.48") == "KM: 68.480"
    assert _format_station_chainage(68.48) == "KM: 68.480"
    assert _format_station_chainage("KM: 68.48") == "KM: 68.480"


def test_station_center_chainage_in_dxf(tmp_path):
    src = tmp_path / "src.dxf"
    out = tmp_path / "out.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line(
        (0.0, 0.0), (2000.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"}
    )
    doc.saveas(str(src))

    pcfg = PlatformConfig(
        source_dxf=str(src),
        output_dxf=str(out),
        track_layer="MAIN_LINE",
        platform_type="SIDE",
        side="LEFT",
        center_on_track=True,
        clearance=1.68,
        platform_width=7.0,
        platform_length=550.0,
        platform_name="PLATFORM 1",
        output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT",
    )
    gen = ESPGenerator(
        ESPConfig(
            source_path=str(src),
            output_dxf=str(out),
            track_source_layer="MAIN_TRACK",
            loops=[],
            additional_lines=[],
            platforms=[PlatformRequest(track_layer="MAIN_LINE", config=pcfg)],
            stations=[
                StationRequest(
                    platform_layer="PLATFORM_1",
                    building_length=40.0,
                    building_width=10.0,
                    platform_side="LEFT",
                    building_name="STATION BUILDING",
                    station_chainage="125",
                )
            ],
            crossovers=[],
            main_directions={},
        )
    )
    gen.run()

    check = ezdxf.readfile(str(out))
    cl_entities = [
        e
        for e in check.modelspace()
        if e.dxf.layer == "STATION-CENTER" and e.dxftype() in ("MTEXT", "TEXT")
    ]
    assert cl_entities, "STATION-CENTER text entity should exist"

    texts = [e.text if e.dxftype() == "MTEXT" else e.dxf.text for e in cl_entities]
    combined = "\n".join(texts)
    assert "C/L OF STATION BUILDING CH:0.00 KM" in combined
    assert "KM: 125.000" in combined

    # Verify positions: Line 2 must be below Line 1
    t1 = next(e for e in cl_entities if "C/L OF STATION BUILDING CH:0.00 KM" in (e.text if e.dxftype() == "MTEXT" else e.dxf.text))
    t2 = next(e for e in cl_entities if "KM: 125.000" in (e.text if e.dxftype() == "MTEXT" else e.dxf.text))
    y1 = t1.dxf.insert[1]
    y2 = t2.dxf.insert[1]
    # Line 2 should be directly under Line 1, not ahead (x2 ~ x1)
    x1 = t1.dxf.insert[0]
    x2 = t2.dxf.insert[0]
    assert x2 == pytest.approx(x1, abs=0.5), f"Line 2 (x={x2}) should be directly under Line 1 (x1={x1})"


def test_station_center_without_chainage_in_dxf(tmp_path):
    src = tmp_path / "src.dxf"
    out = tmp_path / "out.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line(
        (0.0, 0.0), (2000.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"}
    )
    doc.saveas(str(src))

    pcfg = PlatformConfig(
        source_dxf=str(src),
        output_dxf=str(out),
        track_layer="MAIN_LINE",
        platform_type="SIDE",
        side="LEFT",
        center_on_track=True,
        clearance=1.68,
        platform_width=7.0,
        platform_length=550.0,
        platform_name="PLATFORM 1",
        output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT",
    )
    gen = ESPGenerator(
        ESPConfig(
            source_path=str(src),
            output_dxf=str(out),
            track_source_layer="MAIN_TRACK",
            loops=[],
            additional_lines=[],
            platforms=[PlatformRequest(track_layer="MAIN_LINE", config=pcfg)],
            stations=[
                StationRequest(
                    platform_layer="PLATFORM_1",
                    building_length=40.0,
                    building_width=10.0,
                    platform_side="LEFT",
                    building_name="STATION BUILDING",
                    station_chainage=None,
                )
            ],
            crossovers=[],
            main_directions={},
        )
    )
    gen.run()

    check = ezdxf.readfile(str(out))
    cl_entities = [
        e
        for e in check.modelspace()
        if e.dxf.layer == "STATION-CENTER" and e.dxftype() in ("MTEXT", "TEXT")
    ]
    assert cl_entities

    texts = [e.text if e.dxftype() == "MTEXT" else e.dxf.text for e in cl_entities]
    combined = "\n".join(texts)
    assert "C/L OF STATION BUILDING CH:0.00 KM" in combined
    assert "KM: " not in combined


def test_load_station_config_json_aliases(tmp_path):
    cfg_file = tmp_path / "config.json"
    dummy_src = tmp_path / "dummy.dxf"
    ezdxf.new().saveas(str(dummy_src))

    content = {
        "source_path": str(dummy_src),
        "output_dxf": str(tmp_path / "out.dxf"),
        "track_source_layer": "MAIN_TRACK",
        "stations": [
            {
                "platform_layer": "PLATFORM_1",
                "building_length": 40.0,
                "building_width": 10.0,
                "chainage": "125",
            },
            {
                "platform_layer": "PLATFORM_2",
                "building_length": 40.0,
                "building_width": 10.0,
                "station_chainage": "72.10",
            },
        ],
    }
    cfg_file.write_text(json.dumps(content), encoding="utf-8")
    loaded = load_config_from_json(str(cfg_file))
    assert len(loaded.stations) == 2
    assert loaded.stations[0].station_chainage == "125"
    assert loaded.stations[1].station_chainage == "72.10"
