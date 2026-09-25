"""Text look + placement tests: shared Arial styles and 1 m clearance.

Covers: ESP_TEXT and ESP_NUM (Arial.ttf) on labels and dimension values,
dimension values, and overlapping placements getting nudged until the
1 m-inflated boxes are disjoint.
"""

from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest

from common.constants import TEXT_CLEARANCE_M
from common.dxf import (
    add_text,
    draw_arrow_dimension,
    ensure_number_style,
    ensure_text_style,
)
from common.dxf_text import (
    _box_from_entity,
    _boxes_overlap,
    resolve_text_insert,
)
from platform_gen.dxf_io import _add_label
from track.generator import (
    _add_track_label,
    _annotate_overrun,
    _draw_direction_mark,
    _draw_srj_post,
)


def fresh_doc(layers=("T", "D", "O", "SRJ", "DIRECTION", "OVER_RUN", "P")):
    doc = ezdxf.new()
    for name in layers:
        doc.layers.add(name, color=1)
    return doc


def test_styles_use_reference_fonts():
    doc = ezdxf.new()
    assert ensure_text_style(doc) == "ESP_TEXT"
    assert ensure_number_style(doc) == "ESP_NUM"
    assert doc.styles.get("ESP_TEXT").dxf.font.lower() == "arial.ttf"
    assert doc.styles.get("ESP_NUM").dxf.font.lower() == "arial.ttf"


def test_number_style_upgrades_legacy_shx_font():
    doc = ezdxf.new()
    doc.styles.new("ESP_NUM", dxfattribs={"font": "txt.shx"})
    assert ensure_number_style(doc) == "ESP_NUM"
    assert doc.styles.get("ESP_NUM").dxf.font.lower() == "arial.ttf"


def test_letter_labels_use_esp_text():
    doc = fresh_doc()
    pts = [(float(x), 0.0) for x in range(0, 501)]
    add_text(doc, "TBM-176", (10, 10), "T", 1)
    _add_track_label(doc, "LOOP_1", pts, "T", 1)
    _draw_srj_post(doc, (100, 0), (1, 0), False)
    _draw_direction_mark(doc, pts, "UP/DN", True)
    loop = SimpleNamespace(side="LEFT", extend_start_m=120.0, extend_end_m=0.0)
    lpts = [(float(x), 5.3) for x in range(0, 501)]
    _annotate_overrun(doc, loop, lpts, 175.709, 925.709, 55.709, 925.709)
    lbl = SimpleNamespace(text="PLATFORM 1 (550X8.5m)", height=1.0,
                          rotation=0.0, position=(50, 300, 0))
    _add_label(doc, lbl, "P", 1)
    texts = [e for e in doc.modelspace()
             if e.dxftype() in ("TEXT", "MTEXT")]
    assert len(texts) >= 6
    assert {e.dxf.get("style") for e in texts} == {"ESP_TEXT"}


def test_dimension_values_use_number_style():
    doc = fresh_doc()
    draw_arrow_dimension(doc, (0, 0), (27, 0), 2.0, "27.00", "D", 1, 0.8)
    dims = [e for e in doc.modelspace() if e.dxftype() == "DIMENSION"]
    if dims:
        dim = dims[0]
        block = doc.blocks.get(dim.dxf.geometry)
        texts = [e for e in block if e.dxftype() in ("TEXT", "MTEXT")]
        assert texts and texts[0].dxf.style == "ESP_NUM"
    else:
        value = [e for e in doc.modelspace()
                 if e.dxftype() == "TEXT" and e.dxf.text == "27.00"][0]
        assert value.dxf.style == "ESP_NUM"


def test_overlapping_text_is_nudged_clear():
    doc = fresh_doc()
    add_text(doc, "PLATFORM 1 (550X8.5m)", (100, 0), "T", 1)
    placed = resolve_text_insert(doc, "Loop 1", 1.0, 0.0, (102, 0))
    assert abs(placed[0] - 102) + abs(placed[1]) > 1.0
    first = [e for e in doc.modelspace() if e.dxftype() == "TEXT"][0]
    box_a = _box_from_entity(first)
    add_text(doc, "Loop 1", placed, "T", 1)
    second = [e for e in doc.modelspace() if e.dxftype() == "TEXT"][-1]
    assert not _boxes_overlap(box_a, _box_from_entity(second))
    assert TEXT_CLEARANCE_M == pytest.approx(1.0)


def test_clear_spot_is_kept_verbatim():
    doc = fresh_doc()
    placed = resolve_text_insert(doc, "SRJ", 1.0, 0.0, (500, 5))
    assert tuple(placed) == (500, 5)
