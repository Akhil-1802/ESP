"""Unit tests for Road Over Bridge (ROB) functionality."""

import pytest
import ezdxf

from rob.config import ROBConfig
from rob.geometry import generate_rob_geometry, write_rob
from pipeline.steps.rob import RobStep
from config.loader import ESPConfig, PlatformRequest
from platform_gen.config import PlatformConfig


def test_rob_config_validation():
    """Verify validation rules on ROBConfig."""
    cfg = ROBConfig(width=10.0, offset=40.0, reference_end="start")
    assert cfg.reference_end == "START"
    assert cfg.width == 10.0
    assert cfg.offset == 40.0
    assert cfg.block_name == "SGFD"
    assert cfg.output_layer == "SGFD"
    assert cfg.add_dimension is True

    cfg_end = ROBConfig(reference_end="END")
    assert cfg_end.reference_end == "END"

    with pytest.raises(ValueError, match="ROB width must be > 0"):
        ROBConfig(width=0.0)

    with pytest.raises(ValueError, match="ROB width must be > 0"):
        ROBConfig(width=-5.0)

    with pytest.raises(ValueError, match="ROB offset must be >= 0"):
        ROBConfig(offset=-1.0)

    with pytest.raises(ValueError, match="ROB reference_end must be 'START' or 'END'"):
        ROBConfig(reference_end="CENTER")


def test_rob_geometry_multi_track():
    """Verify that ROB spans across multiple tracks and generates 8 CAD segments."""
    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)],
        "LOOP_1": [(0.0, 5.3), (1000.0, 5.3)],
        "LOOP_2": [(0.0, 10.6), (1000.0, 10.6)],
        "MAIN_LINE_2": [(0.0, -5.3), (1000.0, -5.3)],
    }

    origin = (500.0, 0.0)
    tangent = (1.0, 0.0)
    cfg = ROBConfig(
        width=12.0,
        deck_margin=3.5,
        wing_extension=2.5,
        wing_length=8.0,
    )

    geom = generate_rob_geometry(origin, tangent, tracks, cfg)

    # Multi-track transverse extents:
    # min track is MAIN_LINE_2 at -5.3, max track is LOOP_2 at +10.6
    assert geom.deck_span[0] == pytest.approx(-5.3 - 3.5)  # -8.8
    assert geom.deck_span[1] == pytest.approx(10.6 + 3.5)  # +14.1

    diag = 8.0 * 0.7071067811865476
    assert geom.wing_span[0] == pytest.approx(-8.8 - diag)
    assert geom.wing_span[1] == pytest.approx(14.1 + diag)

    # 6 segments generated (unjoined sides with flared wings)
    assert len(geom.segments) == 6

    # hw = 6.0, origin X = 500
    # Left wall from Y=-8.8 to Y=14.1 at X=494
    left_wall = geom.segments[0]
    assert left_wall[0] == pytest.approx((494.0, -8.8))
    assert left_wall[1] == pytest.approx((494.0, 14.1))

    # Right wall from Y=-8.8 to Y=14.1 at X=506
    right_wall = geom.segments[1]
    assert right_wall[0] == pytest.approx((506.0, -8.8))
    assert right_wall[1] == pytest.approx((506.0, 14.1))

    # Top-left diagonal: flares up-left from (494, 14.1)
    top_left = geom.segments[2]
    assert top_left[0] == pytest.approx((494.0, 14.1))
    assert top_left[1] == pytest.approx((494.0 - diag, 14.1 + diag))

    # Top-right diagonal: flares up-right from (506, 14.1)
    top_right = geom.segments[3]
    assert top_right[0] == pytest.approx((506.0, 14.1))
    assert top_right[1] == pytest.approx((506.0 + diag, 14.1 + diag))

    # Bottom-left diagonal: flares down-left from (494, -8.8)
    bottom_left = geom.segments[4]
    assert bottom_left[0] == pytest.approx((494.0, -8.8))
    assert bottom_left[1] == pytest.approx((494.0 - diag, -8.8 - diag))

    # Bottom-right diagonal: flares down-right from (506, -8.8)
    bottom_right = geom.segments[5]
    assert bottom_right[0] == pytest.approx((506.0, -8.8))
    assert bottom_right[1] == pytest.approx((506.0 + diag, -8.8 - diag))

    # Test track filtering: user specifies only MAIN_LINE and LOOP_1
    cfg_subset = ROBConfig(
        width=10.0,
        deck_margin=3.5,
        wing_length=6.0,
        tracks=["MAIN_LINE", "LOOP_1"],
    )
    geom_subset = generate_rob_geometry(origin, tangent, tracks, cfg_subset)
    # MAIN_LINE is at 0.0, LOOP_1 is at 5.3
    assert geom_subset.deck_span[0] == pytest.approx(-3.5)
    assert geom_subset.deck_span[1] == pytest.approx(5.3 + 3.5)  # 8.8
    diag6 = 6.0 * 0.7071067811865476
    assert geom_subset.wing_span[0] == pytest.approx(-3.5 - diag6)
    assert geom_subset.wing_span[1] == pytest.approx(8.8 + diag6)


def test_rob_pipeline_start_minus_offset_and_end_plus_offset(tmp_path):
    """Verify platform start - offset and platform end + offset rules in pipeline."""
    dxf_path = str(tmp_path / "test_esp.dxf")
    doc = ezdxf.new("R2010")
    doc.saveas(dxf_path)

    # Platform with start=475.0, end=1025.0 (length 550m centered on 1500m track)
    plat_cfg = PlatformConfig(
        source_dxf=dxf_path,
        output_dxf=dxf_path,
        track_layer="MAIN_LINE",
        platform_length=550.0,
        center_on_track=True,
        output_layer="PLATFORM_1",
    )
    plat_req = PlatformRequest(track_layer="MAIN_LINE", config=plat_cfg)

    # ROB 1 at platform start - 50m = 475 - 50 = 425m
    rob1 = ROBConfig(
        id="ROB_START",
        platform="PLATFORM_1",
        reference_end="START",
        offset=50.0,
        width=10.0,
        output_layer="ROB_START",
    )

    # ROB 2 at platform end + 75m = 1025 + 75 = 1100m
    rob2 = ROBConfig(
        id="ROB_END",
        platform="PLATFORM_1",
        reference_end="END",
        offset=75.0,
        width=15.0,
        output_layer="ROB_END",
    )

    esp_config = ESPConfig(
        source_path=dxf_path,
        output_dxf=dxf_path,
        track_source_layer="MAIN_LINE",
        platforms=[plat_req],
        robs=[rob1, rob2],
    )

    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1500.0, 0.0)],
        "LOOP_1": [(0.0, 5.3), (1500.0, 5.3)],
    }

    step = RobStep()
    step.config = esp_config
    step._generate_robs(tracks)

    res_doc = ezdxf.readfile(dxf_path)
    msp = res_doc.modelspace()

    # Verify SGFD blocks created in the DXF
    assert "SGFD" in res_doc.blocks
    assert len(list(res_doc.blocks["SGFD"])) == 6
    assert "SGFD_2" in res_doc.blocks
    assert len(list(res_doc.blocks["SGFD_2"])) == 6

    # Verify INSERT block references in modelspace
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    assert len(inserts) == 2

    # ROB 1 at platform start - 50m = 475 - 50 = 425m
    assert inserts[0].dxf.name == "SGFD"
    assert inserts[0].dxf.insert[0] == pytest.approx(425.0)

    # ROB 2 at platform end + 75m = 1025 + 75 = 1100m
    assert inserts[1].dxf.name == "SGFD_2"
    assert inserts[1].dxf.insert[0] == pytest.approx(1100.0)

    # Verify width dimension entities created
    dims = [e for e in msp if e.dxftype() == "DIMENSION"]
    assert len(dims) == 2

    # Verify duplicate BR.CH- chainage labels on bridge deck are omitted by default
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    assert not any("BR.CH-" in t for t in texts)

    # Verify dashed centerlines are omitted by default (no dotted centerline inside bridge)
    centers = [e for e in msp if e.dxftype() == "LINE" and "-CENTER" in e.dxf.layer]
    assert len(centers) == 0


def test_rob_with_station_relative_chainage(tmp_path):
    """Verify that when a station exists, ROB chainage is measured from station center."""
    dxf_path = str(tmp_path / "test_esp_stn.dxf")
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.new("MAIN_LINE")
    # Station building at center (750m) of platform (475m to 1025m)
    doc.layers.new("STATION-BUILDING")
    msp.add_lwpolyline(
        [(730.0, 5.0), (770.0, 5.0), (770.0, 15.0), (730.0, 15.0)],
        close=True,
        dxfattribs={"layer": "STATION-BUILDING"},
    )
    doc.saveas(dxf_path)

    plat_cfg = PlatformConfig(
        source_dxf=dxf_path,
        output_dxf=dxf_path,
        track_layer="MAIN_LINE",
        platform_length=550.0,
        center_on_track=True,
        output_layer="PLATFORM_1",
    )
    plat_req = PlatformRequest(track_layer="MAIN_LINE", config=plat_cfg)

    rob1 = ROBConfig(
        id="ROB_LEFT",
        platform="PLATFORM_1",
        reference_end="START",
        offset=50.0,
        width=10.0,
        output_layer="ROB_1",
    )
    rob2 = ROBConfig(
        id="ROB_RIGHT",
        platform="PLATFORM_1",
        reference_end="END",
        offset=75.0,
        width=15.0,
        output_layer="ROB_2",
    )

    esp_config = ESPConfig(
        source_path=dxf_path,
        output_dxf=dxf_path,
        track_source_layer="MAIN_LINE",
        platforms=[plat_req],
        robs=[rob1, rob2],
    )

    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1500.0, 0.0)],
    }

    step = RobStep()
    step.config = esp_config
    step._generate_robs(tracks)

    res_doc = ezdxf.readfile(dxf_path)
    msp = res_doc.modelspace()

    # Station center is at 750.0m
    # ROB 1 is at 475 - 50 = 425.0m -> relative: 425 - 750 = -325.00m
    # ROB 2 is at 1025 + 75 = 1100.0m -> relative: 1100 - 750 = +350.00m
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    assert not any("BR.CH-" in t for t in texts)

    # Also test station chainage labels pass
    from pipeline.steps.chainage import ChainageStep
    ch_step = ChainageStep()
    ch_step.config = esp_config
    ch_step._generate_station_chainage_labels(tracks)

    res_doc2 = ezdxf.readfile(dxf_path)
    chainage_texts = [e.dxf.text for e in res_doc2.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == "CHAINAGE"]
    assert any("BR AT CH -325.00 m" in t for t in chainage_texts)
    assert any("BR AT CH +350.00 m" in t for t in chainage_texts)

    # Verify chainage dotted leader line starts outside/from the top of bridge (y > 10.0)
    ch_lines = [e for e in res_doc2.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == "CHAINAGE"]
    assert len(ch_lines) >= 2
    for line in ch_lines:
        assert line.dxf.start.y > 10.0, f"Leader line started inside bridge at y={line.dxf.start.y}"


