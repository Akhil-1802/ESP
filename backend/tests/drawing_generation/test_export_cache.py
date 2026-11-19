"""Completed exports must be isolated, invalidated on edits, and never cache failures."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from app.features.drawing_generation import artifacts
from app.features.drawing_generation.cache import BoundedCache
from app.features.drawing_generation.pipeline import export
from app.main import app
from fastapi.testclient import TestClient

KML = b'''<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString>
<coordinates>77,28,0 77.015,28.004,0 77.03,28.01,0</coordinates>
</LineString></Placemark></kml>'''


@pytest.fixture
def isolated_api(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "_DXF_CACHE", BoundedCache(1024 * 1024, 8, 300))
    monkeypatch.setattr(artifacts, "BACKEND_OUTPUT_DIR", tmp_path)
    return TestClient(app, raise_server_exceptions=False)


def generate(client, payload=None, source=KML):
    return client.post("/generate", files={
        "config": ("config.json", json.dumps(payload or {}), "application/json"),
        "kml": ("source.kml", source, "application/vnd.google-earth.kml+xml"),
    })


def test_cached_export_skips_generation_but_settings_or_source_edits_regenerate(isolated_api, monkeypatch):
    calls = []
    original = export.ESPGenerator.run

    def run(generator):
        calls.append(generator.config)
        return original(generator)

    monkeypatch.setattr(export.ESPGenerator, "run", run)
    first = generate(isolated_api)
    second = generate(isolated_api, {"output_dxf": "renamed.dxf"})
    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert len(calls) == 1
    assert first.headers["x-esp-cache"] == "miss"
    assert second.headers["x-esp-cache"] == "hit"
    assert "total;dur=" in first.headers["server-timing"]
    assert "cache;dur=" in second.headers["server-timing"]
    assert generate(isolated_api, {"start_km": 1}).status_code == 200
    assert generate(isolated_api, source=KML.replace(b"77.03,", b"77.04,")).status_code == 200
    assert generate(isolated_api, {"selected_track_id": "path_0"}).status_code == 200
    assert len(calls) == 4


def test_concurrent_identical_exports_generate_once_and_save_distinct_downloads(isolated_api, tmp_path, monkeypatch):
    calls = []
    start = Barrier(4)
    original = export.ESPGenerator.run

    def run(generator):
        calls.append(generator.config)
        return original(generator)

    monkeypatch.setattr(export.ESPGenerator, "run", run)

    def request(_):
        start.wait(timeout=5)
        return generate(isolated_api)

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(request, range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert len(calls) == 1
    assert len({response.headers["content-disposition"] for response in responses}) == 4
    assert len(list(tmp_path.glob("*.dxf"))) == 4
    assert all(response.content == responses[0].content for response in responses)


@pytest.mark.parametrize("failure", ["rejected", "exception", "missing"])
def test_failed_or_missing_exports_are_not_cached(isolated_api, monkeypatch, failure):
    calls = []
    original = export.ESPGenerator.run

    def run(generator):
        calls.append(1)
        if len(calls) == 1:
            if failure == "missing":
                return generator.config.output_dxf
            if failure == "rejected":
                raise ValueError("placement conflict")
            raise RuntimeError("generation failed")
        return original(generator)

    monkeypatch.setattr(export.ESPGenerator, "run", run)
    response = generate(isolated_api)
    assert response.status_code == (422 if failure == "rejected" else 500)
    assert generate(isolated_api).status_code == 200
    assert len(calls) == 2


def test_validation_still_runs_for_cached_config(isolated_api):
    assert generate(isolated_api).status_code == 200
    response = generate(isolated_api, {"crossovers": [{"from_track": "NOPE", "to_track": "MAIN_LINE"}]})
    assert response.status_code == 422
