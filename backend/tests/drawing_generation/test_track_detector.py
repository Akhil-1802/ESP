"""Unit and regression tests for topological track detector."""

from __future__ import annotations

import gzip
from pathlib import Path

import ezdxf
from app.features.drawing_generation.formats.kml.conversion import convert_kml_to_dxf
from app.features.drawing_generation.formats.kml.track_detector import detect_kml_tracks
from app.main import app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent / "fixtures"


def test_detect_single_linestring_kml(tmp_path):
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>TRACK_1</name>
      <LineString>
        <coordinates>
          77.4000,28.6000,0
          77.4100,28.6000,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    kml_file = tmp_path / "single.kml"
    kml_file.write_text(kml_content, encoding="utf-8")

    tracks = detect_kml_tracks(str(kml_file), min_track_length_m=50.0)
    assert len(tracks) == 1
    assert tracks[0]["candidate_id"] == "path_0"
    assert tracks[0]["name"] == "Path 1"
    assert tracks[0]["segment_count"] == 1
    assert tracks[0]["length_m"] > 900.0


def test_detect_connected_segments_chained(tmp_path):
    # Two line segments that connect end-to-end (Seg 1: 0 to 1km, Seg 2: 1km to 2km)
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>SEG_A</name>
      <LineString>
        <coordinates>
          77.4000,28.6000,0
          77.4100,28.6000,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>SEG_B</name>
      <LineString>
        <coordinates>
          77.4100,28.6000,0
          77.4200,28.6000,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    kml_file = tmp_path / "connected.kml"
    kml_file.write_text(kml_content, encoding="utf-8")

    tracks = detect_kml_tracks(str(kml_file), min_track_length_m=50.0)
    # The two segments should be chained into 1 single continuous path
    assert len(tracks) == 1
    assert tracks[0]["segment_count"] == 2
    assert tracks[0]["length_m"] > 1800.0


def test_detect_parallel_tracks_not_merged(tmp_path):
    # Two parallel lines separated by 5.3m in latitude (~0.000048 deg)
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>MAIN_LINE</name>
      <LineString>
        <coordinates>
          77.4000,28.600000,0
          77.4100,28.600000,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>LOOP_LINE</name>
      <LineString>
        <coordinates>
          77.4000,28.600050,0
          77.4100,28.600050,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    kml_file = tmp_path / "parallel.kml"
    kml_file.write_text(kml_content, encoding="utf-8")

    tracks = detect_kml_tracks(str(kml_file), min_track_length_m=50.0, endpoint_tol_m=2.0)
    # Both parallel lines must remain separate candidate paths
    assert len(tracks) == 2
    assert tracks[0]["candidate_id"] == "path_0"
    assert tracks[1]["candidate_id"] == "path_1"
    assert tracks[0]["segment_count"] == 1
    assert tracks[1]["segment_count"] == 1


def test_detect_filters_ticks_and_legends(tmp_path):
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>REAL_TRACK</name>
      <LineString>
        <coordinates>
          77.4000,28.6000,0
          77.4100,28.6000,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>SLEEPER_TICK_1</name>
      <LineString>
        <coordinates>
          77.4050,28.60000,0
          77.4050,28.60003,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>NORTH_ARROW_LEGEND</name>
      <LineString>
        <coordinates>
          0.0000,0.0000,0
          0.0010,0.0010,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    kml_file = tmp_path / "ticks.kml"
    kml_file.write_text(kml_content, encoding="utf-8")

    tracks = detect_kml_tracks(str(kml_file), min_track_length_m=50.0)
    assert len(tracks) == 1
    assert tracks[0]["source_names"][0] == "REAL_TRACK"


def test_server_detect_tracks_endpoint():
    client = TestClient(app)
    kml_bytes = (ROOT / "Ghaziabad.kml").read_bytes()
    resp = client.post(
        "/detect-tracks",
        files={"kml": ("Ghaziabad.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "candidate_tracks" in data
    assert len(data["candidate_tracks"]) >= 1


def test_convert_kml_with_selected_track_id(tmp_path):
    kml_path = ROOT / "Ghaziabad.kml"
    out_dxf = tmp_path / "selected_track.dxf"
    result = convert_kml_to_dxf(str(kml_path), str(out_dxf), selected_track_id=0)
    assert Path(result).is_file()

    doc = ezdxf.readfile(result)
    polylines = [e for e in doc.modelspace() if e.dxftype() == "LWPOLYLINE"]
    assert len(polylines) == 1
    assert polylines[0].dxf.layer == "MAIN_TRACK"


def test_cad_track_removes_transverse_micro_step_without_spike(tmp_path):
    """A 1 m transverse CAD step is normalized instead of bridged diagonally."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark><name>Polyline [ABC]:0</name><LineString><coordinates>
    77.000000,28.000000,0 77.000051,28.000000,0
  </coordinates></LineString></Placemark>
  <Placemark><name>Polyline [ABC]:0</name><LineString><coordinates>
    77.000051,28.000000,0 77.000051,28.000009,0
  </coordinates></LineString></Placemark>
  <Placemark><name>Polyline [ABC]:0</name><LineString><coordinates>
    77.000051,28.000009,0 77.000102,28.000009,0
  </coordinates></LineString></Placemark>
</Document></kml>"""
    kml_file = tmp_path / "short_connector.kml"
    kml_file.write_text(kml_content, encoding="utf-8")

    tracks = detect_kml_tracks(
        str(kml_file), min_track_length_m=1.0, endpoint_tol_m=1.5
    )

    assert len(tracks) == 1
    assert tracks[0]["segment_count"] == 2
    points = tracks[0]["pts_utm"]
    assert len(points) == 3
    first = (points[1][0] - points[0][0], points[1][1] - points[0][1])
    second = (points[2][0] - points[1][0], points[2][1] - points[1][1])
    first_len = (first[0] ** 2 + first[1] ** 2) ** 0.5
    second_len = (second[0] ** 2 + second[1] ** 2) ** 0.5
    dot = (first[0] * second[0] + first[1] * second[1]) / (first_len * second_len)
    assert dot > 0.9999


def test_detect_tracks_on_survey_kml(tmp_path):
    path = tmp_path / "survey.kml"
    path.write_bytes(gzip.decompress((ROOT / "doc.kml.gz").read_bytes()))

    tracks = detect_kml_tracks(str(path), min_track_length_m=100.0, max_candidates=4)
    assert len(tracks) == 4
    # All 4 tracks are sorted by maximum distance descending
    lengths = [t["length_m"] for t in tracks]
    assert lengths == sorted(lengths, reverse=True)
    # Top tracks by distance include ~10,418m, ~7,683m, ~6,737m
    assert tracks[0]["length_m"] > 10000.0
    assert tracks[2]["length_m"] > 7500.0
    assert tracks[2]["segment_count"] >= 100
    assert tracks[3]["length_m"] > 6500.0
    assert tracks[3]["segment_count"] >= 100
