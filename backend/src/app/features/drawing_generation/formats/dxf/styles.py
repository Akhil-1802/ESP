"""DXF layer, linetype and text style management."""

from __future__ import annotations

from ...domain.constants import (
    BOLD_STYLE_FONT,
    BOLD_STYLE_NAME,
    DEFAULT_COLOR,
    NUMBER_STYLE_FONT,
    NUMBER_STYLE_NAME,
    TEXT_STYLE_FONT,
    TEXT_STYLE_NAME,
)


def ensure_dotted_linetype(doc) -> str:
    """Ensure standard DOTTED / DOT linetype exists in doc."""
    name = "DOTTED"
    for cand in ("DOTTED", "DOT"):
        if cand not in doc.linetypes:
            try:
                doc.linetypes.add(
                    cand,
                    pattern=[0.5, 0.0, -0.5],
                    description="Dotted . . . . . . . . . . . . . . .",
                )
            except Exception:
                pass
        else:
            name = cand
    return name


def ensure_dashed_linetype(doc) -> str:
    """Ensure standard DASHED linetype exists in doc."""
    name = "DASHED"
    if name not in doc.linetypes:
        try:
            doc.linetypes.add(
                name,
                pattern=[2.0, 1.25, -0.75],
                description="Dashed __ __ __ __ __ __ __",
            )
        except Exception:
            pass
    return name


def ensure_custom_linetype_5(doc) -> str:
    """Ensure standard '5' linetype exists in doc."""
    name = "5"
    if name not in doc.linetypes:
        try:
            doc.linetypes.add(
                name,
                pattern=[7.5, 5.0, -2.5],
                description="5 __ __ __ __ __",
            )
        except Exception:
            pass
    return name


def ensure_layer(doc, name: str, color: int = DEFAULT_COLOR, linetype: str | None = None):
    """Ensure layer exists with given color and linetype."""
    if linetype:
        u = str(linetype).strip().upper()
        if u in ("DOTTED", "DOT"):
            ensure_dotted_linetype(doc)
        elif u == "DASHED":
            ensure_dashed_linetype(doc)
        elif u == "5":
            ensure_custom_linetype_5(doc)
    if name not in doc.layers:
        kwargs = {"color": color}
        if linetype:
            kwargs["linetype"] = linetype
        doc.layers.add(name=name, **kwargs)
    elif linetype:
        try:
            doc.layers.get(name).dxf.linetype = linetype
        except Exception:
            pass


def ensure_text_style(doc) -> str:
    """Ensure the shared ESP text style exists; return its name."""
    try:
        if TEXT_STYLE_NAME not in doc.styles:
            doc.styles.new(
                TEXT_STYLE_NAME, dxfattribs={"font": TEXT_STYLE_FONT}
            )
    except Exception:
        pass
    return TEXT_STYLE_NAME


def ensure_number_style(doc) -> str:
    """Ensure the thin number style exists; return its name."""
    try:
        if NUMBER_STYLE_NAME not in doc.styles:
            doc.styles.new(
                NUMBER_STYLE_NAME, dxfattribs={"font": NUMBER_STYLE_FONT}
            )
        else:
            doc.styles.get(NUMBER_STYLE_NAME).dxf.font = NUMBER_STYLE_FONT
    except Exception:
        pass
    return NUMBER_STYLE_NAME


def ensure_bold_text_style(doc) -> str:
    """Ensure the bold label style exists; return its name."""
    try:
        if BOLD_STYLE_NAME not in doc.styles:
            doc.styles.new(
                BOLD_STYLE_NAME, dxfattribs={"font": BOLD_STYLE_FONT}
            )
    except Exception:
        return TEXT_STYLE_NAME
    return BOLD_STYLE_NAME
