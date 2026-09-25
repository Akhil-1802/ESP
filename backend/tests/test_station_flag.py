"""Tests for the red waving station flag."""

from __future__ import annotations

import ezdxf
import pytest

from config.loader import ESPConfig, PlatformRequest, StationRequest
from pipeline.orchestrator import ESPGenerator
from platform_gen.config import PlatformConfig
from station.station_flag import (
    FLAG_COLOR,
    FLAG_HEIGHT,
    FLAG_LAYER,
    FLAG_WIDTH,
    draw_station_flag,
)


def test_draw_station_flag_direct():
    doc = ezdxf.new("R2010")
    pole_base = (100.0, 50.0)
    flag_up = (0.0, 1.0)
    flag_right = (1.0, 0.0)

    draw_station_flag(doc, pole_base, flag_up, flag_right, color=1)

    msp = doc.modelspace()
    flag_entities = [e for e in msp if e.dxf.layer == FLAG_LAYER]
    assert len(flag_entities) == 1
    flag = flag_entities[0]
    assert flag.dxftype() == "LWPOLYLINE"
    assert flag.dxf.color == 1
    assert flag.is_closed

    pts = list(flag.get_points())
    assert len(pts) == 50

    assert pts[0][0] == pytest.approx(100.0)
    assert pts[0][1] == pytest.approx(50.0)

    assert pts[-1][0] == pytest.approx(100.0)
    assert pts[-1][1] == pytest.approx(50.0 - FLAG_HEIGHT)

    xs = [p[0] for p in pts]
    assert max(xs) == pytest.approx(100.0 + FLAG_WIDTH)


def test_station_flag_end_to_end(tmp_path):
    src = tmp_path / "src.dxf"
    out = tmp_path / "out.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line((0.0, 0.0), (2000.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src))

    pcfg = PlatformConfig(
        source_dxf=str(src), output_dxf=str(out), track_layer="MAIN_LINE",
        platform_type="SIDE", side="LEFT", center_on_track=True,
        clearance=1.68, platform_width=7.0, platform_length=550.0,
        platform_name="PLATFORM 1", output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT",
    )
    gen = ESPGenerator(ESPConfig(
        source_path=str(src), output_dxf=str(out),
        track_source_layer="MAIN_TRACK", loops=[], additional_lines=[],
        platforms=[PlatformRequest(track_layer="MAIN_LINE", config=pcfg)],
        stations=[StationRequest(
            platform_layer="PLATFORM_1", building_length=40.0,
            building_width=10.0, platform_side="LEFT",
            building_name="STATION BUILDING",
        )],
        crossovers=[], main_directions={},
    ))
    gen.run()

    doc_out = ezdxf.readfile(str(out))
    flags = [e for e in doc_out.modelspace() if e.dxf.layer == FLAG_LAYER]
    assert len(flags) == 1
