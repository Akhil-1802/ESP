"""Marker collectors for station-relative chainage annotations."""

from __future__ import annotations

import math
from typing import List, Tuple

from common.chainage import StationDatum
from common.geometry import nearest_point_on_alignment, point_at_chainage, polyline_length
from platform_gen.track import _extract_points as _pts

Point = Tuple[float, float]

__all__ = [
    "station_centres_from_dxf",
    "determine_side",
    "determine_track_side",
    "collect_platform_ends",
    "collect_srj_turnout_crossover",
    "collect_siding",
    "collect_fm",
    "collect_dead_ends",
    "collect_fob",
    "collect_optional_layers",
]


def station_centres_from_dxf(doc) -> list:
    """Centroids of STATION-BUILDING outlines (largest first)."""
    centres: list = []
    try:
        entities = list(doc.modelspace())
    except Exception:
        return []
    for entity in entities:
        try:
            if entity.dxf.layer != "STATION-BUILDING":
                continue
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            pts = _pts(entity) if _pts is not None else list(entity.get_points())
            pts = [(float(p[0]), float(p[1])) for p in pts]
            if len(pts) < 3:
                continue
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2.0
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            centres.append((area, (cx, cy)))
        except Exception:
            continue
    centres.sort(key=lambda item: item[0], reverse=True)
    return [c for _, c in centres]


def _clean_pts(pts) -> list:
    return [(float(p[0]), float(p[1])) for p in (pts or [])]


def determine_side(
    pt: Point,
    main_line_points: list | None = None,
    config=None,
    host_track: str | None = None,
    configured_side: str | None = None,
) -> str:
    """Determine whether a point lies on the LEFT or RIGHT side of main alignment."""
    if configured_side:
        s = str(configured_side).strip().upper()
        if s in ("LEFT", "RIGHT"):
            return s
    if host_track and config is not None:
        ht = str(host_track).upper()
        for item in list(getattr(config, "loops", None) or []) + list(
            getattr(config, "additional_lines", None) or []
        ):
            if getattr(item, "name", "").upper() == ht and getattr(item, "side", None):
                return str(item.side).strip().upper()
        for sid in list(getattr(config, "sidings", None) or []):
            if getattr(sid, "source_track", "").upper() == ht and getattr(sid, "side", None):
                return str(sid.side).strip().upper()
    if main_line_points and len(main_line_points) >= 2:
        try:
            cleaned = [(float(p[0]), float(p[1])) for p in main_line_points]
            proj = nearest_point_on_alignment(cleaned, (float(pt[0]), float(pt[1])))
            st = point_at_chainage(cleaned, float(proj.chainage))
            tx, ty = st.tangent
            an = math.hypot(tx, ty) or 1.0
            tx, ty = tx / an, ty / an
            vx, vy = float(pt[0]) - float(proj.point[0]), float(pt[1]) - float(proj.point[1])
            lat_off = -ty * vx + tx * vy
            if lat_off < -0.05:
                return "RIGHT"
            elif lat_off > 0.05:
                return "LEFT"
        except Exception:
            pass
    return "LEFT"


def determine_track_side(
    track_name: str | None,
    config,
    default_to: str | None = None,
    configured_side: str | None = None,
    pt: Point | None = None,
    main_line_points: list | None = None,
) -> str:
    """Look up or compute side (LEFT/RIGHT) for a given track name."""
    if configured_side:
        s = str(configured_side).strip().upper()
        if s in ("LEFT", "RIGHT"):
            return s
    if track_name:
        tn = str(track_name).upper()
        for item in list(getattr(config, "loops", None) or []) + list(
            getattr(config, "additional_lines", None) or []
        ):
            if getattr(item, "name", "").upper() == tn and getattr(item, "side", None):
                return str(item.side).strip().upper()
        for sid in list(getattr(config, "sidings", None) or []):
            if getattr(sid, "source_track", "").upper() == tn and getattr(sid, "side", None):
                return str(sid.side).strip().upper()
        if "MAIN" in tn and default_to:
            dt = str(default_to).upper()
            for item in list(getattr(config, "loops", None) or []) + list(
                getattr(config, "additional_lines", None) or []
            ):
                if getattr(item, "name", "").upper() == dt and getattr(item, "side", None):
                    return str(item.side).strip().upper()
            for sid in list(getattr(config, "sidings", None) or []):
                if getattr(sid, "source_track", "").upper() == dt and getattr(sid, "side", None):
                    return str(sid.side).strip().upper()
    if pt is not None:
        return determine_side(pt, main_line_points=main_line_points, config=config, host_track=track_name)
    return "LEFT"


def collect_platform_ends(doc, tracks: dict, datum: StationDatum, config, main_line_points: list) -> list:
    """Collect platform ends (PF END) and stair far ends (RAMP END)."""
    out: list = []
    pf_ends: list = []
    try:
        entities = list(doc.modelspace())
    except Exception:
        return out

    platforms: list = []
    stair_layers: set = set()
    for req in list(getattr(config, "platforms", None) or []):
        try:
            host = getattr(req, "track_layer", None) or getattr(
                getattr(req, "config", None), "track_layer", None
            )
            cfg = getattr(req, "config", None)
            out_layer = getattr(cfg, "output_layer", None)
            stair_layer = getattr(cfg, "stair_layer", None) or "PLATFORM-STAIRS"
            req_side = getattr(req, "side", None) or getattr(cfg, "side", None)
            if not host or host not in tracks or not out_layer:
                continue
            stair_layers.add(str(stair_layer))
            polys = []
            for entity in entities:
                try:
                    if entity.dxf.layer != out_layer or entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                        continue
                    pts = _pts(entity)
                    if len(pts) >= 3:
                        polys.append([(float(p[0]), float(p[1])) for p in pts])
                except Exception:
                    continue
            if not polys:
                continue
            outline = max(polys, key=len)
            cx = sum(p[0] for p in outline) / len(outline)
            cy = sum(p[1] for p in outline) / len(outline)
            pf_side = determine_side((cx, cy), main_line_points=main_line_points, config=config, host_track=host, configured_side=req_side)
            platforms.append((host, out_layer, stair_layer, outline, (cx, cy), pf_side))
        except Exception:
            continue

    for host, _out_layer, _stair_layer, outline, (cx, cy), pf_side in platforms:
        try:
            host_pts = _clean_pts(tracks[host])
            proj_c = nearest_point_on_alignment(host_pts, (cx, cy))
            ref = point_at_chainage(
                host_pts, min(max(float(proj_c.chainage), 0.0), float(polyline_length(host_pts)))
            )
            ax, ay = ref.tangent
            an = math.hypot(ax, ay) or 1.0
            ax, ay = ax / an, ay / an
            s_vals = [(p[0] - cx) * ax + (p[1] - cy) * ay for p in outline]
            for extreme in (min(s_vals), max(s_vals)):
                band = [p for p, s in zip(outline, s_vals) if abs(s - extreme) < 2.0]
                if not band:
                    continue
                ex = sum(p[0] for p in band) / len(band)
                ey = sum(p[1] for p in band) / len(band)
                proj = nearest_point_on_alignment(host_pts, (ex, ey))
                base = (float(proj.point[0]), float(proj.point[1]))
                try:
                    st = point_at_chainage(host_pts, float(proj.chainage))
                    tan = st.tangent
                except Exception:
                    tan = ref.tangent
                rel = datum.relative_for_track(host, float(proj.chainage))
                out.append((base, tan, float(rel), "PF END", pf_side))
                pf_ends.append((host, float(proj.chainage)))
        except Exception:
            continue

    stair_outlines: list = []
    for entity in entities:
        try:
            if str(entity.dxf.layer) not in stair_layers:
                continue
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            try:
                closed = bool(getattr(entity, "is_closed", False))
            except Exception:
                closed = False
            try:
                if not closed and not (int(entity.dxf.get("flags", 0)) & 1):
                    continue
            except Exception:
                pass
            pts = _pts(entity)
            cleaned = [(float(p[0]), float(p[1])) for p in pts]
            if len(cleaned) >= 5 and cleaned[0] == cleaned[-1]:
                cleaned = cleaned[:-1]
            if len(cleaned) != 4:
                continue
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(cleaned, cleaned[1:] + cleaned[:1]))) / 2.0
            if area < 1.0:
                continue
            stair_outlines.append(cleaned)
        except Exception:
            continue

    for rect in stair_outlines:
        try:
            best = None
            for host, _ol, _sl, _outline, (pcx, pcy), pf_side in platforms:
                scx = sum(p[0] for p in rect) / len(rect)
                scy = sum(p[1] for p in rect) / len(rect)
                dist = math.hypot(scx - pcx, scy - pcy)
                if best is None or dist < best[0]:
                    best = (dist, host, (pcx, pcy), pf_side)
            if best is None:
                continue
            _dist, host, (pcx, pcy), pf_side = best
            host_pts = _clean_pts(tracks[host])
            edges = [(rect[i], rect[(i + 1) % 4]) for i in range(4)]
            edges.sort(key=lambda e: math.hypot(e[0][0] - e[1][0], e[0][1] - e[1][1]))
            shorts = edges[:2]
            mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in shorts]
            mids.sort(key=lambda m: math.hypot(m[0] - pcx, m[1] - pcy), reverse=True)
            far = mids[0]
            proj = nearest_point_on_alignment(host_pts, far)
            try:
                abs_ch = float(proj.chainage)
            except Exception:
                continue
            if any(h == host and abs(abs_ch - pe) < 1.0 for h, pe in pf_ends):
                continue
            base = (float(proj.point[0]), float(proj.point[1]))
            try:
                st = point_at_chainage(host_pts, float(proj.chainage))
                tan = st.tangent
            except Exception:
                tan = (1.0, 0.0)
            rel = datum.relative_for_track(host, float(proj.chainage))
            out.append((base, tan, float(rel), "RAMP END", pf_side))
        except Exception:
            continue
    return out


def _point_on_track_helper(tracks: dict, track: str, main_ch: float, extents: dict):
    pts = tracks.get(track)
    if pts is None or len(list(pts)) < 2:
        return None
    try:
        ext = (extents or {}).get(track)
        local = float(main_ch) if ext is None else float(main_ch) - float(ext[0])
        total = polyline_length(_clean_pts(pts))
        local = min(max(float(local), 0.0), float(total))
        return point_at_chainage(_clean_pts(pts), local)
    except Exception:
        return None


def collect_srj_turnout_crossover(
    tracks: dict,
    extents: dict,
    datum: StationDatum,
    crossover_results: list,
    siding_results: list,
    config,
    main_line_points: list,
) -> list:
    """Collect SRJ markers from crossovers and siding turnouts."""
    out: list = []
    for res in crossover_results:
        try:
            from_track = getattr(res, "from_track", None)
            to_track = getattr(res, "to_track", None)
            start_main = float(getattr(res, "chainage", getattr(res, "start_chainage", 0.0)))
            placement = str(getattr(res, "placement", "") or "").strip().upper()
            if placement not in ("AHEAD", "BEHIND"):
                direction = str(getattr(res, "direction", "FORWARD") or "FORWARD").strip().upper()
                placement = "BEHIND" if direction in ("REVERSE", "BEHIND", "REV", "R") else "AHEAD"
            try:
                second_main = float(res.end_chainage if placement == "AHEAD" else res.start_chainage)
            except (TypeError, ValueError, AttributeError):
                continue
            sp_from = _point_on_track_helper(tracks, from_track, start_main, extents)
            sp_to = _point_on_track_helper(tracks, to_track, second_main, extents)
            side_from = determine_track_side(
                from_track, config, default_to=to_track, pt=(sp_from.point if sp_from else None), main_line_points=main_line_points
            )
            side_to = determine_track_side(
                to_track, config, default_to=from_track, pt=(sp_to.point if sp_to else None), main_line_points=main_line_points
            )
            if sp_from is not None:
                out.append((sp_from.point, sp_from.tangent, datum.relative_for_main(start_main), "SRJ", side_from))
            if sp_to is not None:
                out.append((sp_to.point, sp_to.tangent, datum.relative_for_main(second_main), "SRJ", side_to))
        except Exception:
            continue

    for item in siding_results:
        try:
            spec, _result = item
            source = getattr(spec, "source_track", None)
            s_side = determine_track_side(
                source, config, configured_side=getattr(spec, "side", None), main_line_points=main_line_points
            )
            start_main = float(getattr(spec, "start_chainage_m", 0.0))
            sp = _point_on_track_helper(tracks, source, start_main, extents)
            if sp is not None:
                out.append((sp.point, sp.tangent, datum.relative_for_main(start_main), "SRJ", s_side))
        except Exception:
            continue
    return out


def collect_siding(tracks: dict, extents: dict, datum: StationDatum, siding_results: list, config, main_line_points: list) -> list:
    """Collect siding start SRJs."""
    out: list = []
    for item in siding_results:
        try:
            spec, _result = item
            source = getattr(spec, "source_track", None)
            s_side = determine_track_side(
                source, config, configured_side=getattr(spec, "side", None), main_line_points=main_line_points
            )
            start_main = float(getattr(spec, "start_chainage_m", 0.0))
            sp = _point_on_track_helper(tracks, source, start_main, extents)
            if sp is not None:
                out.append((sp.point, sp.tangent, datum.relative_for_main(start_main), "SRJ", s_side))
        except Exception:
            continue
    return out


def collect_fm(datum: StationDatum, fouling_marks: list, config, main_line_points: list) -> list:
    """Collect fouling marks (FM)."""
    out: list = []
    for mark in fouling_marks:
        try:
            px, py = float(mark.point[0]), float(mark.point[1])
            ox, oy = float(mark.other_point[0]), float(mark.other_point[1])
            base = ((px + ox) / 2.0, (py + oy) / 2.0)
            tan = mark.display_tangent or mark.tangent
            rel = datum.relative_for_main(float(mark.chainage_main))
            fm_side = determine_side(base, main_line_points=main_line_points, config=config)
            out.append((base, (float(tan[0]), float(tan[1])), float(rel), "FM", fm_side))
        except Exception:
            continue
    return out


def collect_dead_ends(doc, tracks_for_datum: dict, datum: StationDatum, config, main_line_points: list) -> list:
    """Tips of `]` dead-end markers (OVER_RUN / SIDING_*)."""
    out: list = []
    try:
        entities = list(doc.modelspace())
    except Exception:
        return out
    for entity in entities:
        try:
            layer = str(entity.dxf.layer or "")
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            upper = layer.upper()
            if not (upper == "OVER_RUN" or upper.startswith("SIDING")):
                continue
            try:
                raw = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            except Exception:
                continue
            if len(raw) != 4:
                continue
            bar = math.hypot(raw[1][0] - raw[2][0], raw[1][1] - raw[2][1])
            cap_a = math.hypot(raw[0][0] - raw[1][0], raw[0][1] - raw[1][1])
            cap_b = math.hypot(raw[3][0] - raw[2][0], raw[3][1] - raw[2][1])
            if not (3.0 <= bar <= 5.0 and 0.8 <= cap_a <= 1.8 and 0.8 <= cap_b <= 1.8):
                continue
            tip = ((raw[1][0] + raw[2][0]) / 2.0, (raw[1][1] + raw[2][1]) / 2.0)
            best = None
            for name, pts in (tracks_for_datum or {}).items():
                try:
                    cleaned = _clean_pts(pts)
                    if len(cleaned) < 2:
                        continue
                    proj = nearest_point_on_alignment(cleaned, tip)
                    if best is None or proj.distance < best[0]:
                        st = point_at_chainage(cleaned, float(proj.chainage))
                        best = (float(proj.distance), name, float(proj.chainage), st.tangent)
                except Exception:
                    continue
            if best is None:
                continue
            _dist, name, abs_ch, tan = best
            rel = datum.relative_for_track(name, abs_ch)
            de_side = determine_side(tip, main_line_points=main_line_points, config=config, host_track=name)
            out.append((tip, (float(tan[0]), float(tan[1])), float(rel), "DE", de_side))
        except Exception:
            continue
    return out


def collect_fob(tracks, extents, datum) -> list:
    """FOB chainage labels are disabled -- always returns no markers."""
    return []


def collect_optional_layers(doc, tracks_for_datum: dict, datum: StationDatum, config, main_line_points: list) -> list:
    """LC / bridges / gradient posts."""
    out: list = []
    wants = (
        ("LC", ("LC", "LEVEL")),
        ("BRIDGE", ("BRIDGE",)),
        ("GRADIENT", ("GRADIENT", "GRADE", "KM_POST", "KM-POST", "SEJ", "BUFFER")),
    )
    try:
        entities = list(doc.modelspace())
    except Exception:
        return out
    layers_present: dict = {}
    for entity in entities:
        try:
            upper = str(entity.dxf.layer or "").upper()
        except Exception:
            continue
        for tag, keys in wants:
            if tag in layers_present:
                continue
            if any(k in upper for k in keys) and "TRACK" not in upper and "STATION" not in upper and "PLATFORM" not in upper:
                layers_present[tag] = str(entity.dxf.layer)
    for tag, layer in layers_present.items():
        pts: list = []
        for entity in entities:
            try:
                if str(entity.dxf.layer) != layer:
                    continue
                kind = entity.dxftype()
                if kind in ("TEXT", "MTEXT"):
                    ins = entity.dxf.insert
                    pts.append(((float(ins.x), float(ins.y)), None))
                elif kind == "LINE":
                    s, e = entity.dxf.start, entity.dxf.end
                    pts.append((((float(s.x) + float(e.x)) / 2.0, (float(s.y) + float(e.y)) / 2.0), None))
                elif kind in ("LWPOLYLINE", "POLYLINE"):
                    raw = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                    if raw:
                        pts.append(((sum(p[0] for p in raw) / len(raw), sum(p[1] for p in raw) / len(raw)), None))
            except Exception:
                continue
        for base, _ in pts[:50]:
            try:
                best = None
                for name, tpts in (tracks_for_datum or {}).items():
                    try:
                        cleaned = _clean_pts(tpts)
                        if len(cleaned) < 2:
                            continue
                        proj = nearest_point_on_alignment(cleaned, base)
                        if best is None or proj.distance < best[0]:
                            st = point_at_chainage(cleaned, float(proj.chainage))
                            best = (float(proj.distance), name, float(proj.chainage), st.tangent)
                    except Exception:
                        continue
                if best is None:
                    continue
                _d, name, abs_ch, tan = best
                opt_side = determine_side(base, main_line_points=main_line_points, config=config, host_track=name)
                out.append((base, (float(tan[0]), float(tan[1])), datum.relative_for_track(name, abs_ch), tag, opt_side))
            except Exception:
                continue
    return out
