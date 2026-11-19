"""Tests for direct 1:1 KML conversion (preserving all lines, North-up orientation)."""

from __future__ import annotations

import gzip
from pathlib import Path

import ezdxf
from app.features.drawing_generation.formats.kml.conversion import convert_kml_direct
from app.main import app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent / "fixtures"


def test_convert_kml_direct_ghaziabad(tmp_path):
    kml_path = ROOT / "Ghaziabad.kml"
    out_dxf = tmp_path / "ghaziabad_direct.dxf"
    result = convert_kml_direct(str(kml_path), str(out_dxf))
    assert Path(result).is_file()

    doc = ezdxf.readfile(result)
    msp = doc.modelspace()
    polylines = [e for e in msp if e.dxftype() == "LWPOLYLINE"]
    assert len(polylines) == 1
    assert polylines[0].dxf.layer == "Untitled path"
    assert len(polylines[0].get_points()) == 2


def test_convert_kml_direct_drawing5_preserves_all_lines(tmp_path):
    kml_path = tmp_path / "Drawing5.kml"
    kml_path.write_bytes(gzip.decompress((ROOT / "Drawing5.kml.gz").read_bytes()))
    out_dxf = tmp_path / "drawing5_direct.dxf"
    result = convert_kml_direct(str(kml_path), str(out_dxf))
    assert Path(result).is_file()

    doc = ezdxf.readfile(result)
    msp = doc.modelspace()
    polylines = [e for e in msp if e.dxftype() == "LWPOLYLINE"]
    # Drawing5 has over 1000 linestrings, all should be preserved (not collapsed to 1)
    assert len(polylines) > 500


def test_server_convert_kml_direct_endpoint():
    client = TestClient(app)
    kml_bytes = (ROOT / "Ghaziabad.kml").read_bytes()
    resp = client.post(
        "/convert-kml-direct",
        files={"kml": ("Ghaziabad.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert resp.status_code == 200
    assert "dxf" in resp.headers.get("content-type", "").lower()


def test_server_generate_with_direct_kml():
    client = TestClient(app)
    kml_bytes = (ROOT / "Ghaziabad.kml").read_bytes()
    config_json = '{"direct_kml": true, "output_dxf": "test_direct.dxf"}'
    resp = client.post(
        "/generate",
        files={
            "config": ("config.json", config_json.encode("utf-8"), "application/json"),
            "kml": ("Ghaziabad.kml", kml_bytes, "application/vnd.google-earth.kml+xml"),
        },
    )
    assert resp.status_code == 200
    assert "dxf" in resp.headers.get("content-type", "").lower()
