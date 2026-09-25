"""N-crossover engine validation tests (TEST 1..13)."""

from __future__ import annotations

import math
import pytest

from common.constants import (
    OPPOSITE_DIRECTION_MIN_SEPARATION_M,
    SAME_DIRECTION_MIN_SEPARATION_M,
)
from track.crossover.geometry import compute_crossover_params
from .helpers_crossover import plan_ok, req, straight_tracks


def test_1_single_crossover_valid():
    tracks = straight_tracks()
    results, report = plan_ok(
        [req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD")], tracks)
    assert report.overall_valid, report.errors
    assert len(results) == 1
    r = results[0]
    assert r.validation_status == "VALID"
    assert math.hypot(r.geometry[0][0] - tracks["LOOP_1"][50][0],
                      r.geometry[0][1] - tracks["LOOP_1"][50][1]) < 1.0
    assert len(r.geometry) > 10


def test_2_two_valid_crossovers():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 300.0, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", 700.0, "REVERSE"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)


def test_3_three_valid_crossovers():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", 600.0, "REVERSE"),
        req("C3", "LOOP_2", "MAIN_LINE", 1200.0, "FORWARD"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert len(results) == 3


def test_4_four_valid_crossovers():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", 500.0, "REVERSE"),
        req("C3", "LOOP_2", "MAIN_LINE", 1000.0, "FORWARD"),
        req("C4", "MAIN_LINE", "LOOP_1", 1500.0, "REVERSE"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert len(results) == 4
    assert len(report.spacing_checks) == 3


def test_5_invalid_same_direction_spacing():
    tracks = straight_tracks()
    _results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 1000.0, "FORWARD"),
        req("C2", "LOOP_1", "MAIN_LINE", 1005.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("5.00 m" in e or "deficit" in e.lower() for e in report.errors)
    assert SAME_DIRECTION_MIN_SEPARATION_M == 13.0
    chk = report.spacing_checks[0]
    assert chk.required_m == pytest.approx(13.0)
    assert chk.actual_m == pytest.approx(5.0)
    assert chk.deficit_m == pytest.approx(8.0)


def test_6_invalid_opposite_direction_spacing():
    tracks = straight_tracks()
    _results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 1000.0, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", 1070.0, "REVERSE"),
    ], tracks)
    assert not report.overall_valid
    assert OPPOSITE_DIRECTION_MIN_SEPARATION_M == 54.0
    chk = report.spacing_checks[0]
    assert chk.required_m == pytest.approx(54.0)
    assert chk.actual_m == pytest.approx(27.578, abs=0.01)
    assert chk.deficit_m == pytest.approx(26.422, abs=0.01)
    assert chk.suggested_min_chainage_b == pytest.approx(1151.578, abs=0.01)


def test_7_far_apart_stays_valid():
    tracks = straight_tracks()
    _results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 300.0, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_1", 1400.0, "REVERSE"),
    ], tracks)
    assert report.overall_valid, report.errors
    chk = report.spacing_checks[0]
    assert chk.actual_m == pytest.approx(1002.422, abs=0.01)
    assert chk.required_m == pytest.approx(54.0)
    assert chk.valid


def test_8_footprint_overlap_invalid():
    tracks = straight_tracks()
    _results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 1000.0, "FORWARD"),
        req("C2", "LOOP_1", "MAIN_LINE", 1070.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("overlap" in e.lower() for e in report.errors)
    assert report.spacing_checks[0].valid
    assert any(not c.valid for c in report.footprint_checks)


def test_9_auto_placement():
    tracks = straight_tracks()
    requests = [
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", None, "REVERSE"),
    ]
    assert requests[1].is_auto
    results, report = plan_ok(requests, tracks)
    assert report.overall_valid, report.errors
    c1 = next(r for r in results if r.id == "C1")
    c2 = next(r for r in results if r.id == "C2")
    assert c2.chainage + 1e-9 >= c1.chainage + 54.0
    assert c2.start_chainage >= c1.end_chainage - 1e-9 or \
        c2.end_chainage <= c1.start_chainage + 1e-9 or \
        c2.chainage >= c1.chainage + 54.0
    lo1, hi1 = min(c1.start_chainage, c1.end_chainage), max(c1.start_chainage, c1.end_chainage)
    lo2, hi2 = min(c2.start_chainage, c2.end_chainage), max(c2.start_chainage, c2.end_chainage)
    assert max(lo1, lo2) >= min(hi1, hi2) - 1e-9


def test_10_invalid_chainage():
    tracks = straight_tracks(length=2000.0)
    _results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 5000.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("outside" in e.lower() or "chainage" in e.lower()
               for e in report.errors)


def test_11_nonexistent_track():
    tracks = straight_tracks()
    _results, report = plan_ok([
        req("C1", "LOOP_1", "NO_SUCH_TRACK", 500.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("unknown" in e.lower() or "NO_SUCH_TRACK" in e
               for e in report.errors)


def test_12_turnout_ratio_changes_f_and_ol():
    tracks = straight_tracks()
    p12 = compute_crossover_params(
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD", "1:12"),
        500.0, tracks, {})
    p85 = compute_crossover_params(
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD", "1:8.5"),
        500.0, tracks, {})
    assert p12["f_deg"] == pytest.approx(4.7636, abs=0.01)
    assert p85["f_deg"] == pytest.approx(6.7098, abs=0.01)
    assert p12["ol_mm"] != pytest.approx(p85["ol_mm"])
    assert p12["ol_mm"] > p85["ol_mm"]


def test_13_track_centre_changes_ol():
    narrow = straight_tracks(tc=5.3)
    wide = straight_tracks(tc=6.7)
    p_n = compute_crossover_params(
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD", "1:12"),
        500.0, narrow, {})
    p_w = compute_crossover_params(
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD", "1:12"),
        500.0, wide, {})
    assert p_n["tc_mm"] == pytest.approx(5300.0, abs=5.0)
    assert p_w["tc_mm"] == pytest.approx(6700.0, abs=5.0)
    assert p_w["ol_mm"] > p_n["ol_mm"]
    assert p_n["ol_mm"] == pytest.approx(
        p_n["tc_mm"] * 12.0 + 2.0 * p_n["a_mm"], abs=1.0)
