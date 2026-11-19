"""Station-relative chainage labels: datum 0.000 at station building centre."""

from __future__ import annotations

import math
from types import SimpleNamespace

import ezdxf
import pytest
from app.features.drawing_generation.domain.geometry.chainage import (
    CHAINAGE_LAYER,
    CHAINAGE_PARALLEL_TOL_M,
    CHAINAGE_TEXT_SIDE_M,
    StationDatum,
    draw_chainage_annotation,
    format_chainage_label,
    format_relative_chainage,
    relative_for_point_on_track,
)
from app.features.drawing_generation.pipeline.steps.chainage import ChainageStep


def _straight(length=1000.0, y=0.0, step=10.0):
    pts = []
    x = 0.0
    while x <= length + 1e-9:
        pts.append((float(x), float(y)))
        x += step
    return pts


def test_format_relative_chainage():
    assert format_relative_chainage(358.21) == "+358.21 m"
    assert format_relative_chainage(-120.5) == "-120.50 m"
    assert format_relative_chainage(0.0) == "+0.00 m"
    assert format_relative_chainage(0.0004) == "+0.00 m"
    assert format_relative_chainage(-0.0004) == "+0.00 m"
    assert format_relative_chainage(1250.0) == "+1250.00 m"
    assert format_relative_chainage(-1250.0) == "-1250.00 m"
    assert format_relative_chainage(250.42) == "+250.42 m"
    assert format_relative_chainage(-245.43) == "-245.43 m"


def test_format_chainage_label():
    assert format_chainage_label("SRJ", 356.21) == "SRJ AT CH +356.21 m"
    assert format_chainage_label("FM", -120.5) == "FM AT CH -120.50 m"
    assert format_chainage_label("DE", 0.0) == "DE AT CH +0.00 m"


def test_station_datum_is_projection_not_hardcoded():
    tracks = {"MAIN_LINE": _straight()}
    datum = StationDatum((500.0, 8.0), tracks)
    assert datum.station_chainage_on("MAIN_LINE") == pytest.approx(500.0)
    assert datum.relative_for_main(858.21) == pytest.approx(358.21)
    assert datum.relative_for_main(379.5) == pytest.approx(-120.5)
    assert datum.relative_for_main(500.0) == pytest.approx(0.0)


def test_relative_uses_distance_along_alignment():
    pts = [(0.0, 0.0), (500.0, 0.0), (500.0, 500.0)]
    tracks = {"MAIN_LINE": pts}
    datum = StationDatum((0.0, 0.0), tracks)
    assert datum.station_chainage_on("MAIN_LINE") == pytest.approx(0.0)
    rel = relative_for_point_on_track(tracks, datum, "MAIN_LINE", (500.0, 500.0))
    assert rel == pytest.approx(1000.0)
    assert rel != pytest.approx(((500.0 ** 2 + 500.0 ** 2) ** 0.5))


def test_draw_chainage_annotation_leader_and_vertical_text():
    doc = ezdxf.new()
    n = draw_chainage_annotation(doc, (100.0, 0.0), (1.0, 0.0), 356.21, "SRJ")
    assert n == 1
    assert CHAINAGE_LAYER in doc.layers
    msp = doc.modelspace()
    lines = [e for e in msp if e.dxftype() == "LINE"
             and e.dxf.layer == CHAINAGE_LAYER]
    texts = [e for e in msp if e.dxftype() == "TEXT"
             and e.dxf.layer == CHAINAGE_LAYER]
    assert len(lines) == 1
    assert len(texts) == 1
    s, e = lines[0].dxf.start, lines[0].dxf.end
    assert (float(s.x), float(s.y)) == pytest.approx((100.0, 0.0))
    assert (float(e.x), float(e.y)) == pytest.approx((100.0, 20.0))
    assert lines[0].dxf.linetype == "DASHED"
    assert doc.layers.get(CHAINAGE_LAYER).dxf.linetype == "DASHED"
    assert texts[0].dxf.text == "SRJ AT CH +356.21 m"
    assert float(texts[0].dxf.rotation) == pytest.approx(90.0)
    assert texts[0].dxf.halign == 2
    assert texts[0].dxf.valign == 0
    ins = texts[0].dxf.insert
    assert float(ins[1]) == pytest.approx(20.0)
    assert float(ins[0]) == pytest.approx(100.0 - CHAINAGE_TEXT_SIDE_M)
    assert abs(float(ins[0]) - float(e.x)) == pytest.approx(CHAINAGE_TEXT_SIDE_M)


def test_draw_chainage_annotation_negative_side():
    doc = ezdxf.new()
    draw_chainage_annotation(doc, (100.0, 0.0), (1.0, 0.0), -120.5, "FM")
    texts = [e for e in doc.modelspace() if e.dxftype() == "TEXT"]
    assert texts[0].dxf.text == "FM AT CH -120.50 m"


@pytest.mark.parametrize('degrees', [-150, -45, 0, 30, 110, 180])
@pytest.mark.parametrize('side', ['LEFT', 'RIGHT'])
def test_chainage_text_parallel_to_own_leader_with_gap(degrees, side):
    doc = ezdxf.new()
    angle = math.radians(degrees)
    tangent = (math.cos(angle), math.sin(angle))
    draw_chainage_annotation(doc, (100, 200), tangent, 42, 'SRJ', side=side)
    line = doc.modelspace().query('LINE')[0]
    text = doc.modelspace().query('TEXT')[0]
    direction = (line.dxf.end-line.dxf.start).normalize()
    rot = math.radians(text.dxf.rotation)
    assert abs(math.cos(rot)*direction.y-math.sin(rot)*direction.x) < 1e-8
    delta = text.dxf.align_point-line.dxf.end
    gap = abs(delta.x*direction.y-delta.y*direction.x)
    assert gap >= CHAINAGE_TEXT_SIDE_M-1e-8
    assert abs(delta.dot(direction)) < 1e-8


def test_parallel_markers_share_one_chainage():
    assert float(CHAINAGE_PARALLEL_TOL_M) == pytest.approx(1.0)
    assert abs(495.0 - 495.000) < float(CHAINAGE_PARALLEL_TOL_M)


def test_ramp_and_fob_end_labels():
    assert format_chainage_label("RAMP END", 256.0) == "RAMP END AT CH +256.00 m"
    assert format_chainage_label("PF END", 250.0) == "PF END AT CH +250.00 m"
    assert format_chainage_label("FOB END", 99.291) == "FOB END AT CH +99.29 m"


def test_draw_chainage_annotation_right_side():
    doc = ezdxf.new()
    n = draw_chainage_annotation(doc, (100.0, 0.0), (1.0, 0.0), 356.21, "SRJ", side="RIGHT")
    assert n == 1
    msp = doc.modelspace()
    lines = [e for e in msp if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER]
    texts = [e for e in msp if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    assert len(lines) == 1
    assert len(texts) == 1
    s, e = lines[0].dxf.start, lines[0].dxf.end
    assert (float(s.x), float(s.y)) == pytest.approx((100.0, 0.0))
    assert (float(e.x), float(e.y)) == pytest.approx((100.0, -20.0))
    assert texts[0].dxf.text == "SRJ AT CH +356.21 m"
    assert float(texts[0].dxf.rotation) == pytest.approx(90.0)
    assert texts[0].dxf.halign == 0
    assert texts[0].dxf.valign == 0
    ins = texts[0].dxf.insert
    assert float(ins[1]) == pytest.approx(-20.0)
    assert float(ins[0]) == pytest.approx(100.0 - CHAINAGE_TEXT_SIDE_M)


def test_draw_chainage_annotation_both_sides_srj_fm():
    doc = ezdxf.new()
    n = draw_chainage_annotation(
        doc, (100.0, 0.0), (1.0, 0.0), 472.0, "SRJ",
        leader_len=20.0, side="LEFT", other_side_tag="FM"
    )
    assert n == 1
    msp = doc.modelspace()
    lines = [e for e in msp if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER]
    texts = [e for e in msp if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    assert len(lines) == 1
    assert len(texts) == 2
    # Verify line is at x = 100.0
    assert float(lines[0].dxf.start.x) == pytest.approx(100.0)
    assert float(lines[0].dxf.end.x) == pytest.approx(100.0)
    # Text 1: SRJ AT CH on the LEFT of the line (< 100.0)
    srj_text = [t for t in texts if "SRJ" in t.dxf.text][0]
    assert "SRJ AT CH +472.00 m" == srj_text.dxf.text
    assert float(srj_text.dxf.insert[0]) < 100.0
    # Text 2: FM AT CH on the RIGHT of the line (> 100.0)
    fm_text = [t for t in texts if "FM" in t.dxf.text][0]
    assert "FM AT CH +472.00 m" == fm_text.dxf.text
    assert float(fm_text.dxf.insert[0]) > 100.0



def test_chainage_mixin_left_and_right_sides(tmp_path):
    class FakeGenerator(ChainageStep):
        def __init__(self, out_dxf):
            self.config = SimpleNamespace(
                output_dxf=str(out_dxf),
                loops=[
                    SimpleNamespace(name="LOOP_1", side="LEFT", first_crossover_chainage=200.0, second_crossover_chainage=800.0, extend_start_m=0.0, extend_end_m=0.0),
                    SimpleNamespace(name="LOOP_2", side="RIGHT", first_crossover_chainage=200.0, second_crossover_chainage=800.0, extend_start_m=0.0, extend_end_m=0.0),
                ],
                additional_lines=[],
                platforms=[
                    SimpleNamespace(track_layer="LOOP_1", side="LEFT", config=SimpleNamespace(output_layer="PLATFORM_1", stair_layer="STAIRS_1")),
                    SimpleNamespace(track_layer="LOOP_2", side="RIGHT", config=SimpleNamespace(output_layer="PLATFORM_2", stair_layer="STAIRS_2")),
                ],
                sidings=[],
                fobs=[],
            )
            self._crossover_results = []
            self._siding_results = []
            self._fouling_marks = []

    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.layers.new("STATION-BUILDING")
    msp.add_lwpolyline([(490.0, 10.0), (510.0, 10.0), (510.0, 20.0), (490.0, 20.0)], close=True, dxfattribs={"layer": "STATION-BUILDING"})

    doc.layers.new("PLATFORM_1")
    msp.add_lwpolyline([(300.0, 6.0), (700.0, 6.0), (700.0, 10.0), (300.0, 10.0)], close=True, dxfattribs={"layer": "PLATFORM_1"})

    doc.layers.new("PLATFORM_2")
    msp.add_lwpolyline([(300.0, -10.0), (700.0, -10.0), (700.0, -6.0), (300.0, -6.0)], close=True, dxfattribs={"layer": "PLATFORM_2"})

    dxf_path = tmp_path / "test_esp.dxf"
    doc.saveas(dxf_path)

    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)],
        "LOOP_1": [(0.0, 5.3), (1000.0, 5.3)],
        "LOOP_2": [(0.0, -5.3), (1000.0, -5.3)],
    }

    gen = FakeGenerator(dxf_path)
    gen._generate_station_chainage_labels(tracks)

    result_doc = ezdxf.readfile(dxf_path)
    rmsp = result_doc.modelspace()
    chainage_lines = [e for e in rmsp if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER]
    chainage_texts = [e for e in rmsp if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]

    assert len(chainage_lines) >= 2
    assert len(chainage_texts) >= 2

    left_lines = [l for l in chainage_lines if l.dxf.end.y > 0]
    right_lines = [l for l in chainage_lines if l.dxf.end.y < 0]
    left_texts = [t for t in chainage_texts if t.dxf.insert.y > 0]
    right_texts = [t for t in chainage_texts if t.dxf.insert.y < 0]

    assert len(left_lines) > 0, "Expected chainage leaders on the LEFT (positive Y)"
    assert len(right_lines) > 0, "Expected chainage leaders on the RIGHT (negative Y)"
    assert len(left_texts) > 0, "Expected chainage texts on the LEFT"
    assert len(right_texts) > 0, "Expected chainage texts on the RIGHT"


def test_station_flag_layer_excluded_from_chainage_outer_boundary(tmp_path):
    class FakeGenerator(ChainageStep):
        def __init__(self, out_dxf):
            self.config = SimpleNamespace(
                output_dxf=str(out_dxf),
                loops=[
                    SimpleNamespace(name="LOOP_1", side="LEFT", first_crossover_chainage=200.0, second_crossover_chainage=800.0, extend_start_m=0.0, extend_end_m=0.0),
                    SimpleNamespace(name="LOOP_2", side="RIGHT", first_crossover_chainage=200.0, second_crossover_chainage=800.0, extend_start_m=0.0, extend_end_m=0.0),
                ],
                additional_lines=[],
                platforms=[
                    SimpleNamespace(track_layer="LOOP_1", side="LEFT", config=SimpleNamespace(output_layer="PLATFORM_1", stair_layer="STAIRS_1")),
                    SimpleNamespace(track_layer="LOOP_2", side="RIGHT", config=SimpleNamespace(output_layer="PLATFORM_2", stair_layer="STAIRS_2")),
                ],
                sidings=[],
                fobs=[],
            )
            self._crossover_results = []
            self._siding_results = []
            self._fouling_marks = []

    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)],
        "LOOP_1": [(0.0, 5.3), (1000.0, 5.3)],
        "LOOP_2": [(0.0, -5.3), (1000.0, -5.3)],
    }

    doc1 = ezdxf.new()
    msp1 = doc1.modelspace()
    doc1.layers.new("STATION-BUILDING")
    msp1.add_lwpolyline([(490.0, 10.0), (510.0, 10.0), (510.0, 20.0), (490.0, 20.0)], close=True, dxfattribs={"layer": "STATION-BUILDING"})
    doc1.layers.new("PLATFORM_1")
    msp1.add_lwpolyline([(300.0, 6.0), (700.0, 6.0), (700.0, 10.0), (300.0, 10.0)], close=True, dxfattribs={"layer": "PLATFORM_1"})
    doc1.layers.new("PLATFORM_2")
    msp1.add_lwpolyline([(300.0, -10.0), (700.0, -10.0), (700.0, -6.0), (300.0, -6.0)], close=True, dxfattribs={"layer": "PLATFORM_2"})
    dxf1 = tmp_path / "test_no_flag.dxf"
    doc1.saveas(dxf1)

    gen1 = FakeGenerator(dxf1)
    gen1._generate_station_chainage_labels(tracks)

    res1 = ezdxf.readfile(dxf1)
    left1 = [e for e in res1.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.end.y > 0]
    right1 = [e for e in res1.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.end.y < 0]
    left1_y = left1[0].dxf.end.y
    right1_y = right1[0].dxf.end.y

    doc2 = ezdxf.new()
    msp2 = doc2.modelspace()
    doc2.layers.new("STATION-BUILDING")
    msp2.add_lwpolyline([(490.0, 10.0), (510.0, 10.0), (510.0, 20.0), (490.0, 20.0)], close=True, dxfattribs={"layer": "STATION-BUILDING"})
    doc2.layers.new("PLATFORM_1")
    msp2.add_lwpolyline([(300.0, 6.0), (700.0, 6.0), (700.0, 10.0), (300.0, 10.0)], close=True, dxfattribs={"layer": "PLATFORM_1"})
    doc2.layers.new("PLATFORM_2")
    msp2.add_lwpolyline([(300.0, -10.0), (700.0, -10.0), (700.0, -6.0), (300.0, -6.0)], close=True, dxfattribs={"layer": "PLATFORM_2"})
    doc2.layers.new("STATION-FLAG")
    msp2.add_line((500.0, 50.0), (500.0, 100.0), dxfattribs={"layer": "STATION-FLAG"})
    dxf2 = tmp_path / "test_with_flag.dxf"
    doc2.saveas(dxf2)

    gen2 = FakeGenerator(dxf2)
    gen2._generate_station_chainage_labels(tracks)

    res2 = ezdxf.readfile(dxf2)
    left2 = [e for e in res2.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.end.y > 0]
    right2 = [e for e in res2.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.end.y < 0]
    left2_y = left2[0].dxf.end.y
    right2_y = right2[0].dxf.end.y

    assert left1_y == pytest.approx(left2_y), f"Flag shifted left chainage from {left1_y} to {left2_y}"
    assert right1_y == pytest.approx(right2_y), f"Flag shifted right chainage from {right1_y} to {right2_y}"
