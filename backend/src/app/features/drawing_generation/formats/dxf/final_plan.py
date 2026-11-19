"""Orient a completed ESP using the length-weighted main-line best fit."""
import math

import ezdxf
from ezdxf.math import Matrix44


def _horizontal_labels(layout):
    """Resolve text-bearing blocks per instance, then orient labels in world XY."""
    def contains_text(block, visited):
        if block.name in visited:
            return False
        visited = visited | {block.name}
        for item in block:
            if item.dxftype() in ('TEXT', 'MTEXT', 'ATTDEF', 'ATTRIB'):
                return True
            if item.dxftype() == 'INSERT' and (
                item.attribs or contains_text(item.block(), visited)
            ):
                return True
        return False

    def visit(entity):
        kind = entity.dxftype()
        layer = entity.dxf.layer.upper()
        # Gradient captions follow the two slope segments and the marker stem.
        # The modelspace transform already rotates the complete symbol together.
        if layer == 'GRADIENT':
            return
        if kind in ('TEXT', 'MTEXT', 'ATTRIB'):
            if entity.has_xdata('ESP_LABEL'):
                if (1000, 'PLATFORM') in entity.get_xdata('ESP_LABEL'):
                    return
            text = entity.plain_text() if kind == 'MTEXT' else entity.dxf.text
            # The caption runs along the narrow FOB deck, so retain its
            # deck-relative rotation when the complete plan is rotated.
            if text.strip().upper() == 'FOOT OVER BRIDGE':
                return
            # Chainage labels rotate with their marker lines. Station chainages
            # share STATION with names, so identify only its chainage captions.
            if layer == 'CHAINAGE' or (
                layer == 'STATION' and text.strip().upper().startswith(('CH:', 'CH.'))
            ):
                return
        if kind == 'DIMENSION' and layer == 'TRACK_CENTERS':
            # Dimension text lives in its rendered geometry block, not in an
            # INSERT visited below. Rebuild it in the final world coordinates
            # and persist the same policy for subsequent CAD regeneration.
            entity.dxf.text_rotation = 0
            entity.dxf.horizontal_direction = 0
            override = entity.override()
            override.update({'dimtih': 1, 'dimtoh': 1})
            override.render()
        elif kind == 'INSERT' and (entity.attribs or contains_text(entity.block(), set())):
            # Resolve each instance in world coordinates; shared block definitions
            # cannot give horizontal labels to differently rotated references.
            for child in entity.explode(target_layout=layout):
                visit(child)
        elif kind in ('TEXT', 'ATTRIB'):
            # FIT/ALIGNED text derives its direction from two placement points.
            if entity.dxf.get('halign', 0) in (3, 5):
                start = entity.dxf.insert
                end = entity.dxf.align_point
                entity.dxf.align_point = (start.x + start.distance(end), start.y, start.z)
            entity.dxf.rotation = 0
        elif kind == 'MTEXT':
            entity.set_rotation(0)

    for entity in list(layout):
        visit(entity)


def align_final_plan(path: str, document=None) -> float:
    """Rotate all modelspace entities together; return the applied radians.

    Fit the displayed MAIN_LINE, after trimming. Integrating along segments
    makes the fit independent of vertex spacing. Keep its first point fixed.
    """
    doc = document if document is not None else ezdxf.readfile(path)
    mains = list(doc.modelspace().query('LWPOLYLINE[layer=="MAIN_LINE"]'))
    if not mains:
        raise ValueError("Cannot align final plan: MAIN_LINE polyline is missing")
    main = max(mains, key=lambda e: sum(
        math.dist(a[:2], b[:2]) for a, b in zip(list(e), list(e)[1:])
    ))
    pts = [(float(p[0]), float(p[1])) for p in main]
    origin = pts[0]
    local = [(x-origin[0], y-origin[1]) for x, y in pts]
    weight = sx = sy = sxx = syy = sxy = 0.0
    for (x, y), (u, v) in zip(local, local[1:]):
        length = math.hypot(u-x, v-y)
        weight += length
        sx += length*(x+u)/2
        sy += length*(y+v)/2
        sxx += length*(x*x+x*u+u*u)/3
        syy += length*(y*y+y*v+v*v)/3
        sxy += length*(2*x*y+x*v+u*y+2*u*v)/6
    if weight <= 1e-9:
        raise ValueError("Cannot align final plan: main line has zero length")
    xx = sxx/weight-(sx/weight)**2
    yy = syy/weight-(sy/weight)**2
    xy = sxy/weight-sx*sy/weight**2
    angle = 0.5*math.atan2(2*xy, xx-yy)
    # Preserve increasing main-line distance towards positive X.
    dx, dy = local[-1]
    if dx*math.cos(angle)+dy*math.sin(angle) < 0:
        angle += math.pi
    matrix = Matrix44.chain(
        Matrix44.translate(-origin[0], -origin[1], 0),
        Matrix44.z_rotate(-angle),
        Matrix44.translate(origin[0], origin[1], 0),
    )
    for entity in doc.modelspace():
        try:
            entity.transform(matrix)
        except (AttributeError, NotImplementedError) as exc:
            raise ValueError(f"Cannot align DXF entity {entity.dxftype()}") from exc
    _horizontal_labels(doc.modelspace())
    from ...domain.track.cal_layout import finalize_cal_leaders
    finalize_cal_leaders(doc)
    if document is None:
        doc.saveas(path)
    return -angle
