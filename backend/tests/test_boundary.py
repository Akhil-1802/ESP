"""Unit tests for land boundary generation."""

from __future__ import annotations

import ezdxf
import pytest

from config.loader import ESPConfig
from pipeline.orchestrator import ESPGenerator
from track.specs import CrossoverSpec, LoopSpec
from track.turnouts import select_turnout


def _create_source_dxf(path, length=2000.0, layer="MAIN_TRACK"):
    doc = ezdxf.new("R2010")
    doc.layers.add(layer, color=1)
    doc.modelspace().add_line((0.0, 0.0), (length, 0.0), dxfattribs={"layer": layer})
    doc.saveas(str(path))


def test_land_boundary_with_station(tmp_path):
    """Station on LEFT -> boundary is station + 40m on LEFT, other entity + 70m on RIGHT."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 400.0, 1400.0, extend_start_m=0.0, extend_end_m=0.0),
        LoopSpec("LOOP_2", 10.0, "RIGHT", 400.0, 1400.0, extend_start_m=0.0, extend_end_m=0.0),
    ]

    from config.loader import PlatformRequest, StationRequest
    from platform_gen.config import PlatformConfig

    platforms = [
        PlatformRequest(
            track_layer="LOOP_1",
            config=PlatformConfig(
                source_dxf=str(src),
                output_dxf=str(out),
                track_layer="LOOP_1",
                platform_type="SIDE",
                side="LEFT",
                platform_width=8.0,
                platform_length=200.0,
                output_layer="PLATFORM_1",
                stair_layer="STAIRS_1",
            ),
        ),
        PlatformRequest(
            track_layer="LOOP_2",
            config=PlatformConfig(
                source_dxf=str(src),
                output_dxf=str(out),
                track_layer="LOOP_2",
                platform_type="SIDE",
                side="RIGHT",
                platform_width=6.0,
                platform_length=200.0,
                output_layer="PLATFORM_2",
                stair_layer="STAIRS_2",
            ),
        ),
    ]

    stations = [
        StationRequest(platform_layer="PLATFORM_1", building_length=40.0, building_width=12.0, building_name="TEST_STATION", platform_side="LEFT"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        platforms=platforms,
        stations=stations,
        crossovers=[],
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    doc = ezdxf.readfile(str(out))
    assert "LAND_BOUNDARY" in doc.layers
    assert doc.layers.get("LAND_BOUNDARY").dxf.color == 3
    assert doc.layers.get("LAND_BOUNDARY").dxf.linetype == "5"
    assert "5" in doc.linetypes

    b_lines = [e for e in doc.modelspace() if e.dxf.layer == "LAND_BOUNDARY"]
    assert len(b_lines) == 2

    left_b = [e for e in b_lines if list(e.get_points())[0][1] > 0][0]
    right_b = [e for e in b_lines if list(e.get_points())[0][1] < 0][0]

    left_pts = list(left_b.get_points())
    right_pts = list(right_b.get_points())

    # Full surveyed length of MAIN_LINE
    assert left_pts[0][0] == pytest.approx(0.0, abs=1e-2)
    assert left_pts[-1][0] == pytest.approx(2000.0, abs=1e-2)
    assert right_pts[0][0] == pytest.approx(0.0, abs=1e-2)
    assert right_pts[-1][0] == pytest.approx(2000.0, abs=1e-2)

    # Station building is behind PLATFORM_1 (LOOP_1 5.3 + clearance 1.68 + width 8.0 + station width 12.0 = 26.98m)
    # Left boundary: 26.98 + 40.0 = 66.98m
    assert left_pts[0][1] == pytest.approx(26.98 + 40.0, abs=0.1)
    # Right side outermost entity (platform 2 outer edge + stairs ~18.3m) -> right boundary y ~ -88.3m
    assert right_pts[0][1] == pytest.approx(-88.28, abs=0.5)


def test_land_boundary_trimmed_with_main_line(tmp_path):
    """When 50m SRJ trim is enabled, land boundary length matches trimmed MAIN_LINE exactly."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 500.0, 1250.0, extend_start_m=0.0, extend_end_m=0.0),
    ]
    xspecs = [
        CrossoverSpec("MAIN_LINE", "LOOP_1", 500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("LOOP_1", "MAIN_LINE", 1100.0, None,
                      select_turnout("1:12"), "AHEAD", id="C2",
                      direction="FORWARD", position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        crossovers=xspecs,
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    assert gen._main_line_trim_range is not None
    start_dist, end_dist = gen._main_line_trim_range

    doc = ezdxf.readfile(str(out))
    b_lines = [e for e in doc.modelspace() if e.dxf.layer == "LAND_BOUNDARY"]
    assert len(b_lines) == 2

    for b in b_lines:
        pts = list(b.get_points())
        assert pts[0][0] == pytest.approx(start_dist, abs=1e-2)
        assert pts[-1][0] == pytest.approx(end_dist, abs=1e-2)


def test_land_boundary_not_shown_before_done(tmp_path):
    """Before Done button is clicked (enable_main_line_trim=False), LAND_BOUNDARY is not present."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 500.0, 1250.0, extend_start_m=0.0, extend_end_m=0.0),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        crossovers=[],
        enable_main_line_trim=False,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    doc = ezdxf.readfile(str(out))
    b_lines = [e for e in doc.modelspace() if getattr(e.dxf, "layer", "") == "LAND_BOUNDARY"]
    assert len(b_lines) == 0


def test_land_boundary_excludes_srj_and_markers_from_offset(tmp_path):
    """Verify SRJ, FM, and overrun markers do NOT inflate the 70m boundary distance."""
    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    _create_source_dxf(src, length=2000.0)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 400.0, 1400.0, extend_start_m=0.0, extend_end_m=0.0),
        LoopSpec("LOOP_2", 5.3, "RIGHT", 400.0, 1400.0, extend_start_m=0.0, extend_end_m=0.0),
    ]

    from config.loader import PlatformRequest, StationRequest
    from platform_gen.config import PlatformConfig

    platforms = [
        PlatformRequest(
            track_layer="LOOP_1",
            config=PlatformConfig(
                source_dxf=str(src),
                output_dxf=str(out),
                track_layer="LOOP_1",
                platform_type="SIDE",
                side="LEFT",
                platform_width=8.0,
                platform_length=200.0,
                output_layer="PLATFORM_1",
                stair_layer="STAIRS_1",
            ),
        ),
    ]

    stations = [
        StationRequest(platform_layer="PLATFORM_1", building_length=40.0, building_width=12.0, building_name="TEST_STATION", platform_side="LEFT"),
    ]

    xspecs = [
        CrossoverSpec("MAIN_LINE", "LOOP_2", 500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
    ]

    cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        platforms=platforms,
        stations=stations,
        crossovers=xspecs,
        enable_main_line_trim=True,
    )

    gen = ESPGenerator(cfg)
    gen.run()

    doc = ezdxf.readfile(str(out))
    b_lines = [e for e in doc.modelspace() if e.dxf.layer == "LAND_BOUNDARY"]
    assert len(b_lines) == 2

    right_b = [e for e in b_lines if list(e.get_points())[0][1] < 0][0]
    right_pts = list(right_b.get_points())

    # Outermost track on RIGHT is LOOP_2 at -5.30m
    # Distance from LOOP_2 to boundary should be EXACTLY 70m (y = -75.30m), NOT 74m (y = -79.30m)
    assert right_pts[0][1] == pytest.approx(-5.30 - 70.0, abs=0.1)


