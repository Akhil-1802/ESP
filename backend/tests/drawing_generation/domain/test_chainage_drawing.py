"""Station-relative chainage labels: datum 0.000 at station building centre."""

from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest
from app.features.drawing_generation.domain.geometry.chainage import CHAINAGE_LAYER
from app.features.drawing_generation.pipeline.steps.chainage import ChainageStep


def _straight(length=1000.0, y=0.0, step=10.0):
    pts = []
    x = 0.0
    while x <= length + 1e-9:
        pts.append((float(x), float(y)))
        x += step
    return pts


from .test_chainage import _straight


def test_alignment_interval_chainages_km_only(tmp_path):
    """When user inputs 4 for KM and nothing for M, shows CH-4 and Ch. 4000 M."""
    tracks = {"MAIN_LINE": _straight(length=350.0)}
    doc = ezdxf.new()
    doc.layers.new("MAIN_TRACK")
    doc.modelspace().add_lwpolyline(tracks["MAIN_LINE"], dxfattribs={"layer": "MAIN_TRACK"})
    dxf_path = tmp_path / "interval_km.dxf"
    doc.saveas(dxf_path)

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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

    class Gen(ChainageStep):
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


def test_chainage_leaders_capped_at_station_flag_axis(tmp_path):
    """Verify that chainage leader lines and labels do not extend beyond the station flag axis."""
    class FakeGenerator(ChainageStep):
        def __init__(self, out_dxf):
            self.config = SimpleNamespace(
                output_dxf=str(out_dxf),
                loops=[
                    SimpleNamespace(name="LOOP_1", side="LEFT", first_crossover_chainage=200.0, second_crossover_chainage=800.0, extend_start_m=0.0, extend_end_m=0.0),
                ],
                additional_lines=[],
                platforms=[
                    SimpleNamespace(track_layer="LOOP_1", side="LEFT", config=SimpleNamespace(output_layer="PLATFORM_1", stair_layer="STAIRS_1")),
                ],
                sidings=[],
                fobs=[],
            )
            self._crossover_results = []
            self._siding_results = []
            self._fouling_marks = []

    # Track with far-extending geometry 5km away
    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (500.0, 0.0), (5000.0, 1000.0)],
        "LOOP_1": [(0.0, 5.3), (1000.0, 5.3)],
    }

    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.layers.new("STATION-BUILDING")
    # Station at (500, 10), so station datum center is (500, 10), center_proj = 10.0
    msp.add_lwpolyline([(490.0, 10.0), (510.0, 10.0), (510.0, 20.0), (490.0, 20.0)], close=True, dxfattribs={"layer": "STATION-BUILDING"})
    doc.layers.new("PLATFORM_1")
    msp.add_lwpolyline([(300.0, 6.0), (700.0, 6.0), (700.0, 10.0), (300.0, 10.0)], close=True, dxfattribs={"layer": "PLATFORM_1"})

    # Even if far away entities exist at Y=500m
    doc.layers.new("FAR_TRACK")
    msp.add_line((4000.0, 500.0), (5000.0, 1000.0), dxfattribs={"layer": "FAR_TRACK"})

    dxf_path = tmp_path / "test_flag_cap.dxf"
    doc.saveas(dxf_path)

    gen = FakeGenerator(dxf_path)
    gen._generate_station_chainage_labels(tracks)

    res = ezdxf.readfile(dxf_path)
    chainage_lines = [e for e in res.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER]
    assert len(chainage_lines) > 0

    # Flag axis is at center_proj + 25.0, leader tip projection along normal must not exceed it
    import math
    for line in chainage_lines:
        # Distance of leader tip from track center along normal direction
        leader_len = math.hypot(line.dxf.end.x - line.dxf.start.x, line.dxf.end.y - line.dxf.start.y)
        # Leader line must not be an absurd 500m ray into the sky
        assert leader_len <= 45.0, f"Leader length too long: {leader_len:.1f} m"


def test_down_station_chainage_symmetric_distance_opposite_direction(tmp_path):
    class FakeGenerator(ChainageStep):
        def __init__(self, out_dxf):
            self.config = SimpleNamespace(
                output_dxf=str(out_dxf),
                loops=[
                    SimpleNamespace(name="LOOP_1", side="LEFT", first_crossover_chainage=375.0, second_crossover_chainage=472.0, extend_start_m=0.0, extend_end_m=0.0),
                    SimpleNamespace(name="LOOP_2", side="RIGHT", first_crossover_chainage=321.0, second_crossover_chainage=418.0, extend_start_m=0.0, extend_end_m=0.0),
                ],
                additional_lines=[],
                platforms=[],
                sidings=[],
                fobs=[],
            )
            self._crossover_results = [
                SimpleNamespace(from_track="MAIN_LINE", to_track="LOOP_1", chainage=375.0, start_chainage=375.0, end_chainage=472.0, placement="AHEAD"),
                SimpleNamespace(from_track="MAIN_LINE", to_track="LOOP_2", chainage=321.0, start_chainage=321.0, end_chainage=418.0, placement="AHEAD"),
            ]
            self._siding_results = []
            self._fouling_marks = [
                SimpleNamespace(point=(391.0, 2.5), other_point=(391.0, 2.5), tangent=(1.0, 0.0), display_tangent=(1.0, 0.0), chainage_main=391.0),
                SimpleNamespace(point=(337.0, -2.5), other_point=(337.0, -2.5), tangent=(1.0, 0.0), display_tangent=(1.0, 0.0), chainage_main=337.0),
            ]

    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)],
        "LOOP_1": [(0.0, 5.3), (1000.0, 5.3)],
        "LOOP_2": [(0.0, -5.3), (1000.0, -5.3)],
    }

    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.layers.new("STATION-BUILDING")
    msp.add_lwpolyline([(490.0, 10.0), (510.0, 10.0), (510.0, 20.0), (490.0, 20.0)], close=True, dxfattribs={"layer": "STATION-BUILDING"})
    dxf_path = tmp_path / "test_down_chainage.dxf"
    doc.saveas(dxf_path)

    gen = FakeGenerator(dxf_path)
    gen._generate_station_chainage_labels(tracks)

    res = ezdxf.readfile(dxf_path)
    lines_up = [e for e in res.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.end.y > 0]
    lines_down = [e for e in res.modelspace() if e.dxftype() == "LINE" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.end.y < 0]
    texts_down = [e for e in res.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == CHAINAGE_LAYER and e.dxf.insert.y < 0]

    assert len(lines_up) > 0, "Should have UP chainage lines"
    assert len(lines_down) > 0, "Should have DOWN chainage lines"
    assert len(texts_down) > 0, "Should have DOWN chainage texts"

    for line in lines_up:
        assert line.dxf.end.y == pytest.approx(40.0, abs=0.5)

    for line in lines_down:
        assert line.dxf.end.y == pytest.approx(-40.0, abs=0.5)

    for text in texts_down:
        assert text.dxf.insert.y == pytest.approx(-40.0, abs=0.5)
