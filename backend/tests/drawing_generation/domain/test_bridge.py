"""Bridge placement, type captions, and independent DXF block regression tests."""
from types import SimpleNamespace
import json
import math

import ezdxf
import pytest

from app.features.drawing_generation.config import ESPConfig, load_config_from_json
from app.features.drawing_generation.domain.bridges.bridge.config import BridgeConfig
from app.features.drawing_generation.domain.bridges.bridge.geometry import generate_bridge_geometry
from app.features.drawing_generation.domain.bridges.bridge.placement import (
    alignment_start_metres, parse_absolute_chainage, resolve_bridge_placement,
)
from app.features.drawing_generation.pipeline.steps.bridge import BridgeStep


TRACKS = {"MAIN_LINE": [(0.0, 0.0), (2000.0, 0.0)],
          "LOOP_1": [(0.0, 5.3), (2000.0, 5.3)]}


def building(start, end):
    return SimpleNamespace(_bridge_outline=[(start, 10), (end, 10), (end, 20), (start, 20)])


def config(**kwargs):
    return SimpleNamespace(stations=[building(480, 520), building(1480, 1520)],
                           start_km=12, start_m=0, **kwargs)


@pytest.mark.parametrize("direction,expected", [("INCREASING", 1620), ("DECREASING", 1380)])
def test_offset_uses_selected_station_edge(direction, expected):
    cfg = BridgeConfig(station_index=1, direction=direction, offset=100)
    placement = resolve_bridge_placement(cfg, config(), TRACKS)
    assert placement.distance == pytest.approx(expected)
    assert placement.point == pytest.approx((expected, 0))
    assert placement.absolute_chainage == pytest.approx(12000 + expected)


@pytest.mark.parametrize("chainage", ["12+850", "12850", 12850, "12.850 KM", "12850 M"])
def test_fixed_chainage_converts_datum_without_a_station(chainage):
    cfg = BridgeConfig(position_mode="FIXED", chainage=chainage)
    placement = resolve_bridge_placement(cfg, SimpleNamespace(stations=[], start_km=12, start_m=0), TRACKS)
    assert placement.distance == pytest.approx(850)


def test_curved_alignment_uses_distance_along_segments():
    tracks = {"MAIN_LINE": [(0, 0), (600, 0), (600, 800)]}
    cfg = BridgeConfig(position_mode="FIXED", chainage="12+850")
    result = resolve_bridge_placement(cfg, config(), tracks)
    assert result.point == pytest.approx((600, 250))
    assert result.tangent == pytest.approx((0, 1))


@pytest.mark.parametrize("raw,expected", [("-0+100", -100), ("0+000", 0), ("12+850.5", 12850.5)])
def test_absolute_parser(raw, expected):
    assert parse_absolute_chainage(raw) == expected


@pytest.mark.parametrize("raw", ["", "nan", "inf", "12+1000", "12+85x", None])
def test_invalid_chainage_rejected(raw):
    with pytest.raises(ValueError):
        parse_absolute_chainage(raw)


@pytest.mark.parametrize("kwargs", [
    {"width": math.nan}, {"width": 0}, {"deck_margin": math.inf},
    {"bridge_type": "INVALID"}, {"bridge_type": "OTHER"},
    {"bridge_type": "OTHER", "custom_type": "Bad\\Pcaption"},
    {"position_mode": "OFFSET", "station_index": None},
    {"position_mode": "OFFSET", "station_index": True},
    {"position_mode": "OFFSET", "station_index": 0, "offset": math.inf},
    {"position_mode": "OFFSET", "station_index": 0, "direction": "LEFT"},
])
def test_invalid_bridge_inputs(kwargs):
    with pytest.raises(ValueError):
        BridgeConfig(**({"position_mode": "FIXED", "chainage": "12+850"} | kwargs))


def test_missing_station_and_out_of_bounds_are_errors():
    with pytest.raises(ValueError, match="unavailable"):
        resolve_bridge_placement(BridgeConfig(station_index=5), config(), TRACKS)
    with pytest.raises(ValueError, match="outside MAIN"):
        resolve_bridge_placement(BridgeConfig(position_mode="FIXED", chainage="11+999"), config(), TRACKS)
    cfg = BridgeConfig(station_index=0, direction="DECREASING", offset=1000)
    with pytest.raises(ValueError, match="outside MAIN"):
        resolve_bridge_placement(cfg, config(), TRACKS)


def test_negative_start_and_explicit_metre_datum():
    assert alignment_start_metres(SimpleNamespace(start_km="-0", start_m=100)) == -100
    assert alignment_start_metres(SimpleNamespace(start_chainage="12+500")) == 12500
    assert alignment_start_metres(SimpleNamespace(start_chainage="12")) == 12000
    assert alignment_start_metres(SimpleNamespace(start_chainage="12.0")) == 12


def test_multi_bridge_blocks_and_type_captions_roundtrip(tmp_path):
    output = tmp_path / "bridges.dxf"
    doc = ezdxf.new("R2010")
    doc.saveas(output)
    bridges = [
        BridgeConfig(position_mode="FIXED", chainage="12+500", width=10, bridge_type="PSC_SLAB"),
        BridgeConfig(position_mode="FIXED", chainage="13+000", width=20, bridge_type="RCC_BOX"),
        BridgeConfig(position_mode="FIXED", chainage="13+500", bridge_type="OTHER", custom_type="Steel girder"),
    ]
    esp = ESPConfig(str(output), str(output), "MAIN_LINE", start_km=12, bridges=bridges)
    step = BridgeStep()
    step.config = esp
    step._generate_bridges(TRACKS)
    result = ezdxf.readfile(output)
    inserts = list(result.modelspace().query("INSERT"))
    assert [e.dxf.insert.x for e in inserts] == pytest.approx([500, 1000, 1500])
    assert len({e.dxf.name for e in inserts}) == 3
    assert result.blocks[inserts[0].dxf.name][0].dxf.start.x == pytest.approx(-5)
    assert result.blocks[inserts[1].dxf.name][0].dxf.start.x == pytest.approx(-10)
    texts = [e.dxf.text for e in result.modelspace().query("TEXT")]
    assert {"PSC SLAB BRIDGE", "RCC BOX BRIDGE", "Steel girder BRIDGE"} <= set(texts)
    assert bridges[0]._absolute_chainage == 12500


def test_json_loader_reads_bridge_modes(tmp_path):
    source = tmp_path / "source.dxf"
    ezdxf.new().saveas(source)
    payload = {"source_path": str(source), "output_dxf": str(tmp_path / "output.dxf"),
               "track_source_layer": "MAIN_LINE", "bridges": [
                   {"position_mode": "FIXED", "chainage": "12+850", "bridge_type": "RCC_BOX"}]}
    filename = tmp_path / "config.json"
    filename.write_text(json.dumps(payload))
    loaded = load_config_from_json(str(filename))
    assert loaded.bridges[0].bridge_type == "RCC_BOX"
    assert loaded.bridges[0].chainage == "12+850"

def test_span_uses_actual_crossing_when_nearest_point_is_far_along_track():
    tracks = {"MAIN_LINE": [(0, 0), (2000, 0)],
              "DIAGONAL": [(0, -300), (2000, 1700)]}
    cfg = BridgeConfig(position_mode="FIXED", chainage="500")
    geom = generate_bridge_geometry((500, 0), (1, 0), tracks, cfg)
    assert geom.deck_span == pytest.approx((-3.5, 203.5))


def test_legacy_bridge_payload_requires_explicit_reconfiguration(tmp_path):
    filename = tmp_path / "old.json"
    filename.write_text(json.dumps({"robs": [{"platform": "PLATFORM_1"}]}))
    with pytest.raises(ValueError, match="reconfigured"):
        load_config_from_json(str(filename))
