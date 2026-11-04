"""Station-relative chainage labels: datum 0.000 at station building centre."""

from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest

from common.chainage import (
    CHAINAGE_LAYER,
    CHAINAGE_PARALLEL_TOL_M,
    CHAINAGE_TEXT_SIDE_M,
    StationDatum,
    draw_chainage_annotation,
    format_chainage_label,
    format_relative_chainage,
    relative_for_point_on_track,
)
from pipeline.chainage_step import ChainageMixin


def _straight(length=1000.0, y=0.0, step=10.0):
    pts = []
    x = 0.0
    while x <= length + 1e-9:
        pts.append((float(x), float(y)))
        x += step
    return pts


def test_format_relative_chainage():
    assert format_relative_chainage(358.21) == "+ 0+358"
    assert format_relative_chainage(-120.5) == "- 0+120"
    assert format_relative_chainage(0.0) == "+ 0+000"
    assert format_relative_chainage(0.0004) == "+ 0+000"
    assert format_relative_chainage(-0.0004) == "+ 0+000"
    assert format_relative_chainage(1250.0) == "+ 1+250"
    assert format_relative_chainage(-1250.0) == "- 1+250"


def test_format_chainage_label():
    assert format_chainage_label("SRJ", 356.21) == "SRJ AT CH + 0+356"
    assert format_chainage_label("FM", -120.5) == "FM AT CH - 0+120"
    assert format_chainage_label("DE", 0.0) == "DE AT CH + 0+000"


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
    assert texts[0].dxf.text == "SRJ AT CH + 0+356"
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
    assert texts[0].dxf.text == "FM AT CH - 0+120"


def test_parallel_markers_share_one_chainage():
    assert float(CHAINAGE_PARALLEL_TOL_M) == pytest.approx(1.0)
    assert abs(495.0 - 495.000) < float(CHAINAGE_PARALLEL_TOL_M)


def test_ramp_and_fob_end_labels():
    assert format_chainage_label("RAMP END", 256.0) == "RAMP END AT CH + 0+256"
    assert format_chainage_label("PF END", 250.0) == "PF END AT CH + 0+250"
    assert format_chainage_label("FOB END", 99.291) == "FOB END AT CH + 0+099"


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
    assert texts[0].dxf.text == "SRJ AT CH + 0+356"
    assert float(texts[0].dxf.rotation) == pytest.approx(90.0)
    assert texts[0].dxf.halign == 0
    assert texts[0].dxf.valign == 0
    ins = texts[0].dxf.insert
    assert float(ins[1]) == pytest.approx(-20.0)
    assert float(ins[0]) == pytest.approx(100.0 - CHAINAGE_TEXT_SIDE_M)


def test_chainage_mixin_left_and_right_sides(tmp_path):
    class FakeGenerator(ChainageMixin):
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
    class FakeGenerator(ChainageMixin):
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


def test_alignment_interval_chainages_km_only(tmp_path):
    """When user inputs 4 for KM and nothing for M, shows CH-4 and Ch. 4000 M."""
    tracks = {"MAIN_LINE": _straight(length=350.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "interval_km.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=4,
                start_m=None,
                start_chainage="4",
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    texts = [e.dxf.text for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    
    # At start (4000m): top is CH-4 (only 4 shown), bottom is Ch. 4000 M
    assert "CH-4" in texts
    assert "Ch. 4000 M" in texts
    # At +100m: CH-4+100 and Ch. 4100 M
    assert "CH-4+100" in texts
    assert "Ch. 4100 M" in texts


def test_alignment_interval_chainages_km_and_m(tmp_path):
    """When user inputs 1 for KM and 900 for M, shows CH-1+900 and Ch. 1900 M."""
    tracks = {"MAIN_LINE": _straight(length=300.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "interval_km_m.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=1,
                start_m=900,
                start_chainage="1+900",
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    texts = [e.dxf.text for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    
    assert "CH-1+900" in texts
    assert "Ch. 1900 M" in texts
    assert "CH-2+000" in texts
    assert "Ch. 2000 M" in texts


def test_alignment_interval_chainages_hidden_when_loops_present(tmp_path):
    """When loops are configured as input, alignment interval chainages are hidden."""
    tracks = {"MAIN_LINE": _straight(length=300.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "interval_hidden.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=1,
                start_m=900,
                loops=[{"name": "LOOP_1"}],
                show_alignment_chainages=False,
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    texts = [e.dxf.text for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    assert len(texts) == 0


def test_alignment_station_markers_drawn(tmp_path):
    """Alignment station markers draw prominent perpendicular lines and labels at given chainage."""
    tracks = {"MAIN_LINE": _straight(length=1000.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "station_markers.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=2,
                start_m=0,
                start_chainage="2",
                station_markers=[
                    {"name": "DELHI JUNCTION", "km": 2, "m": 400},
                    {"name": "NEW DELHI", "km": 2, "m": 900},
                ],
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    stn_texts = [e.dxf.text for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == "STATION"]
    stn_lines = [e for e in res.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == "STATION"]
    flag_polys = [e for e in res.modelspace() if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "STATION-FLAG"]
    flag_lines = [e for e in res.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == "STATION-FLAG"]

    assert "STATION: DELHI JUNCTION" in stn_texts
    assert "CH: 2+400" in stn_texts
    assert "STATION: NEW DELHI" in stn_texts
    assert "CH: 2+900" in stn_texts
    # 2 station perpendicular lines on STATION layer
    assert len(stn_lines) == 2
    # 2 station waving flags on STATION-FLAG layer with polylines and hatch lines
    assert len(flag_polys) == 2
    assert len(flag_lines) > 20


def test_alignment_station_markers_crossbar_when_flag_disabled(tmp_path):
    """When station flag is explicitly disabled, draws terminal crossbar instead."""
    tracks = {"MAIN_LINE": _straight(length=1000.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "station_crossbar.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=2,
                station_markers=[
                    {"name": "STATION NO FLAG", "km": 2, "m": 500, "show_flag": False},
                ],
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    stn_lines = [e for e in res.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == "STATION"]
    flag_polys = [e for e in res.modelspace() if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "STATION-FLAG"]

    # 1 perpendicular line + 1 top crossbar line = 2 lines on STATION
    assert len(stn_lines) == 2
    # No flags on STATION-FLAG layer
    assert len(flag_polys) == 0


def test_alignment_station_markers_hidden_when_loops_present(tmp_path):
    """Station markers along alignment are hidden when loops or other features exist."""
    tracks = {"MAIN_LINE": _straight(length=1000.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "station_markers_hidden.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=2,
                loops=[{"name": "LOOP_1"}],
                station_markers=[{"name": "DELHI", "km": 2, "m": 400}],
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    stn_texts = [e.dxf.text for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == "STATION"]
    assert len(stn_texts) == 0


def test_station_marker_separates_left_and_right_and_omits_interval_collision(tmp_path):
    """Station marker places name on left and chainage on right, and omits colliding interval tick."""
    tracks = {"MAIN_LINE": _straight(length=1000.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "station_separation.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=5,
                start_m=0,
                start_chainage="5",
                station_markers=[
                    {"name": "STATION 1", "km": 5, "m": 200},
                ],
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    interval_texts = [e for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    interval_str = [e.dxf.text for e in interval_texts]

    # Interval tick at 200m (CH-5+200) was omitted so it doesn't collide with the station at 200m
    assert "CH-5+200" not in interval_str
    # Adjacent interval ticks exist
    assert "CH-5+100" in interval_str
    assert "CH-5+300" in interval_str

    # Station texts are on layer STATION
    stn_entities = [e for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == "STATION"]
    stn_name_e = next(e for e in stn_entities if "STATION: STATION 1" in e.dxf.text)
    stn_ch_e = next(e for e in stn_entities if "CH: 5+200" in e.dxf.text)

    # Station name is to the LEFT of the station line (x < 200)
    assert stn_name_e.dxf.insert[0] < 200.0
    # Station chainage is to the RIGHT of the station line (x > 200)
    assert stn_ch_e.dxf.insert[0] > 200.0
    # Horizontal separation between name and chainage is at least 2.5m
    assert abs(stn_ch_e.dxf.insert[0] - stn_name_e.dxf.insert[0]) >= 2.5


def test_alignment_interval_chainages_positive_slope_rotation_and_gap(tmp_path):
    """When track slope has norm_deg > 90 (e.g. 95 deg), text rotation does not flip upside down.

    Top text (CH-...) and bottom text (Ch. ... M) both maintain upwards orientation and have
    clean gap from the track line without overlapping it.
    """
    # Track with slight positive slope (e.g. dy/dx = 8.7 / 100 => norm_deg ~ 95 deg)
    tracks = {"MAIN_LINE": [(0.0, 0.0), (100.0, 8.7), (200.0, 17.4)]}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "interval_slope.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=9,
                start_m=600,
                start_chainage="9+600",
            )

    gen = Gen(dxf_path)
    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    texts = [e for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER]
    assert len(texts) > 0

    for t in texts:
        # Rotation must be positive (in [0, 180)), pointing upwards, not flipped negative
        assert 0.0 <= t.dxf.rotation < 180.0, f"Text {t.dxf.text} has flipped rotation {t.dxf.rotation}"

    # Verify CH-9+600 top text is safely above the track and does not cross y=0
    top_t = next(t for t in texts if t.dxf.text == "CH-9+600")
    assert top_t.dxf.insert[1] > 6.0, f"Top text {top_t.dxf.text} insert y={top_t.dxf.insert[1]} too close to track"

    # Verify Ch. 9600 M bottom text is safely below the track
    bot_t = next(t for t in texts if t.dxf.text == "Ch. 9600 M")
    assert bot_t.dxf.insert[1] < 0.0, f"Bottom text {bot_t.dxf.text} insert y={bot_t.dxf.insert[1]} above track"


def test_alignment_interval_chainages_negative_start_chainage_progression(tmp_path):
    """When start chainage is negative (e.g. KM -4), interval ticks progress towards positive:
    - d = 0m: CH--4 (or CH--4+000) and Ch. -4000 M
    - d = 100m: CH--3+900 and Ch. -3900 M
    - d = 1000m: CH--3 and Ch. -3000 M
    - d = 1500m: CH--2+500 and Ch. -2500 M
    """
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1500.0, 0.0)]}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "interval_negative.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageMixin):
        def __init__(self, p):
            self.config = SimpleNamespace(
                output_dxf=str(p),
                start_km=-4,
                start_m="",
                start_chainage="-4",
                station_markers=[
                    {"name": "STN_NEG", "km": -3, "m": 900},
                ],
            )

    gen = Gen(dxf_path)
    # Test station marker parsing
    parsed = gen._parse_alignment_station_markers(tracks["MAIN_LINE"], -4000.0, 1500.0)
    assert len(parsed) == 1
    assert parsed[0]["d"] == pytest.approx(100.0)
    assert parsed[0]["ch_disp"] == "-3+900"

    gen._generate_alignment_interval_chainages(tracks)

    res = ezdxf.readfile(dxf_path)
    texts = [e.dxf.text for e in res.modelspace() if e.dxftype() == "TEXT"]

    # Verify start tick at d=0
    assert "CH--4" in texts
    assert "Ch. -4000 M" in texts

    # Verify tick at d=200 (-3800m)
    assert "CH--3+800" in texts
    assert "Ch. -3800 M" in texts

    # Verify tick at d=1000 (-3000m)
    assert "CH--3" in texts
    assert "Ch. -3000 M" in texts





