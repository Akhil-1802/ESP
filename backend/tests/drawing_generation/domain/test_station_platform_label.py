"""Station platform label placement and DIRECTION mark tests."""

from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest
from app.features.drawing_generation.domain.geometry.operations import polygon_contains
from app.features.drawing_generation.domain.station.builder import _polygon_area
from app.features.drawing_generation.pipeline.steps.station import StationStep


def _platform_rect(x0=0.0, x1=550.0, y0=6.0, y1=14.5):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _add_platform_label(doc, text="PLATFORM 1 (550X8.5m)", pos=(275.0, 10.25)):
    msp = doc.modelspace()
    if "PLATFORM_1_TEXT" not in doc.layers:
        doc.layers.add("PLATFORM_1_TEXT", color=1)
    mtext = msp.add_mtext(
        text,
        dxfattribs={"layer": "PLATFORM_1_TEXT", "color": 1, "char_height": 1.0},
    )
    mtext.set_location(pos, attachment_point=5)
    return mtext


def _building_at_middle():
    return SimpleNamespace(
        outline=[(261.5, 6.0), (288.5, 6.0), (288.5, 14.5), (261.5, 14.5)],
        center=(275.0, 10.25),
        angle=0.0,
    )


def _label_box(label):
    ins = label.dxf.insert
    cx, cy = float(ins.x), float(ins.y)
    txt = str(label.text or "")
    halfw = len(txt) * 1.0 * 0.7 / 2.0
    return [(cx + sx * halfw, cy + sy * 0.5)
            for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)] + [(cx, cy)]


def test_platform_label_moves_clear_of_station():
    doc = ezdxf.new("R2010")
    label = _add_platform_label(doc)
    platform = _platform_rect()
    building = _building_at_middle()
    assert polygon_contains(building.outline, (275.0, 10.25))
    StationStep._clear_platform_label_from_station(
        doc, platform, building, "PLATFORM_1_TEXT", 27.0)
    ins = label.dxf.insert
    moved = (float(ins.x), float(ins.y))
    assert polygon_contains(platform, moved)
    assert not any(polygon_contains(building.outline, c)
                   for c in _label_box(label))


def test_clear_label_is_left_alone():
    doc = ezdxf.new("R2010")
    label = _add_platform_label(doc, pos=(100.0, 10.25))
    platform = _platform_rect()
    building = _building_at_middle()
    StationStep._clear_platform_label_from_station(
        doc, platform, building, "PLATFORM_1_TEXT", 27.0)
    ins = label.dxf.insert
    assert (float(ins.x), float(ins.y)) == (100.0, 10.25)


def _add_platform_label_at(doc, text, pos, height=1.2):
    msp = doc.modelspace()
    if "PLATFORM_1_TEXT" not in doc.layers:
        doc.layers.add("PLATFORM_1_TEXT", color=1)
    mtext = msp.add_mtext(
        text,
        dxfattribs={"layer": "PLATFORM_1_TEXT", "color": 1,
                    "char_height": height},
    )
    mtext.set_location(pos, attachment_point=5)
    return mtext


def test_nudged_out_label_returns_inside_platform():
    doc = ezdxf.new("R2010")
    label = _add_platform_label_at(
        doc, "PLATFORM 1 (550X7m)", (1000.0, 11.18))
    platform = [(725.0, 1.7), (1275.0, 1.7),
                (1275.0, 8.7), (725.0, 8.7)]
    building = SimpleNamespace(
        outline=[(981.4, 10.1), (1021.4, 10.1),
                 (1021.4, 20.1), (981.4, 20.1)],
        center=(1001.4, 15.1),
        angle=0.0,
    )
    assert polygon_contains(building.outline, (1000.0, 11.18))
    StationStep._clear_platform_label_from_station(
        doc, platform, building, "PLATFORM_1_TEXT", 40.0)
    ins = label.dxf.insert
    moved = (float(ins.x), float(ins.y))
    assert moved[1] == pytest.approx((1.7 + 8.7) / 2.0)
    assert polygon_contains(platform, moved)
    assert not any(polygon_contains(building.outline, c)
                   for c in _label_box(label))


def test_station_run_keeps_platform_label_inside_platform(tmp_path):
    from app.features.drawing_generation.config import (
        ESPConfig,
        PlatformRequest,
        StationRequest,
    )
    from app.features.drawing_generation.domain.platform.config import PlatformConfig
    from app.features.drawing_generation.domain.platform.track import _extract_points
    from app.features.drawing_generation.pipeline.generator import ESPGenerator

    src = tmp_path / "src.dxf"
    out = tmp_path / "out.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line(
        (0.0, 0.0), (2000.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src))
    pcfg = PlatformConfig(
        source_dxf=str(src), output_dxf=str(out), track_layer="MAIN_LINE",
        platform_type="SIDE", side="LEFT", center_on_track=True,
        clearance=1.68, platform_width=7.0, platform_length=550.0,
        platform_name="PLATFORM 1", output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT")
    gen = ESPGenerator(ESPConfig(
        source_path=str(src), output_dxf=str(out),
        track_source_layer="MAIN_TRACK", loops=[], additional_lines=[],
        platforms=[PlatformRequest(track_layer="MAIN_LINE", config=pcfg)],
        stations=[StationRequest(
            platform_layer="PLATFORM_1", building_length=40.0,
            building_width=10.0, platform_side="LEFT",
            building_name="STATION BUILDING")],
        crossovers=[], main_directions={}))
    gen.run()
    check = ezdxf.readfile(str(out))

    plats = [e for e in check.modelspace()
             if e.dxf.layer == "PLATFORM_1"
             and e.dxftype() in ("LWPOLYLINE", "POLYLINE")]
    assert plats
    plats.sort(key=lambda e: _polygon_area(_extract_points(e)),
               reverse=True)
    platform = [(float(p[0]), float(p[1]))
                for p in _extract_points(plats[0])]
    outline = None
    for e in check.modelspace():
        if e.dxf.layer == "STATION-BUILDING" \
                and e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            pts = [(float(p[0]), float(p[1])) for p in _extract_points(e)]
            if len(pts) >= 4:
                outline = pts
                break
    assert outline is not None
    labels = [e for e in check.modelspace()
              if e.dxftype() in ("TEXT", "MTEXT")
              and e.dxf.layer == "PLATFORM_1_TEXT"
              and "PLATFORM 1" in str(
                  e.text if e.dxftype() == "MTEXT" else e.dxf.text or "")]
    assert len(labels) == 1
    label = labels[0]
    ins = label.dxf.insert
    pos = (float(ins.x), float(ins.y))
    assert polygon_contains(platform, pos)
    if label.dxftype() == "MTEXT":
        h = float(label.dxf.get("char_height", 1.0) or 1.0)
        txt = str(label.text or "")
    else:
        h = float(label.dxf.get("height", 1.0) or 1.0)
        txt = str(label.dxf.get("text", "") or "")
    halfw = max((len(p) for p in txt.split("\\P")), default=0) * h * 0.7 / 2.0
    box = [(pos[0] + sx * halfw, pos[1] + sy * h / 2.0)
           for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)] + [pos]
    assert all(polygon_contains(platform, c) for c in box)
    assert not any(polygon_contains(outline, c) for c in box)


def test_station_up_dn_marker_above_station_and_removed_from_main_line(tmp_path):
    from app.features.drawing_generation.config import (
        ESPConfig,
        PlatformRequest,
        StationRequest,
    )
    from app.features.drawing_generation.domain.platform.config import PlatformConfig
    from app.features.drawing_generation.pipeline.generator import ESPGenerator

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

    check = ezdxf.readfile(str(out))
    dir_entities = [e for e in check.modelspace() if e.dxf.layer == "DIRECTION"]
    texts = [e for e in dir_entities if e.dxftype() in ("TEXT", "MTEXT")]
    text_values = [str(e.text if e.dxftype() == "MTEXT" else e.dxf.text) for e in texts]

    assert "UP/DN" not in text_values
    assert "UP" in text_values
    assert "DN" in text_values

    for t in texts:
        val = str(t.text if t.dxftype() == "MTEXT" else t.dxf.text)
        if val in ("UP", "DN"):
            ins = t.dxf.insert
            align_pt = getattr(t.dxf, "align_point", None)
            pt_y = align_pt.y if align_pt is not None and (t.dxf.halign or t.dxf.valign) else ins.y
            assert pt_y > 30.0, f"{val} text should be placed above station (y > 30), got {pt_y}"

    dir_lines = [e for e in dir_entities if e.dxftype() == "LINE"]
    assert any(abs(e.dxf.start.y - e.dxf.end.y) < 1e-3 and e.dxf.start.y > 30.0 for e in dir_lines)


def test_station_up_dn_preserved_after_srj_trim(tmp_path):
    """When main lines are trimmed to outermost SRJs (Step 10), DIRECTION mark above station must NOT be deleted."""
    from app.features.drawing_generation.config import (
        CrossoverSpec,
        ESPConfig,
        LoopSpec,
        PlatformConfig,
        PlatformRequest,
        StationRequest,
    )
    from app.features.drawing_generation.domain.track.turnouts import select_turnout
    from app.features.drawing_generation.pipeline.generator import ESPGenerator

    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_lwpolyline(
        [(0.0, 0.0), (2000.0, 0.0)], dxfattribs={"layer": "MAIN_TRACK"}
    )
    doc.saveas(src)

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 500.0, 1500.0, extend_start_m=120.0, extend_end_m=120.0),
        LoopSpec("LOOP_2", 5.3, "RIGHT", 500.0, 1500.0, extend_start_m=120.0, extend_end_m=120.0),
    ]
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("MAIN_LINE", "LOOP_2", 800.0, None,
                      select_turnout("1:12"), "AHEAD", id="C2",
                      direction="FORWARD", position_mode="FIXED"),
    ]
    pcfg = PlatformConfig(
        source_dxf=str(src), output_dxf=str(out), track_layer="LOOP_1",
        platform_type="SIDE", side="LEFT", center_on_track=True,
        clearance=1.68, platform_width=7.0, platform_length=550.0,
        platform_name="PLATFORM 1", output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT",
    )
    cfg = ESPConfig(
        source_path=str(src), output_dxf=str(out),
        track_source_layer="MAIN_TRACK", loops=loops, additional_lines=[],
        platforms=[PlatformRequest(track_layer="LOOP_1", config=pcfg)],
        stations=[StationRequest(
            platform_layer="PLATFORM_1", building_length=40.0,
            building_width=10.0, platform_side="LEFT",
            building_name="STATION BUILDING",
        )],
        crossovers=xspecs, main_directions={},
    )
    gen = ESPGenerator(cfg)
    gen.run()

    check = ezdxf.readfile(str(out))
    dir_entities = [e for e in check.modelspace() if e.dxf.layer == "DIRECTION"]
    texts = [e for e in dir_entities if e.dxftype() in ("TEXT", "MTEXT")]
    text_values = [str(e.text if e.dxftype() == "MTEXT" else e.dxf.text) for e in texts]

    assert "UP" in text_values
    assert "DN" in text_values

    for t in texts:
        val = str(t.text if t.dxftype() == "MTEXT" else t.dxf.text)
        if val in ("UP", "DN"):
            ins = t.dxf.insert
            align_pt = getattr(t.dxf, "align_point", None)
            pt_y = align_pt.y if align_pt is not None and (t.dxf.halign or t.dxf.valign) else ins.y
            assert pt_y > 30.0, f"{val} should be above station (y > 30), got {pt_y}"
