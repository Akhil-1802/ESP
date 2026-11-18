"""Key plans reuse finalized decisions and preserve data while resizing their layout."""

import copy
import io
import json
import math

import ezdxf
import pytest
from fastapi.testclient import TestClient

from common.cache import BoundedCache
from key_plan import KeyPlanOptions, generate_key_plan
from key_plan.layout import build_scene
from pipeline.orchestrator import ESPGenerator
from .test_generation_performance import yard_config
import server
from platform_gen.kml_io import build_kml_document, _load_kml_points


@pytest.fixture
def snapshot():
    return dict(version=1, start=1000, end=2200, start_chainage_m=4000, north_angle=55,
        tracks=[
            dict(name="MAIN_LINE", kind="MAIN", number=3, offset=0, start=1000, end=2200,
                 label="MAIN LINE NO-3 CAL 750.000M (FM TO FM)", length_m=750, direction=""),
            dict(name="LOOP_1", kind="LOOP", number=1, offset=5.3, start=1100, end=2100,
                 label="LOOP LINE NO-1 CAL 805.000M (FM TO FM)", length_m=805, direction=""),
            dict(name="LOOP_2", kind="LOOP", number=2, offset=-5.3, start=1100, end=2100,
                 label="LOOP LINE NO-2 CAL 805.000M (FM TO FM)", length_m=805, direction="")],
        platforms=[dict(name="PLATFORM_1", track="LOOP_1", second_track=None, type="SIDE", side="LEFT",
            start=1300, end=1900, offset=12, length_m=600, width_m=10, label="PASSENGER PLATFORM")],
        crossovers=[dict(id="C4", from_track="MAIN_LINE", to_track="LOOP_1", start=1200,
            end=1297.578, turnout="1:12", position_mode="resolved")],
        stations=[dict(name="JETALPUR", chainage=1600, chainage_m=5600)],
        buildings=[dict(name="JETALPUR BUILDING", platform="PLATFORM_1", chainage=1600,
            length_m=40, width_m=10, offset=25)], bridges=[])


@pytest.mark.parametrize("width,height", [(420, 150), (840, 150), (420, 300), (840, 300)])
def test_container_scales_x_and_y_independently_without_altering_measurements(snapshot, width, height):
    original = copy.deepcopy(snapshot)
    scene = build_scene(snapshot, KeyPlanOptions(width=width, height=height))
    platform = scene.platforms[0]
    assert platform["x0"] == pytest.approx(130 * width/420)
    assert platform["x1"] == pytest.approx(290 * width/420)
    assert platform["y0"] == pytest.approx(92 * height/150)
    assert platform["y1"] - platform["y0"] == pytest.approx(7 * height/150)
    assert platform["length_m"] == 600
    assert platform["width_m"] == 10
    c4 = scene.crossovers[0]
    assert c4["start"] == 1200 and c4["end"] == 1297.578
    assert c4["x1"]-c4["x0"] == pytest.approx(97.578/1200*(width-2*width*50/420))
    assert snapshot == original
    for item in scene.lines + scene.polygons:
        assert all(0 <= x <= width and 0 <= y <= height for x, y in item["points"])


def test_dxf_roundtrip_preserves_labels_units_and_geometry(snapshot, tmp_path):
    path = tmp_path / "key_plan.dxf"
    doc = generate_key_plan(snapshot)
    assert not doc.audit().errors
    doc.saveas(path)
    result = ezdxf.readfile(path)
    assert result.units == 4
    texts = [e.dxf.text for e in result.modelspace().query("TEXT")]
    assert "KEY PLAN (NOT TO SCALE)" in texts
    assert "PLATFORM 1 600.00 x 10.00M" in texts
    assert "C4 1:12" in texts
    assert any("CH:5600.00m" in text for text in texts)
    assert all(e.dxf.rotation == 0 for e in result.modelspace().query("TEXT"))


def test_vertical_order_uses_geometry_not_array_order(snapshot):
    snapshot["tracks"].reverse()
    tracks = {t["name"]: t["y"] for t in build_scene(snapshot, KeyPlanOptions()).tracks}
    assert tracks == {"LOOP_2": 60, "MAIN_LINE": 75, "LOOP_1": 90}


def test_island_platform_sits_between_its_tracks(snapshot):
    p = snapshot["platforms"][0]
    p.update(type="ISLAND", second_track="MAIN_LINE")
    snapshot["buildings"] = []
    scene = build_scene(snapshot, KeyPlanOptions())
    platform = scene.platforms[0]
    assert 75 < platform["y0"] < platform["y1"] < 90


def test_track_label_avoids_platform_on_the_lower_side(snapshot):
    snapshot["platforms"][0].update(track="LOOP_2", side="RIGHT", offset=-12)
    snapshot["buildings"] = []
    scene = build_scene(snapshot, KeyPlanOptions())
    track = next(t for t in scene.tracks if t["name"] == "LOOP_2")
    text = next(t for t in scene.texts if t["text"] == track["label"])
    assert text["y"] > track["y"]


def test_layout_rejects_overlapping_platforms_and_unreadable_captions(snapshot):
    overlapping = copy.deepcopy(snapshot)
    overlapping["platforms"].append(dict(overlapping["platforms"][0], name="PLATFORM_2"))
    with pytest.raises(ValueError, match="platforms overlap"):
        build_scene(overlapping, KeyPlanOptions())
    with pytest.raises(ValueError, match="caption is too long|label is too long"):
        build_scene(snapshot, KeyPlanOptions(width=210, height=300, station_caption="Long station name " * 8))


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_DXF_CACHE", BoundedCache(8*1024*1024, 8, 300))
    monkeypatch.setattr(server, "_KEY_PLAN_SNAPSHOTS", BoundedCache(1024*1024, 8, 600))
    monkeypatch.setattr(server, "BACKEND_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "cleanup_expired_outputs", lambda: 0)
    return TestClient(server.app, raise_server_exceptions=False)


KML = b'''<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString>
<coordinates>77,28,0 77.015,28.004,0 77.03,28.01,0</coordinates>
</LineString></Placemark></kml>'''


def export(api, finalized):
    payload = dict(enable_main_line_trim=finalized, align_final_plan_to_x_axis=finalized,
                   start_km=4, start_m=0, station_markers=[dict(name="TEST", km=5, m=0)])
    return api.post("/generate", files={"config": ("config.json", json.dumps(payload), "application/json"),
        "kml": ("source.kml", KML, "application/vnd.google-earth.kml+xml")})


def test_api_uses_finalized_snapshot_on_cache_hits_without_regeneration(api, monkeypatch):
    initial = export(api, False)
    assert initial.status_code == 200
    assert "x-esp-generation-id" not in initial.headers
    final = export(api, True)
    assert final.status_code == 200, final.text
    identifier = final.headers["x-esp-generation-id"]
    preflight = api.options('/key-plan', headers={'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
    assert preflight.status_code == 200
    def forbidden(*args, **kwargs):
        pytest.fail("Key-plan generation must not rerun the ESP pipeline")
    monkeypatch.setattr(server.ESPGenerator, "run", forbidden)
    cached = export(api, True)
    assert cached.status_code == 200
    assert cached.headers["x-esp-cache"] == "hit"
    for token in (identifier, cached.headers["x-esp-generation-id"]):
        response = api.post("/key-plan", json={"generation_id": token, "options": {"width": 840, "height": 300}})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "image/vnd.dxf"
        assert "KEY PLAN (NOT TO SCALE)" in response.text


def test_api_expired_snapshot_and_invalid_options_are_explicit(api):
    assert api.post("/key-plan", json={"generation_id": "0"*32}).status_code == 410
    token = export(api, True).headers["x-esp-generation-id"]
    for options in ({"width": -1}, {"height": 0}, {"width": "NaN"}, {"height": 150, "unknown": 1}):
        assert api.post("/key-plan", json={"generation_id": token, "options": options}).status_code == 422
    server._KEY_PLAN_SNAPSHOTS.clear()
    assert api.post("/key-plan", json={"generation_id": token}).status_code == 410


def test_complete_yard_snapshot_survives_cleanup_and_keeps_resolved_connections(tmp_path):
    generator = ESPGenerator(yard_config(tmp_path))
    generator.run()
    snapshot = generator.key_plan_snapshot
    assert snapshot is not None and generator.context.document is None
    assert len(snapshot["platforms"]) == 2
    assert len(snapshot["buildings"]) == 1
    assert {b["kind"] for b in snapshot["bridges"]} == {"FOB", "ROB"}
    assert snapshot["crossovers"][0]["end"] == pytest.approx(generator._crossover_results[0].end_chainage)
    # Confirm the rich pipeline output is a plain JSON snapshot, not a live document.
    detached = json.loads(json.dumps(snapshot))
    key_plan = generate_key_plan(detached)
    stream = io.StringIO()
    key_plan.write(stream)
    assert "KEY PLAN (NOT TO SCALE)" in stream.getvalue()


def test_survey_north_survives_horizontal_conversion_and_coordinate_cache(tmp_path):
    source = tmp_path / 'alignment.kml'
    source.write_bytes(KML)
    unrotated = _load_kml_points(str(source), align_horizontal=False)[0]
    dx, dy = unrotated[-1][0]-unrotated[0][0], unrotated[-1][1]-unrotated[0][1]
    expected = 90-math.degrees(math.atan2(dy, dx))
    first = build_kml_document(str(source))
    cached = build_kml_document(str(source))
    assert first._esp_north_angle_deg == pytest.approx(expected)
    assert cached._esp_north_angle_deg == pytest.approx(expected)
    assert cached._esp_kml_cache_hit is True
