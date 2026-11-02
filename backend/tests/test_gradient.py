"""Tests for Gradient Annotation feature."""

import math
import pytest
import ezdxf

from config.loader import (
    ESPConfig,
    GradientRequest,
    PlatformRequest,
    StationRequest,
    load_config_from_json,
)
from pipeline.orchestrator import ESPGenerator
from pipeline.steps.gradient import (
    compute_gradient_offset,
    format_chainage_display,
    parse_chainage_val,
)
from platform_gen.config import PlatformConfig


def test_parse_chainage_val():
    num, unit = parse_chainage_val("125.400")
    assert num == pytest.approx(125.4)
    assert unit is None

    num, unit = parse_chainage_val("125.400 KM")
    assert num == pytest.approx(125.4)
    assert unit == "KM"

    num, unit = parse_chainage_val("CH: 125.400 KM")
    assert num == pytest.approx(125.4)
    assert unit == "KM"

    num, unit = parse_chainage_val("KM: 125.400")
    assert num == pytest.approx(125.4)
    assert unit is None

    num, unit = parse_chainage_val("125+400")
    assert num == pytest.approx(125400.0)
    assert unit == "M"

    num, unit = parse_chainage_val("500 M")
    assert num == pytest.approx(500.0)
    assert unit == "M"

    with pytest.raises(ValueError):
        parse_chainage_val("")


def test_compute_gradient_offset():
    # Equal chainages
    assert compute_gradient_offset("125.000", "125.000") == pytest.approx(0.0)
    assert compute_gradient_offset("125", "125") == pytest.approx(0.0)

    # Greater chainage (ahead of station center)
    assert compute_gradient_offset("125.400", "125.000") == pytest.approx(400.0)
    assert compute_gradient_offset("125.400 KM", "125 KM") == pytest.approx(400.0)

    # Lesser chainage (behind station center)
    assert compute_gradient_offset("124.700", "125.000") == pytest.approx(-300.0)
    assert compute_gradient_offset("124.700 KM", "125.000 KM") == pytest.approx(-300.0)

    # Station center 0, gradient in meters
    assert compute_gradient_offset("350 M", "0") == pytest.approx(350.0)


def test_format_chainage_display():
    assert format_chainage_display("125.400") == "CH: 125.400 KM"
    assert format_chainage_display("125.4") == "CH: 125.400 KM"
    assert format_chainage_display("125+400") == "CH: 125.400 KM"
    assert format_chainage_display("450 M") == "CH: 450.00 M"


def _make_sample_pipeline(
    tmp_path,
    gradients: list[GradientRequest],
    track_coords=((0.0, 0.0), (2000.0, 0.0)),
    station_chainage="125",
):
    src = tmp_path / "src.dxf"
    out = tmp_path / "out.dxf"
    doc = ezdxf.new()
    if len(track_coords) == 2:
        doc.modelspace().add_line(
            track_coords[0], track_coords[1], dxfattribs={"layer": "MAIN_TRACK"}
        )
    else:
        doc.modelspace().add_lwpolyline(
            list(track_coords), dxfattribs={"layer": "MAIN_TRACK"}
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
    stations = []
    if station_chainage is not None:
        stations.append(
            StationRequest(
                platform_layer="PLATFORM_1",
                building_length=40.0,
                building_width=10.0,
                platform_side="LEFT",
                building_name="STATION BUILDING",
                station_chainage=station_chainage,
            )
        )

    return ESPGenerator(
        ESPConfig(
            source_path=str(src),
            output_dxf=str(out),
            track_source_layer="MAIN_TRACK",
            loops=[],
            additional_lines=[],
            platforms=[PlatformRequest(track_layer="MAIN_LINE", config=pcfg)],
            stations=stations,
            crossovers=[],
            main_directions={"MAIN_LINE": "UP"},
            gradients=gradients,
        )
    ), out


def test_gradient_at_station_center(tmp_path):
    """Gradient chainage equal to station center chainage (offset = 0)."""
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                chainage="125.000",
                gradient_value="1 in 684",
                direction="UP",
                rl="102.45",
            )
        ],
        station_chainage="125",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    grad_lines = [
        e for e in doc.modelspace() if e.dxf.layer == "GRADIENT" and e.dxftype() == "LINE"
    ]
    assert grad_lines, "GRADIENT lines should be present"

    # Station building is centered at 1000m along the 2000m track
    # Connection point on track should be at x = 1000.0, y = 0.0
    stems = [
        line
        for line in grad_lines
        if line.dxf.start[1] == pytest.approx(0.0, abs=0.5)
        and line.dxf.end[1] > 0.0
    ]
    assert stems, "Connecting stem from track should be present"
    stem = stems[0]
    assert stem.dxf.start[0] == pytest.approx(1000.0, abs=1.0)


def test_gradient_greater_than_station_center(tmp_path):
    """Gradient chainage greater than station center chainage (+400m)."""
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="UP LINE",
                chainage="125.400",
                gradient_value="1 in 400",
                direction="DOWN",
                rl="105.50",
            )
        ],
        station_chainage="125",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    grad_lines = [
        e for e in doc.modelspace() if e.dxf.layer == "GRADIENT" and e.dxftype() == "LINE"
    ]
    stems = [
        line
        for line in grad_lines
        if line.dxf.start[1] == pytest.approx(0.0, abs=0.5)
        and line.dxf.end[1] > 0.0
    ]
    assert stems
    # Station at 1000m, gradient at +400m -> x = 1400m
    assert stems[0].dxf.start[0] == pytest.approx(1400.0, abs=1.0)


def test_gradient_less_than_station_center(tmp_path):
    """Gradient chainage less than station center chainage (-300m)."""
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                chainage="124.700",
                gradient_value="1 in 500",
                direction="UP",
                rl="99.20",
            )
        ],
        station_chainage="125",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    grad_lines = [
        e for e in doc.modelspace() if e.dxf.layer == "GRADIENT" and e.dxftype() == "LINE"
    ]
    stems = [
        line
        for line in grad_lines
        if line.dxf.start[1] == pytest.approx(0.0, abs=0.5)
        and line.dxf.end[1] > 0.0
    ]
    assert stems
    # Station at 1000m, gradient at -300m -> x = 700m
    assert stems[0].dxf.start[0] == pytest.approx(700.0, abs=1.0)


def test_gradient_on_curved_alignment(tmp_path):
    """Gradient annotation correctly follows curved railway track geometry."""
    # Polyline curving upwards
    curve_points = [
        (0.0, 0.0),
        (500.0, 0.0),
        (1000.0, 100.0),
        (1500.0, 300.0),
        (2000.0, 600.0),
    ]
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                chainage="125.200",
                gradient_value="1 in 684",
                direction="DOWN",
            )
        ],
        track_coords=curve_points,
        station_chainage="125.000",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    grad_lines = [
        e for e in doc.modelspace() if e.dxf.layer == "GRADIENT" and e.dxftype() == "LINE"
    ]
    assert grad_lines

    # Find the stem line connecting track to horizontal bar
    # Its start should be on the curved track (y > 0.0 since it's past station center)
    vertical_stems = [
        l for l in grad_lines if abs(l.dxf.start[0] - l.dxf.end[0]) < 1e-3 and l.dxf.end[1] > l.dxf.start[1]
    ]
    assert vertical_stems
    track_pt = (vertical_stems[0].dxf.start[0], vertical_stems[0].dxf.start[1])
    assert track_pt[0] > 1000.0
    assert track_pt[1] > 100.0


def test_gradient_outside_extent_raises_error(tmp_path):
    """Validation error when gradient chainage falls outside track extent."""
    gen, _ = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                chainage="128.000",  # +3000m from station center (1000m + 3000m = 4000m > 2000m)
                gradient_value="1 in 684",
                direction="UP",
            )
        ],
        station_chainage="125.000",
    )
    with pytest.raises(ValueError) as exc:
        gen.run()
    assert "falls outside" in str(exc.value)


def test_gradient_labels_in_dxf(tmp_path):
    """Verify all text labels: gradient value, direction, chainage, RL, track designation."""
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="UP LINE",
                chainage="125.400",
                gradient_value="1 in 684",
                direction="DOWN",
                rl="102.45 M",
                line_length=30.0,
                offset=15.0,
            )
        ],
        station_chainage="125",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    texts = [
        e.dxf.text for e in doc.modelspace() if e.dxf.layer == "GRADIENT" and e.dxftype() == "TEXT"
    ]
    assert texts
    combined = "\n".join(texts)

    assert "1 in 684 DOWN" in combined
    assert "CH: 125.400 KM" in combined
    assert "RL: 102.45 M" in combined
    assert "UP LINE" in combined


def test_gradient_json_loading(tmp_path):
    """Verify gradients are loaded properly from JSON config."""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        """{
        "source_path": "source.dxf",
        "output_dxf": "out.dxf",
        "track_source_layer": "MAIN_TRACK",
        "gradients": [
            {
                "track": "UP LINE",
                "chainage": "125.400",
                "gradient_value": "1 in 684",
                "direction": "DOWN",
                "rl": "102.45",
                "line_length": 25.0,
                "offset": 10.0
            }
        ]
    }""",
        encoding="utf-8",
    )
    loaded = load_config_from_json(str(cfg_file))
    assert len(loaded.gradients) == 1
    g = loaded.gradients[0]
    assert g.track_designation == "UP LINE"
    assert g.chainage == "125.400"
    assert g.gradient_value == "1 in 684"
    assert g.direction == "DOWN"
    assert g.rl == "102.45"
    assert g.line_length == 25.0
    assert g.offset == 10.0
