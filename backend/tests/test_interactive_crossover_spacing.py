"""Interactive crossover placement spacing tests (test_ic_01 to test_ic_09d)."""

from __future__ import annotations

import pytest

from .helpers_interactive import OL_12_53, mk, plan_ok, straight_tracks


def test_ic_01_single_valid_crossover():
    tracks = straight_tracks()
    results, report = plan_ok(
        [mk("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD")], tracks)
    assert report.overall_valid, report.errors
    assert results[0].validation_status == "VALID"


def test_ic_02_known_endpoint():
    tracks = straight_tracks()
    results, report = plan_ok(
        [mk("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD")], tracks)
    assert report.overall_valid, report.errors
    res = results[0]
    assert res.start_chainage == pytest.approx(500.0)
    assert res.end_chainage == pytest.approx(500.0 + OL_12_53, abs=0.01)
    assert res.ol_mm == pytest.approx(97578.0, abs=1.0)
    assert res.f_deg == pytest.approx(4.7636, abs=0.001)
    assert res.track_centre_m == pytest.approx(5.3, abs=0.01)


def test_ic_03_second_valid_after_endpoint():
    tracks = straight_tracks()
    results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 200.0 + OL_12_53 + 54.0,
           "REVERSE"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)
    chk = report.spacing_checks[0]
    assert chk.actual_m == pytest.approx(54.0, abs=0.01)


def test_ic_04_second_too_close_to_endpoint():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 200.0 + OL_12_53 + 10.0,
           "REVERSE"),
    ], tracks)
    assert not report.overall_valid
    chk = report.spacing_checks[0]
    assert chk.actual_m == pytest.approx(10.0, abs=0.01)
    assert chk.deficit_m == pytest.approx(44.0, abs=0.01)


def test_ic_05_same_direction_violation():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 1000.0, "FORWARD"),
        mk("C2", "LOOP_1", "MAIN_LINE", 1005.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    chk = report.spacing_checks[0]
    assert chk.required_m == pytest.approx(13.0)
    assert chk.actual_m == pytest.approx(5.0)


def test_ic_06_opposite_direction_violation():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 175.709, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 229.709, "REVERSE"),
    ], tracks)
    assert not report.overall_valid
    chk = report.spacing_checks[0]
    assert chk.required_m == pytest.approx(54.0)
    assert chk.actual_m == pytest.approx(43.578, abs=0.05)


def test_ic_07_sharing_main_line():
    tracks = straight_tracks()
    results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 175.709, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 327.287, "REVERSE"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)


def test_ic_08_disjoint_tracks():
    tracks = straight_tracks()
    aux1 = [(x, 20.0) for x, _ in tracks["MAIN_LINE"]]
    aux2 = [(x, 25.3) for x, _ in tracks["MAIN_LINE"]]
    tracks = dict(tracks, AUX_1=aux1, AUX_2=aux2)
    results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD"),
        mk("C2", "AUX_1", "AUX_2", 900.0, "FORWARD"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)


def test_ic_08b_disjoint_same_start_valid():
    tracks = straight_tracks()
    xs = [p[0] for p in tracks["MAIN_LINE"]]
    tracks = dict(tracks, MAIN_LINE_1=[(x, 10.6) for x in xs])
    results, report = plan_ok([
        mk("C4", "LOOP_2", "MAIN_LINE", 1206.71, "FORWARD"),
        mk("C5", "LOOP_1", "MAIN_LINE_1", 1206.71, "REVERSE"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)


def test_ic_08c_same_pair_split_by_disjoint_still_caught():
    tracks = straight_tracks()
    xs = [p[0] for p in tracks["MAIN_LINE"]]
    tracks = dict(tracks, MAIN_LINE_1=[(x, 10.6) for x in xs])
    _results, report = plan_ok([
        mk("A", "LOOP_1", "MAIN_LINE_1", 500.0, "FORWARD"),
        mk("B", "LOOP_2", "MAIN_LINE", 501.0, "FORWARD"),
        mk("C", "LOOP_1", "MAIN_LINE_1", 505.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any(a == "A" and b == "C"
               for a, b in [(c.a_id, c.b_id) for c in report.spacing_checks
                            if not c.valid])


def test_ic_09_footprint_overlap_rejected():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        mk("C2", "LOOP_1", "MAIN_LINE", 260.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("overlap" in e.lower() for e in report.errors)


def test_ic_09b_disjoint_identical_footprints_valid():
    tracks = straight_tracks()
    xs = [p[0] for p in tracks["MAIN_LINE"]]
    tracks = dict(tracks, MAIN_LINE_1=[(x, 10.6) for x in xs])
    results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE_1", 359.13, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 359.13, "FORWARD"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)
    assert all(c.valid for c in report.footprint_checks)


def test_ic_09c_same_strip_identical_footprints_invalid():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 359.13, "FORWARD"),
        mk("C2", "LOOP_1", "MAIN_LINE", 359.13, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("overlap" in e.lower() for e in report.errors)


def test_ic_09d_same_strip_split_by_disjoint_still_caught():
    tracks = straight_tracks()
    xs = [p[0] for p in tracks["MAIN_LINE"]]
    tracks = dict(tracks, MAIN_LINE_1=[(x, 10.6) for x in xs])
    _results, report = plan_ok([
        mk("A", "LOOP_1", "MAIN_LINE_1", 500.0, "FORWARD"),
        mk("B", "MAIN_LINE", "LOOP_2", 501.0, "FORWARD"),
        mk("C", "LOOP_1", "MAIN_LINE_1", 505.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any(a == "A" and c == "C" and not chk.valid
               for chk in report.footprint_checks
               for a, c in [(chk.a_id, chk.b_id)])
