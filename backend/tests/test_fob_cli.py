"""FOB interactive CLI tests: _ask_fobs with scripted answers."""

from __future__ import annotations

import pytest

from cli.fobs import _ask_fobs
from config.loader import PlatformRequest
from platform_gen.config import PlatformConfig


def _platforms():
    out = []
    for number, track in ((1, "LOOP_1"), (2, "LOOP_2")):
        out.append(PlatformRequest(track, PlatformConfig(
            source_dxf="s.dxf", output_dxf="o.dxf", track_layer=track,
            output_layer=f"PLATFORM_{number}")))
    return out


def _run(monkeypatch, answers, echo=False, **kw):
    it = iter(answers)

    def fake(prompt=""):
        if echo:
            print(prompt, end="")
        return next(it)

    monkeypatch.setattr("builtins.input", fake)
    return _ask_fobs(["MAIN_LINE", "LOOP_1", "LOOP_2"],
                     _platforms(), 550.0, **kw)


def test_cli_full_answers(monkeypatch, capsys):
    fobs = _run(monkeypatch, echo=True, answers=[
        "1",            # number of FOBs
        "MAIN_LINE",    # reference track
        "2",            # platforms to connect
        "PLATFORM_1", "PLATFORM_2",
        "650",          # reference chainage
        "3",            # width
        "5", "BOTH",    # extension + side
        "20", "LEFT",   # arm on PLATFORM_1
        "0",            # no arm on PLATFORM_2
    ])
    assert len(fobs) == 1
    fob = fobs[0]
    assert fob.reference_track == "MAIN_LINE"
    assert fob.reference_chainage == 650.0
    assert fob.platforms == ["PLATFORM_1", "PLATFORM_2"]
    assert fob.width == 3.0
    assert (fob.extend_start_m, fob.extend_end_m) == (5.0, 5.0)
    assert fob.arms == {"PLATFORM_1": {"length": 20.0, "side": "LEFT"}}
    assert "[275-825]" in capsys.readouterr().out


def test_cli_defaults_and_rescue(monkeypatch):
    fobs = _run(monkeypatch, [
        "1",
        "",             # reference track default -> MAIN_LINE
        "1",            # too few -> re-asked
        "2",
        "PLATFORM_2", "PLATFORM_1",
        "600",          # reference chainage within platform extent
        "",             # width default -> 3.0
        "",             # extension default -> 0.0 (no side asked)
        "", "",         # no arms
    ])
    assert len(fobs) == 1
    fob = fobs[0]
    assert fob.reference_track == "MAIN_LINE"
    assert fob.reference_chainage == 600.0
    assert fob.platforms == ["PLATFORM_2", "PLATFORM_1"]
    assert fob.width == 3.0
    assert (fob.extend_start_m, fob.extend_end_m) == (0.0, 0.0)
    assert fob.arms == {}


def test_cli_zero_fobs(monkeypatch):
    assert _run(monkeypatch, ["0"]) == []


def test_cli_no_platforms_skips(monkeypatch):
    it = iter([])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(it))
    assert _ask_fobs(["MAIN_LINE"], []) == []
