"""Key plans reuse finalized decisions and preserve data while resizing their layout."""

import copy
import io
import json
import math

import ezdxf
import pytest
from app.features.drawing_generation import artifacts
from app.features.drawing_generation.cache import BoundedCache
from app.features.drawing_generation.domain.key_plan.config import KeyPlanOptions
from app.features.drawing_generation.domain.key_plan.generator import generate_key_plan
from app.features.drawing_generation.domain.key_plan.layout import build_scene
from app.features.drawing_generation.domain.track.overrun_metadata import (
    resolved_overruns,
)
from app.features.drawing_generation.domain.track.specs import LineSpec
from app.features.drawing_generation.formats.dxf.tracks import draw_srj_overrun_stub
from app.features.drawing_generation.formats.kml.conversion import (
    _load_kml_points,
    build_kml_document,
)
from app.features.drawing_generation.pipeline import export
from app.features.drawing_generation.pipeline.generator import ESPGenerator
from app.main import app
from fastapi.testclient import TestClient

from .yard_fixture import yard_config


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
    assert "1:12" in texts
    assert not any('C4' in text for text in texts)
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
    monkeypatch.setattr(export, "_DXF_CACHE", BoundedCache(8*1024*1024, 8, 300))
    monkeypatch.setattr(export, "_KEY_PLAN_SNAPSHOTS", BoundedCache(1024*1024, 8, 600))
    monkeypatch.setattr(artifacts, "BACKEND_OUTPUT_DIR", tmp_path)
    return TestClient(app, raise_server_exceptions=False)


KML = b'''<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString>
<coordinates>77,28,0 77.015,28.004,0 77.03,28.01,0</coordinates>
</LineString></Placemark></kml>'''


def request_export(api, finalized):
    payload = dict(enable_main_line_trim=finalized, align_final_plan_to_x_axis=finalized,
                   start_km=4, start_m=0, station_markers=[dict(name="TEST", km=5, m=0)])
    return api.post("/generate", files={"config": ("config.json", json.dumps(payload), "application/json"),
        "kml": ("source.kml", KML, "application/vnd.google-earth.kml+xml")})


def test_api_uses_finalized_snapshot_on_cache_hits_without_regeneration(api, monkeypatch):
    initial = request_export(api, False)
    assert initial.status_code == 200
    assert "x-esp-generation-id" not in initial.headers
    final = request_export(api, True)
    assert final.status_code == 200, final.text
    identifier = final.headers["x-esp-generation-id"]
    preflight = api.options('/key-plan', headers={'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
    assert preflight.status_code == 200
    def forbidden(*args, **kwargs):
        pytest.fail("Key-plan generation must not rerun the ESP pipeline")
    monkeypatch.setattr(export.ESPGenerator, "run", forbidden)
    cached = request_export(api, True)
    assert cached.status_code == 200
    assert cached.headers["x-esp-cache"] == "hit"
    for token in (identifier, cached.headers["x-esp-generation-id"]):
        response = api.post("/key-plan", json={"generation_id": token, "options": {"width": 840, "height": 300}})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "image/vnd.dxf"
        assert "KEY PLAN (NOT TO SCALE)" in response.text


def test_api_expired_snapshot_and_invalid_options_are_explicit(api):
    assert api.post("/key-plan", json={"generation_id": "0"*32}).status_code == 410
    token = request_export(api, True).headers["x-esp-generation-id"]
    for options in ({"width": -1}, {"height": 0}, {"width": "NaN"}, {"height": 150, "unknown": 1}):
        assert api.post("/key-plan", json={"generation_id": token, "options": options}).status_code == 422
    export._KEY_PLAN_SNAPSHOTS.clear()
    assert api.post("/key-plan", json={"generation_id": token}).status_code == 410


def test_two_stations_on_shared_alignment_keep_independent_finalized_plans(api):
    tokens = {}
    for km, name in enumerate(("PANSAR", "SATMILE"), start=1):
        payload = dict(enable_main_line_trim=True, align_final_plan_to_x_axis=True,
                       station_markers=[dict(name=name, km=km, m=0)])
        response = api.post("/generate", files={
            "config": ("config.json", json.dumps(payload), "application/json"),
            "kml": ("source.kml", KML, "application/vnd.google-earth.kml+xml"),
        })
        assert response.status_code == 200, response.text
        tokens[name] = response.headers["x-esp-generation-id"]
    for name, token in tokens.items():
        plan = api.post("/key-plan", json={"generation_id": token})
        assert plan.status_code == 200, plan.text
        assert name in plan.text
        assert all(other not in plan.text for other in tokens if other != name)


def test_complete_yard_snapshot_survives_cleanup_and_keeps_resolved_connections(tmp_path):
    generator = ESPGenerator(yard_config(tmp_path))
    generator.run()
    snapshot = generator.key_plan_snapshot
    assert snapshot is not None and generator.context.document is None
    assert len(snapshot["platforms"]) == 2
    assert len(snapshot["buildings"]) == 1
    assert {b["kind"] for b in snapshot["bridges"]} == {"FOB", "BRIDGE"}
    bridge = next(b for b in snapshot["bridges"] if b["kind"] == "BRIDGE")
    cfg = generator.config.bridges[0]
    assert bridge["chainage"] == pytest.approx(cfg._calculated_chainage)
    assert bridge["absolute_chainage"] == pytest.approx(cfg._absolute_chainage)
    assert bridge["bridge_type"] == "PSC_SLAB" and bridge["label"] == "PSC SLAB"
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


@pytest.mark.parametrize('start_length,end_length', [(120, 80), (0, 120), (120, 0), (0, 0)])
def test_final_snapshot_retains_actual_overruns_and_separates_running_track(tmp_path, start_length, end_length):
    cfg = yard_config(tmp_path)
    for loop in cfg.loops:
        loop.extend_start_m, loop.extend_end_m = start_length, end_length
    generator = ESPGenerator(cfg)
    generator.run()
    snapshot = json.loads(json.dumps(generator.key_plan_snapshot))
    expected = 2 * (int(start_length > 0) + int(end_length > 0))
    assert len(snapshot['overruns']) == expected
    tracks = {track['name']: track for track in snapshot['tracks']}
    for overrun in snapshot['overruns']:
        track = tracks[overrun['track']]
        assert overrun['length_m'] == pytest.approx(start_length if overrun['at_start'] else end_length)
        assert overrun['srj_chainage'] == pytest.approx(track['start'] if overrun['at_start'] else track['end'])
        assert (overrun['tip_chainage'] < overrun['srj_chainage']) == overrun['at_start']
        assert snapshot['start'] <= overrun['tip_chainage'] <= snapshot['end']
    scene = build_scene(snapshot, KeyPlanOptions())
    assert len(scene.overruns) == expected
    assert len([line for line in scene.lines if line['layer'] == 'KEY_PLAN_DEAD_END']) == expected
    assert len(scene.directions) == 4
    assert {(d['side'], d['direction']) for d in scene.directions} == {
        ('left', 'UP'), ('left', 'DN'), ('right', 'UP'), ('right', 'DN')}
    texts = [e.dxf.text for e in generate_key_plan(snapshot).modelspace().query('TEXT')]
    assert not any('OVER RUN' in text or text == 'DE' for text in texts)


@pytest.mark.parametrize('width,height', [(420, 150), (840, 150), (420, 300), (840, 300)])
def test_overrun_endpoints_and_up_dn_arrows_scale_with_the_container(snapshot, width, height):
    snapshot['overruns'] = [dict(track='LOOP_1', at_start=True, srj_chainage=1100,
                                tip_chainage=1000, length_m=100),
                            dict(track='LOOP_1', at_start=False, srj_chainage=2100,
                                 tip_chainage=2200, length_m=100)]
    snapshot['tracks'][0]['direction'] = 'UP'
    snapshot['tracks'].append(dict(snapshot['tracks'][0], name='MAIN_LINE_1', offset=-10.6, direction='DN'))
    original = copy.deepcopy(snapshot)
    scene = build_scene(snapshot, KeyPlanOptions(width=width, height=height))
    assert snapshot == original
    assert scene.overruns[0]['x_tip'] == pytest.approx(50*width/420)
    assert scene.overruns[1]['x_tip'] == pytest.approx(370*width/420)
    assert all(overrun['length_m'] == 100 for overrun in scene.overruns)
    directions = {direction['direction']: direction for direction in scene.directions}
    assert directions['UP']['x_head'] < directions['UP']['x_tail']
    assert directions['DN']['x_head'] > directions['DN']['x_tail']
    assert len(scene.directions) == 4
    for marker in scene.directions:
        xs = [marker['x_head'], marker['x_tail']]
        assert max(xs) < width*50/420 if marker['side'] == 'left' else min(xs) > width*(1-50/420)
    texts = [text['text'] for text in scene.texts]
    assert 'UP MAIN LINE' in texts and 'DN MAIN LINE' in texts
    for item in scene.lines + scene.polygons:
        assert all(0 <= x <= width and 0 <= y <= height for x, y in item['points'])


def test_direction_snapshot_uses_additional_line_settings_and_explicit_overrides(tmp_path):
    cfg = yard_config(tmp_path)
    cfg.additional_lines = [LineSpec('MAIN_LINE_1', 15.9, 'RIGHT', direction='DN')]
    cfg.main_directions = {'MAIN_LINE': 'UP'}
    gen = ESPGenerator(cfg)
    gen.run()
    directions = {t['name']: t['direction'] for t in gen.key_plan_snapshot['tracks']}
    assert directions['MAIN_LINE'] == 'UP'
    assert directions['MAIN_LINE_1'] == 'DN'
    assert directions['LOOP_1'] == ''
    cfg.main_directions['MAIN_LINE_1'] = 'UP'
    gen = ESPGenerator(cfg)
    gen.run()
    assert next(t for t in gen.key_plan_snapshot['tracks'] if t['name'] == 'MAIN_LINE_1')['direction'] == 'UP'


def test_overrun_clamped_at_main_start_uses_actual_length_and_resolved_srj(tmp_path):
    cfg = yard_config(tmp_path)
    for loop in cfg.loops:
        loop.extend_start_m = loop.extend_end_m = 120
    cfg.loops[0].first_crossover_chainage = 50
    cfg.crossovers[0].from_track = 'LOOP_1'
    cfg.crossovers[0].to_track = 'MAIN_LINE'
    cfg.crossovers[0].from_chainage_m = 50
    generator = ESPGenerator(cfg)
    generator.run()
    overrun = next(o for o in generator.key_plan_snapshot['overruns'] if o['track'] == 'LOOP_1' and o['at_start'])
    assert overrun['tip_chainage'] == pytest.approx(0)
    assert 0 < overrun['length_m'] < 120
    assert overrun['length_m'] == pytest.approx(overrun['srj_chainage'])
    scene = build_scene(generator.key_plan_snapshot, KeyPlanOptions())
    assert any(o['length_m'] == overrun['length_m'] for o in scene.overruns)
    assert not any('OVER RUN' in text['text'] for text in scene.texts)


def test_curved_overrun_metadata_survives_dxf_roundtrip_and_transforms(tmp_path):
    from ezdxf.math import Matrix44
    doc = ezdxf.new('R2010')
    draw_srj_overrun_stub(doc, [(0, 5), (30, 5), (30, 45)], True, True, track_name='LOOP_1')
    path = tmp_path / 'overrun.dxf'
    doc.saveas(path)
    loaded = ezdxf.readfile(path)
    record = list(resolved_overruns(loaded))[0]
    assert record['length_m'] == 70
    assert tuple(record['srj']) == (30, 45, 0)
    assert tuple(record['tip']) == (0, 5, 0)
    for entity in loaded.modelspace():
        entity.transform(Matrix44.translate(100, 200, 0))
    translated = list(resolved_overruns(loaded))[0]
    assert tuple(translated['srj']) == (130, 245, 0)
    assert tuple(translated['tip']) == (100, 205, 0)
    assert translated['length_m'] == 70
    assert not loaded.audit().errors


def test_cached_finalization_exports_overruns_and_directions_without_replanning(api, monkeypatch):
    payload = dict(enable_main_line_trim=True, align_final_plan_to_x_axis=True,
        loops=[dict(name='LOOP_1', spacing=5.3, side='LEFT', first_crossover_chainage=500,
                    second_crossover_chainage=1800, extend_start_m=120, extend_end_m=120)],
        additional_lines=[dict(name='MAIN_LINE_1', spacing=15.9, side='RIGHT', direction='DN')],
        main_directions={'MAIN_LINE': 'UP'})
    def finalize():
        return api.post('/generate', files={'config': ('config.json', json.dumps(payload), 'application/json'),
            'kml': ('source.kml', KML, 'application/vnd.google-earth.kml+xml')})
    response = finalize()
    assert response.status_code == 200, response.text
    monkeypatch.setattr(ESPGenerator, 'run', lambda *_: pytest.fail('Cached key plans must not regenerate the ESP'))
    cached = finalize()
    assert cached.status_code == 200 and cached.headers['x-esp-cache'] == 'hit'
    response = api.post('/key-plan', json={'generation_id': cached.headers['x-esp-generation-id']})
    assert response.status_code == 200, response.text
    doc = ezdxf.read(io.StringIO(response.content.decode('utf-8'), newline=None))
    texts = [e.dxf.text for e in doc.modelspace().query('TEXT')]
    assert not any('OVER RUN' in text for text in texts)
    assert 'UP MAIN LINE' in texts and 'DN MAIN LINE' in texts
    assert texts.count('UP MAIN LINE') == texts.count('DN MAIN LINE') == 2
    assert len(doc.modelspace().query('LWPOLYLINE[layer=="KEY_PLAN_DEAD_END"]')) == 2


def test_reference_presentation_keeps_geometry_without_overrun_or_crossover_names(snapshot):
    snapshot['tracks'][0]['direction'] = 'UP/DN'
    snapshot['overruns'] = [dict(track='LOOP_1', at_start=True, srj_chainage=1100,
                                tip_chainage=1000, length_m=100)]
    scene = build_scene(snapshot, KeyPlanOptions(left_destination='BJD', right_destination='SANAND'))
    texts = [text['text'] for text in scene.texts]
    assert not any('OVER RUN' in text or 'C4' in text for text in texts)
    assert '1:12' in texts
    assert len(scene.overruns) == 1 and len(scene.crossovers) == 1
    assert any(line['layer'] == 'KEY_PLAN_DEAD_END' for line in scene.lines)
    assert any(line['layer'] == 'KEY_PLAN_CONNECTION' for line in scene.lines)
    assert texts.count('DN MAIN LINE') == texts.count('UP MAIN LINE') == 2
    for side in ('left', 'right'):
        markers = {d['direction']: d for d in scene.directions if d['side'] == side}
        assert markers['DN']['y'] > markers['UP']['y']
