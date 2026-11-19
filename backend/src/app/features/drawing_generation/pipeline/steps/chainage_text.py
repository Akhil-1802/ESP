import math

_TEXT_LIFT = {
    "SRJ": 0.0,
    "FM": 0.0,
    "DE": 0.0,
    "SIDING": 0.0,
    "PF END": 0.0,
    "RAMP END": 0.0,
    "LC": 0.0,
    "BRIDGE": 0.0,
    "BR": 0.0,
}

_STUB_GAP_M = 2.0
_DEDUPE_M = 2.0


def _calc_text_insert(p_base, normal, tangent, dist_start, text_len, rot_deg, side_offset=0.0):
    """Calculate DXF text insertion point along a given normal ray.

    Ensures that regardless of whether rot_deg is parallel (+1) or antiparallel (-1)
    to the normal direction, the text occupies the region [dist_start, dist_start + text_len]
    away from p_base along normal, preventing it from extending back towards or crossing the track.
    """
    nx, ny = normal
    tx, ty = tangent
    vx = math.cos(math.radians(rot_deg))
    vy = math.sin(math.radians(rot_deg))
    dot = vx * nx + vy * ny
    if dot >= 0:
        d_ins = dist_start
    else:
        d_ins = dist_start + text_len
    return (
        p_base[0] + nx * d_ins + tx * side_offset,
        p_base[1] + ny * d_ins + ty * side_offset,
    )
