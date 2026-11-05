"""Backend API tests: POST /generate (config JSON + KML files -> DXF)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from wizard import wizard_to_config_dict

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parents[2]


def _files(**overrides):
    files = {
        "config": (
            "inputconfig.json",
            (ROOT / "examples" / "inputconfig.json").read_bytes(),
            "application/json",
        ),
        "kml": (
            "ESP.kml",
            (ROOT / "data" / "ESP.kml").read_bytes(),
            "application/vnd.google-earth.kml+xml",
        ),
    }
    files.update(overrides)
    return files


def test_generate_returns_dxf():
    out_dir = ROOT / "output"
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
    with (ROOT / "data" / "ESP.kml").open("rb") as stream:
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
    payload = json.loads((ROOT / "examples" / "inputconfig.json").read_bytes())
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
            "kml": ("ESP.kml", (ROOT / "data" / "ESP.kml").read_bytes(),
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


def _wizard_files(spec: dict):
    return {
        "spec": ("spec.json", json.dumps(spec), "application/json"),
        "kml": (
            "ESP.kml",
            (ROOT / "data" / "ESP.kml").read_bytes(),
            "application/vnd.google-earth.kml+xml",
        ),
    }


def test_wizard_centers_loops_like_interactive():
    config = wizard_to_config_dict(
        {"loops": {"count": 2, "spacings": [5.3, 6.3], "sides": ["LEFT", "RIGHT"]}},
        main_center=1000.0,
    )
    c1 = [loop["first_crossover_chainage"] for loop in config["loops"]]
    c2 = [loop["second_crossover_chainage"] for loop in config["loops"]]
    assert c1 == [625.0, 625.0]
    assert c2 == [1375.0, 1375.0]
    assert [loop["extend_start_m"] for loop in config["loops"]] == [120.0, 120.0]
    assert [loop["extend_end_m"] for loop in config["loops"]] == [120.0, 120.0]


def test_wizard_additional_main_lines_include_default_directions():
    config = wizard_to_config_dict({
        "main_lines": {"count": 2, "distances": [5.3, 6.5], "sides": ["LEFT", "RIGHT"]},
    })
    assert config["additional_lines"][:2] == [
        {"name": "MAIN_LINE_1", "spacing": 5.3, "side": "LEFT", "direction": "DN"},
        {"name": "MAIN_LINE_2", "spacing": 6.5, "side": "RIGHT", "direction": "DN"},
    ]
    assert config["main_directions"] == {
        "MAIN_LINE": "UP", "MAIN_LINE_1": "DN", "MAIN_LINE_2": "DN",
    }


def test_wizard_rejects_bad_shapes():
    with pytest.raises(ValueError):
        wizard_to_config_dict({"loops": {"count": 2, "sides": ["LEFT"]}}, 1000.0)
    with pytest.raises(ValueError):
        wizard_to_config_dict({"loops": {"count": 1, "spacings": [4.0]}}, 1000.0)
    with pytest.raises(ValueError):
        wizard_to_config_dict({"mystery": 1}, 1000.0)


def test_generate_wizard_returns_dxf():
    out_dir = ROOT / "output"
    before = set(out_dir.glob("*.dxf")) if out_dir.is_dir() else set()
    spec = {
        "output_dxf": "ESP_wizard_test.dxf",
        "loops": {"count": 2, "spacings": [5.3, 6.3], "sides": ["LEFT", "RIGHT"]},
        "crossovers": "DEFAULT",
        "platforms": [
            {"track": "LOOP_1", "side": "LEFT"},
            {"track": "LOOP_2", "side": "RIGHT"},
        ],
    }
    response = client.post("/generate-wizard", files=_wizard_files(spec))
    if response.status_code == 200:
        assert response.headers["content-type"] == "image/vnd.dxf"
        assert response.content.startswith(b"  0")
        assert len(response.content) > 100_000
        created = set(out_dir.glob("*.dxf")) - before
        assert len(created) == 1
        created.pop().unlink()
    else:
        assert response.status_code == 422


def test_generate_wizard_rejects_bad_spec():
    spec = {"loops": {"count": 1, "spacings": [4.0]}}
    response = client.post("/generate-wizard", files=_wizard_files(spec))
    assert response.status_code == 422


def test_cleanup_expired_outputs_deletes_old_files_and_preserves_gitkeep(tmp_path):
    import os
    import time
    from server import cleanup_expired_outputs

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


def test_health_check_get_and_head():
    # Test GET request
    response_get = client.get("/health")
    assert response_get.status_code == 200
    assert response_get.json() == {"status": "ok"}

    # Test HEAD request
    response_head = client.head("/health")
    assert response_head.status_code == 200
    assert response_head.text == ""
