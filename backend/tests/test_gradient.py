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

    # Yard chainages in meters (e.g. gradient 400, station 350 -> +50 m)
    assert compute_gradient_offset("400", "350") == pytest.approx(50.0)
    assert compute_gradient_offset("400.000", "350.000") == pytest.approx(50.0)
    assert compute_gradient_offset("400.000", "375.000") == pytest.approx(25.0)
    assert compute_gradient_offset("300", "350") == pytest.approx(-50.0)


def test_format_chainage_display():
    assert format_chainage_display("125.400") == "CH: 125.400 KM"
    assert format_chainage_display("125.4") == "CH: 125.400 KM"
    assert format_chainage_display("125+400") == "CH: 125.400 KM"
    assert format_chainage_display("450 M") == "CH: 450.00 M"


def _get_grad_lines(doc):
    lines = []
    for e in doc.modelspace():
        if e.dxf.layer == "GRADIENT":
            if e.dxftype() == "LINE":
                lines.append(e)
            elif e.dxftype() == "INSERT":
                lines.extend([sub for sub in e.virtual_entities() if sub.dxftype() == "LINE"])
    return lines


def _get_grad_texts(doc):
    texts = []
    for e in doc.modelspace():
        if e.dxf.layer == "GRADIENT":
            if e.dxftype() == "TEXT":
                texts.append(e)
            elif e.dxftype() == "INSERT":
                texts.extend([sub for sub in e.virtual_entities() if sub.dxftype() == "TEXT"])
    return texts


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
    # Verify block reference is inserted
    block_refs = [e for e in doc.modelspace() if e.dxftype() == "INSERT" and e.dxf.layer == "GRADIENT"]
    assert len(block_refs) == 1, "Gradient should be created as a block reference (INSERT entity)"
    assert block_refs[0].dxf.name.startswith("GRADIENT_")

    grad_lines = _get_grad_lines(doc)
    assert grad_lines, "GRADIENT lines should be present"

    # Station building is centered at 1000m along the 2000m track
    # No stem should connect all the way down to track (y = 0.0)
    assert not any(line.dxf.start[1] == pytest.approx(0.0, abs=0.5) for line in grad_lines)

    # Slanted/straight segments (left and right) and vertical center marker
    segments = [l for l in grad_lines if abs(l.dxf.start[0] - l.dxf.end[0]) > 3.0]
    assert len(segments) == 2, "Both left and right segments should be drawn"
    v_marker = next(l for l in grad_lines if abs(l.dxf.start[0] - l.dxf.end[0]) < 1e-3)

    # The small vertical line is at the CENTER junction (target chainage x = 1000.0)
    assert v_marker.dxf.start[0] == pytest.approx(1000.0, abs=0.1)
    # Both segments connect at the center vertical marker
    assert any(s.dxf.end[0] == pytest.approx(1000.0, abs=0.1) for s in segments)
    assert any(s.dxf.start[0] == pytest.approx(1000.0, abs=0.1) for s in segments)

    # Verify NO dotted chainage labels (GRADIENT AT CH ...) are created on CHAINAGE layer
    ch_texts = [
        e.dxf.text for e in doc.modelspace() if e.dxf.layer == "CHAINAGE" and e.dxftype() == "TEXT"
    ]
    assert not any("GRADIENT AT CH" in t for t in ch_texts)


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
    grad_lines = _get_grad_lines(doc)
    assert grad_lines
    assert not any(line.dxf.start[1] == pytest.approx(0.0, abs=0.5) for line in grad_lines)
    # Station at 1000m, gradient at +400m -> x = 1400m
    starts = [line.dxf.start[0] for line in grad_lines]
    assert any(x == pytest.approx(1400.0, abs=1.0) for x in starts)


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
    grad_lines = _get_grad_lines(doc)
    assert grad_lines
    assert not any(line.dxf.start[1] == pytest.approx(0.0, abs=0.5) for line in grad_lines)
    # Station at 1000m, gradient at -300m -> x = 700m
    starts = [line.dxf.start[0] for line in grad_lines]
    assert any(x == pytest.approx(700.0, abs=1.0) for x in starts)


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
    grad_lines = _get_grad_lines(doc)
    assert grad_lines

    # Gradient annotation positioned along transverse normal from track point past station center
    starts = [l.dxf.start for l in grad_lines]
    assert any(pt[0] > 1000.0 and pt[1] > 100.0 for pt in starts)


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
    texts = [e.dxf.text for e in _get_grad_texts(doc)]
    assert texts
    combined = "\n".join(texts)

    assert "684" in combined
    assert "CH: 125.40" in combined
    assert "RL: 102.45" in combined
    assert "DN" in combined


def test_gradient_two_sided_profiles(tmp_path):
    """Verify two-sided gradient: left=STRAIGHT (202), right=RISE (1278)."""
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                chainage="125.000",
                left_gradient_value="202",
                left_direction="STRAIGHT",
                right_gradient_value="1278",
                right_direction="RISE",
                rl="97.91",
            )
        ],
        station_chainage="125",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    grad_lines = _get_grad_lines(doc)
    texts = [e.dxf.text for e in _get_grad_texts(doc)]
    combined = "\n".join(texts)

    # Values for left and right
    assert "202" in combined
    assert "1278" in combined
    assert "RL: 97.91" in combined

    # Check that left segment is horizontal (dy = 0) and right segment has upward slope (dy > 0)
    segments = [l for l in grad_lines if abs(l.dxf.start[0] - l.dxf.end[0]) > 3.0]
    assert len(segments) == 2

    # Left segment: from x ≈ 995 to x ≈ 1000
    left_seg = next(s for s in segments if min(s.dxf.start[0], s.dxf.end[0]) < 999.0)
    assert abs(left_seg.dxf.start[1] - left_seg.dxf.end[1]) == pytest.approx(0.0, abs=0.01), "Left segment must be STRAIGHT (horizontal)"

    # Right segment: from x ≈ 1000 to x ≈ 1005 (RISE -> higher than center)
    right_seg = next(s for s in segments if max(s.dxf.start[0], s.dxf.end[0]) > 1001.0)
    p_center_y = min(left_seg.dxf.start[1], left_seg.dxf.end[1])
    p_right_outer = max(right_seg.dxf.start[1], right_seg.dxf.end[1])
    assert p_right_outer > p_center_y, "Right RISE must go upward from center"


def test_gradient_left_rise_and_down_from_center(tmp_path):
    """Verify RISE goes upward from center and DOWN goes downward from center on both sides."""
    # Test Left RISE + Right DOWN: left outer > center, right outer < center
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                chainage="125.000",
                left_gradient_value="525",
                left_direction="RISE",
                right_gradient_value="260",
                right_direction="DOWN",
            )
        ],
        station_chainage="125",
    )
    gen.run()

    doc = ezdxf.readfile(str(out))
    grad_lines = _get_grad_lines(doc)
    segments = [l for l in grad_lines if abs(l.dxf.start[0] - l.dxf.end[0]) > 3.0]
    v_marker = next(l for l in grad_lines if abs(l.dxf.start[0] - l.dxf.end[0]) < 1e-3)
    p_center_y = max(v_marker.dxf.start[1], v_marker.dxf.end[1])

    left_seg = next(s for s in segments if min(s.dxf.start[0], s.dxf.end[0]) < 999.0)
    right_seg = next(s for s in segments if max(s.dxf.start[0], s.dxf.end[0]) > 1001.0)

    # Left RISE: left outer endpoint goes UPWARD from center (+y)
    left_outer_y = left_seg.dxf.start[1] if left_seg.dxf.start[0] < 999.0 else left_seg.dxf.end[1]
    assert left_outer_y > p_center_y, "Left RISE must go upward from center"

    # Right DOWN: right outer endpoint goes DOWNWARD from center (-y)
    right_outer_y = right_seg.dxf.start[1] if right_seg.dxf.start[0] > 1001.0 else right_seg.dxf.end[1]
    assert right_outer_y < p_center_y, "Right DOWN must go downward from center"


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


def test_gradient_km_and_m_loading_and_pipeline(tmp_path):
    """Verify gradients specified with km and m are loaded and processed accurately."""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        """{
        "source_path": "source.dxf",
        "output_dxf": "out.dxf",
        "track_source_layer": "MAIN_TRACK",
        "gradients": [
            {
                "track": "MAIN_LINE",
                "km": 70,
                "m": 400,
                "gradient_value": "260",
                "direction": "RISE",
                "rl": "102.45"
            }
        ]
    }""",
        encoding="utf-8",
    )
    loaded = load_config_from_json(str(cfg_file))
    assert len(loaded.gradients) == 1
    g = loaded.gradients[0]
    assert g.chainage == "70+400"
    assert g.km == 70
    assert g.m == 400

    # Pipeline execution with km & m
    gen, out = _make_sample_pipeline(
        tmp_path,
        gradients=[
            GradientRequest(
                track_designation="MAIN_LINE",
                km=125,
                m=400,
                chainage="125+400",
                left_gradient_value="525",
                left_direction="STRAIGHT",
                right_gradient_value="260",
                right_direction="RISE",
            )
        ],
        station_chainage="125",
    )
    gen.run()
    doc = ezdxf.readfile(str(out))
    labels = _get_grad_texts(doc)
    assert any("CH:" in l.dxf.text for l in labels)
