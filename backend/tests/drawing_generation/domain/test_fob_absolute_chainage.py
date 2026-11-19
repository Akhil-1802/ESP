"""Absolute FOB chainage must use the original MAIN survey datum."""
from types import SimpleNamespace

import ezdxf
import pytest

from app.features.drawing_generation.domain.bridges.fob.config import FOBConfig
from app.features.drawing_generation.domain.bridges.fob.deck import generate_fob, resolve_fob_chainage

DATUM = SimpleNamespace(start_km=12, start_m=0)
TRACKS = {"MAIN_LINE": [(0, 0), (2000, 0)],
          "LOOP_1": [(500, 5.3), (1500, 5.3)]}


@pytest.mark.parametrize("raw", ["12+850", "12850", 12850, "12.850 KM", "12850 M"])
def test_absolute_fob_uses_nonzero_main_datum(raw):
    cfg = FOBConfig(position_mode="FIXED", absolute_chainage=raw)
    assert resolve_fob_chainage(cfg, TRACKS, alignment_config=DATUM) == pytest.approx(850)
    # Subsequent rendering reuses the resolved distance without converting a second time.
    assert resolve_fob_chainage(cfg, TRACKS) == pytest.approx(850)


@pytest.mark.parametrize("raw", ["", "nan", "inf", "12+1000", "12+abc"])
def test_invalid_absolute_fob_chainage_is_rejected(raw):
    with pytest.raises(ValueError):
        FOBConfig(position_mode="FIXED", absolute_chainage=raw)


@pytest.mark.parametrize("raw", ["11+999", "14+001"])
def test_absolute_fob_outside_main_is_rejected(raw):
    cfg = FOBConfig(position_mode="FIXED", absolute_chainage=raw)
    with pytest.raises(ValueError, match="outside MAIN"):
        resolve_fob_chainage(cfg, TRACKS, alignment_config=DATUM)


def test_absolute_fob_projects_to_bounded_reference_without_double_subtraction():
    cfg = FOBConfig(reference_track="LOOP_1", position_mode="FIXED", absolute_chainage="12+850",
                    platforms=["P1", "P2"])
    assert resolve_fob_chainage(cfg, TRACKS, alignment_config=DATUM) == pytest.approx(350)
    polygons = {"P1": [(600, 8), (1400, 8), (1400, 11), (600, 11)],
                "P2": [(600, -11), (1400, -11), (1400, -8), (600, -8)]}
    doc = ezdxf.new("R2010")
    outline = generate_fob(doc, TRACKS, {"LOOP_1": (500, 1500)}, polygons, cfg)
    assert (min(p[0] for p in outline) + max(p[0] for p in outline)) / 2 == pytest.approx(850)


def test_absolute_fob_rejects_reference_track_that_does_not_reach_chainage():
    cfg = FOBConfig(reference_track="LOOP_1", position_mode="FIXED", absolute_chainage="12+100")
    with pytest.raises(ValueError, match="does not cross"):
        resolve_fob_chainage(cfg, TRACKS, alignment_config=DATUM)


def test_absolute_fob_handles_negative_start():
    cfg = FOBConfig(position_mode="FIXED", absolute_chainage="0+050")
    assert resolve_fob_chainage(cfg, TRACKS, alignment_config=SimpleNamespace(start_km="-0", start_m=100)) == pytest.approx(150)


def test_absolute_fob_requires_fixed_mode_and_datum():
    with pytest.raises(ValueError, match="FIXED"):
        FOBConfig(position_mode="OFFSET", absolute_chainage="12+850")
    cfg = FOBConfig(position_mode="FIXED", absolute_chainage="12+850")
    with pytest.raises(ValueError, match="start datum"):
        resolve_fob_chainage(cfg, TRACKS)
