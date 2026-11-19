from ...domain.constants import LOOP_CROSSOVER_DISTANCE_M
from ...domain.geometry.operations import polyline_length
from .conversion import build_kml_document


def main_track_center(source, selected_track_id=None, layer="MAIN_TRACK"):
    """Return the midpoint chainage of the longest matching MAIN alignment."""
    doc = build_kml_document(str(source), selected_track_id=selected_track_id)
    best_len = 0.0
    for entity in doc.modelspace():
        if entity.dxf.layer != layer:
            continue
        if entity.dxftype() == "LINE":
            pts = [(entity.dxf.start.x, entity.dxf.start.y),
                   (entity.dxf.end.x, entity.dxf.end.y)]
        elif entity.dxftype() == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in entity.get_points()]
        else:
            continue
        if len(pts) < 2:
            continue
        length = polyline_length(pts)
        if length > best_len:
            best_len = length
    if best_len < LOOP_CROSSOVER_DISTANCE_M:
        raise ValueError(
            f"MAIN track on layer {layer!r} is only {best_len:.1f}m - "
            f"a fixed {LOOP_CROSSOVER_DISTANCE_M:.0f}m loop cannot fit."
        )
    return best_len / 2.0
