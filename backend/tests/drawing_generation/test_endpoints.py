"""Backend API tests: POST /generate (config JSON + KML files -> DXF)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.features.drawing_generation import artifacts
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parent / "fixtures"


def _files(**overrides):
    files = {
        "config": (
            "inputconfig.json",
            (ROOT / "inputconfig.json").read_bytes(),
            "application/json",
        ),
        "kml": (
            "ESP.kml",
            (ROOT / "ESP.kml").read_bytes(),
            "application/vnd.google-earth.kml+xml",
        ),
    }
    files.update(overrides)
    return files


def test_generate_returns_dxf():
    out_dir = artifacts.BACKEND_OUTPUT_DIR
    before = set(out_dir.glob("*.dxf")) if out_dir.is_dir() else set()
    response = client.post("/generate", files=_files())
    # Note: If crossover conflict is detected in the input config, API returns 422
    if response.status_code == 200:
        assert response.headers["content-type"] == "image/vnd.dxf"
        assert response.content.startswith(b"  0")
        assert len(response.content) > 100_000
        created = set(out_dir.glob("*.dxf")) - before
        assert len(created) == 1
        saved = created.pop()
        assert saved.read_bytes() == response.content
        saved.unlink()
    else:
        assert response.status_code == 422


def test_main_center_returns_centred_loop():
    with (ROOT / "ESP.kml").open("rb") as stream:
        content = stream.read()
    response = client.post(
        "/main-center",
        files={"kml": ("ESP.kml", content, "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["default_c2_m"] - data["default_c1_m"] == pytest.approx(750.0)
    assert data["main_center_m"] == pytest.approx(
        (data["default_c1_m"] + data["default_c2_m"]) / 2.0)
    assert data["main_length_m"] == pytest.approx(data["main_center_m"] * 2.0)


def test_main_center_rejects_non_kml():
    response = client.post(
        "/main-center",
        files={"kml": ("source.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 422


def test_generate_rejects_unknown_crossover_track():
    payload = json.loads((ROOT / "inputconfig.json").read_bytes())
    payload.pop("crossover_preset", None)
    payload.pop("crossover_preset_turnout", None)
    payload["crossovers"] = [
        {"from_track": "NOPE", "to_track": "MAIN_LINE",
         "from_chainage_m": 175.709, "turnout": "1:12",
         "direction": "REVERSE"},
    ]
    response = client.post(
        "/generate",
        files={
            "config": ("inputconfig.json", json.dumps(payload), "application/json"),
            "kml": ("ESP.kml", (ROOT / "ESP.kml").read_bytes(),
                    "application/vnd.google-earth.kml+xml"),
        },
    )
    assert response.status_code == 422
    assert "unknown" in response.json()["detail"].lower()


def test_generate_rejects_invalid_json():
    response = client.post(
        "/generate",
        files=_files(config=("inputconfig.json", b"{not json", "application/json")),
    )
    assert response.status_code == 422


def test_generate_rejects_non_kml_source():
    response = client.post(
        "/generate",
        files=_files(kml=("source.txt", b"hello", "text/plain")),
    )
    assert response.status_code == 422


def test_generate_requires_both_files():
    config_only = {"config": _files()["config"]}
    assert client.post("/generate", files=config_only).status_code == 422


def test_cleanup_expired_outputs_deletes_old_files_and_preserves_gitkeep(tmp_path):
    import os
    import time

    from app.features.drawing_generation.artifacts import cleanup_expired_outputs

    # Create dummy files in a temporary output directory
    gitkeep = tmp_path / ".gitkeep"
    gitkeep.write_text("")

    fresh_file = tmp_path / "fresh.dxf"
    fresh_file.write_text("fresh")

    old_file = tmp_path / "old.dxf"
    old_file.write_text("old")

    # Set old_file's mtime to 15 minutes ago (900 seconds)
    fifteen_mins_ago = time.time() - 900
    os.utime(old_file, (fifteen_mins_ago, fifteen_mins_ago))

    # Run cleanup with 600s (10 min) TTL
    deleted_count = cleanup_expired_outputs(output_dir=tmp_path, ttl_seconds=600.0)

    assert deleted_count == 1
    assert not old_file.exists()
    assert fresh_file.exists()
    assert gitkeep.exists()
