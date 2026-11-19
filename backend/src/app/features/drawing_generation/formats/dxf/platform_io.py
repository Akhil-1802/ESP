"""Platform DXF writing (1:1 real-world scale).

Primitives (layers, polylines, dimensions) live in common.dxf;
this module keeps only platform-specific writing (outlines, stairs,
labels) so the drawing style stays in one place.
"""

from __future__ import annotations

from ezdxf.document import Drawing

from ...domain.platform.config import PlatformConfig
from ...domain.platform.models import PlatformResult
from .primitives import add_polyline as _add_polyline
from .primitives import draw_arrow_dimension
from .styles import ensure_layer as _ensure_layer
from .styles import ensure_text_style as _ensure_text_style
from .text import resolve_text_insert as _resolve_text_insert


def _add_label(doc: Drawing, label, layer: str, color: int):
    if 'ESP_LABEL' not in doc.appids:
        doc.appids.new('ESP_LABEL')
    if doc.dxfversion >= "AC1015":
        pos = _resolve_text_insert(
            doc, label.text, label.height, label.rotation, label.position, anchor="middle-center"
        )
        mtext = doc.modelspace().add_mtext(
            label.text,
            dxfattribs={
                "layer": layer,
                "color": color,
                "style": _ensure_text_style(doc),
                "char_height": label.height,
                "rotation": label.rotation,
            },
        )
        mtext.set_location(pos, attachment_point=5)
        mtext.set_xdata('ESP_LABEL', [(1000, 'PLATFORM')])
        return mtext
    pos = _resolve_text_insert(
        doc, label.text.replace("\\P", " "), label.height, label.rotation, label.position
    )
    text = doc.modelspace().add_text(
        label.text.replace("\\P", " "),
        dxfattribs={
            "layer": layer,
            "color": color,
            "style": _ensure_text_style(doc),
            "height": label.height,
            "rotation": label.rotation,
            "insert": (pos[0], pos[1], pos[2] if len(tuple(pos)) >= 3 else 0),
        },
    )
    text.set_xdata('ESP_LABEL', [(1000, 'PLATFORM')])
    return text


def write_platform(doc: Drawing, result: PlatformResult, cfg: PlatformConfig) -> None:
    """Write platform outline, stairs, labels and dimensions to DXF."""
    _ensure_layer(doc, cfg.output_layer, cfg.platform_color)
    _ensure_layer(doc, cfg.text_layer, cfg.platform_color)

    msp = doc.modelspace()

    # --- platform outline, true scale, closed polyline -----------------
    outline_pts = [(p[0], p[1]) for p in result.outline]
    _add_polyline(
        doc,
        outline_pts,
        cfg.output_layer,
        cfg.platform_color,
        close=True,
    )

    if cfg.add_hatch:
        if doc.dxfversion < "AC1015":
            raise ValueError("Interior hatch requires a DXF version AC1015 (R2000) or newer")
        hatch = msp.add_hatch(color=cfg.platform_color, dxfattribs={"layer": cfg.output_layer})
        hatch.set_pattern_fill(cfg.hatch_pattern, scale=1.0)
        hatch.paths.add_polyline_path(outline_pts, is_closed=True)

    # --- stairs -------------------------------------------------------
    if result.stairs:
        _ensure_layer(doc, cfg.stair_layer, cfg.stair_color)
        for stair in result.stairs:
            stair_pts = [(p[0], p[1]) for p in stair.outline]
            _add_polyline(
                doc,
                stair_pts,
                cfg.stair_layer,
                cfg.stair_color,
                close=True,
            )
            for tread_line in stair.tread_lines:
                p1, p2 = tread_line
                _add_polyline(
                    doc,
                    [(p1[0], p1[1]), (p2[0], p2[1])],
                    cfg.stair_layer,
                    cfg.stair_color,
                    close=False,
                )

    # --- text labels -------------------------------------------------------
    for label in result.labels:
        _add_label(doc, label, cfg.text_layer, cfg.platform_color)

    # --- dimensions (width / clearance) with arrowheads ------------------
    if result.dimensions:
        _ensure_layer(doc, cfg.dimension_layer, cfg.platform_color)
        for dim in result.dimensions:
            draw_arrow_dimension(
                doc,
                dim.p1,
                dim.p2,
                dim.dim_offset,
                dim.text,
                cfg.dimension_layer,
                cfg.platform_color,
                cfg.dim_text_height,
            )


__all__ = ["write_platform"]
