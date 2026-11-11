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

    # 1. Closed outline LWPOLYLINE
    polylines = [e for e in flag_entities if e.dxftype() == "LWPOLYLINE"]
    assert len(polylines) == 1
    flag = polylines[0]
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

    # 2. No circles on flag
    circles = [e for e in flag_entities if e.dxftype() == "CIRCLE"]
    assert len(circles) == 0

    # 3. Pole & hatch lines
    lines = [e for e in flag_entities if e.dxftype() == "LINE"]
    assert len(lines) > 10  # pole + diagonal hatch lines
    for line in lines:
        assert line.dxf.color == 1


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
    assert len(flags) > 0
    assert any(e.dxftype() == "LWPOLYLINE" for e in flags)
    assert not any(e.dxftype() == "CIRCLE" for e in flags)
    assert any(e.dxftype() == "LINE" for e in flags)

    # Station roof outer edge:
    # MAIN_LINE y = 0.0, clearance = 1.68, platform width = 7.0, building clearance ~ 1.0, width = 10.0 -> roof y ~ 19.68
    bldgs = [e for e in doc_out.modelspace() if e.dxf.layer == "STATION-BUILDING" and e.dxftype() in ("LWPOLYLINE", "POLYLINE")]
    assert bldgs
    bldg_pts = [p for b in bldgs for p in b.get_points()]
    station_roof_y = max(p[1] for p in bldg_pts)
    land_boundary_y = station_roof_y + 40.0

    # Every flag entity vertex must be strictly UNDER the 40m land boundary
    for f in flags:
        if f.dxftype() == "LWPOLYLINE":
            for p in f.get_points():
                assert p[1] < land_boundary_y, f"Flag vertex {p} must be below boundary {land_boundary_y}"
        elif f.dxftype() == "LINE":
            assert f.dxf.start.y < land_boundary_y
            assert f.dxf.end.y < land_boundary_y

    # Station centerline text & lines must also be under the 40m land boundary
    cl_entities = [e for e in doc_out.modelspace() if e.dxf.layer == "STATION-CENTER"]
    for cl in cl_entities:
        if cl.dxftype() == "LINE":
            assert cl.dxf.start.y < land_boundary_y
            assert cl.dxf.end.y < land_boundary_y
        elif cl.dxftype() in ("TEXT", "MTEXT"):
            assert cl.dxf.insert[1] < land_boundary_y

