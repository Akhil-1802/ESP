"""Tests for Gradient Annotation feature."""

import math

import ezdxf
import pytest
from app.features.drawing_generation.config import (
    GradientRequest,
    load_config_from_json,
)

from app.features.drawing_generation.formats.dxf.final_plan import align_final_plan

from .gradient_fixture import _get_grad_lines, _get_grad_texts, _make_sample_pipeline


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


@pytest.mark.parametrize(("value", "station"), [("12+850", "12+750"), ("12850", None)])
def test_absolute_gradient_on_nonzero_datum(tmp_path, value, station):
    gen, out = _make_sample_pipeline(
        tmp_path, [GradientRequest(absolute_chainage=value, right_gradient_value="260")],
        station_chainage=station,
    )
    gen.config.start_km, gen.config.start_m = 12, 250
    gen.run()
    doc = ezdxf.readfile(out)
    marker, = doc.modelspace().query('INSERT[layer=="GRADIENT"]')
    assert marker.dxf.insert.x == pytest.approx(600)
    assert "CH: 12+850" in [t.dxf.text for t in _get_grad_texts(doc)]


def test_absolute_gradient_rejects_outside_main(tmp_path):
    gen, _ = _make_sample_pipeline(tmp_path, [GradientRequest(absolute_chainage="11+999")])
    gen.config.start_km = 12
    with pytest.raises(ValueError, match="outside MAIN"):
        gen.run()


def test_final_gradient_text_follows_slopes_and_stem(tmp_path):
    gradient = GradientRequest(
        absolute_chainage="0+600", left_gradient_value="120", left_direction="RISE",
        right_gradient_value="65", right_direction="DOWN", rl="97.53",
    )
    gen, out = _make_sample_pipeline(
        tmp_path, [gradient], track_coords=((0, 0), (2000, 400)), station_chainage=None,
    )
    gen.run()
    assert abs(align_final_plan(str(out))) > 0.1
    doc = ezdxf.readfile(out)
    left, right, stem = _get_grad_lines(doc)
    labels = {text.dxf.text: text for text in _get_grad_texts(doc)}
    for caption, line in [('120', left), ('65', right), ('CH: 0+600', stem),
                          ('RL: 97.53m', stem), ('UP LINE', stem)]:
        direction = line.dxf.end - line.dxf.start
        rotation = math.radians(labels[caption].dxf.rotation)
        assert math.sin(rotation - direction.angle) == pytest.approx(0, abs=1e-8)
