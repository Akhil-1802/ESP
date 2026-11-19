"""Topological track detection and grouping engine for railway KML files.

Correctly chains multi-segment railway tracks (including straight tangents,
transition curves, and circular curve chords) into complete continuous paths.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any

from pyproj import Transformer
from shapely.geometry import LineString

# Distinct high-contrast palette for multi-track visual identification
TRACK_PALETTE = [
    "#00e5ff",  # Vibrant Cyan
    "#00e676",  # Bright Emerald
    "#ffd700",  # Golden Yellow
    "#f50057",  # Vivid Magenta / Rose
    "#ff9100",  # Safety Orange
    "#b388ff",  # Soft Purple / Lavender
    "#00b0ff",  # Light Blue
    "#76ff03",  # Lime
    "#ff3d00",  # Coral Red
    "#e040fb",  # Neon Violet
]


def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def _tangent_vector(pts: list[tuple[float, float]], at_start: bool = True) -> tuple[float, float]:
    if len(pts) < 2:
        return (1.0, 0.0)
    p0, p1 = (pts[0], pts[1]) if at_start else (pts[-2], pts[-1])
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy) or 1.0
    return (dx / length, dy / length)


def _angle_diff_deg(v1: tuple[float, float], v2: tuple[float, float]) -> float:
    dot = max(-1.0, min(1.0, v1[0] * v2[0] + v1[1] * v2[1]))
    return math.degrees(math.acos(dot))


def _remove_short_transverse_steps(
    segments: list[dict[str, Any]],
    transformer_inv: Transformer,
    max_step_m: float = 1.5,
) -> list[dict[str, Any]]:
    """Remove CAD-only 90-degree micro-steps from an ordered polyline handle.

    Some CAD-to-KML exports split one nominal alignment into 5 m chords and
    insert exact 1 m transverse connectors.  The railway line cannot traverse
    such a 90-degree connector; treating it as a loose endpoint gap creates an
    artificial diagonal spike.  Omit only the tightly constrained pattern and
    carry its translation into subsequent chords so the alignment stays
    continuous without smoothing genuine curves.
    """
    if len(segments) < 3:
        return segments

    correction_x = 0.0
    correction_y = 0.0
    cleaned: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        points = segment["m_pts"]
        vector = (
            points[-1][0] - points[0][0],
            points[-1][1] - points[0][1],
        )
        length = math.hypot(vector[0], vector[1])
        is_transverse_step = False
        if 0 < index < len(segments) - 1 and length <= max_step_m:
            prev_vector = _tangent_vector(segments[index - 1]["m_pts"], at_start=False)
            next_vector = _tangent_vector(segments[index + 1]["m_pts"], at_start=True)
            step_vector = _tangent_vector(points, at_start=True)
            entry = _angle_diff_deg(prev_vector, step_vector)
            exit_angle = _angle_diff_deg(step_vector, next_vector)
            through = _angle_diff_deg(prev_vector, next_vector)
            is_transverse_step = (
                80.0 <= entry <= 100.0
                and 80.0 <= exit_angle <= 100.0
                and through <= 2.0
            )

        if is_transverse_step:
            correction_x += vector[0]
            correction_y += vector[1]
            continue

        if correction_x or correction_y:
            shifted = [
                (point[0] - correction_x, point[1] - correction_y)
                for point in points
            ]
            shifted_wgs = [transformer_inv.transform(point[0], point[1]) for point in shifted]
            segment = {**segment, "m_pts": shifted, "wgs84_pts": shifted_wgs}
        cleaned.append(segment)
    return cleaned


def detect_kml_tracks(
    kml_path: str,
    min_track_length_m: float = 50.0,
    endpoint_tol_m: float = 1.5,
    max_angle_diff_deg: float = 35.0,
    include_coords: bool = True,
    max_candidates: int = 4,
) -> list[dict[str, Any]]:
    """Inspect and topologically group connected LineStrings into candidate continuous paths.

    Chains straight segments and curve chords that belong to the same track alignment,
    calculating the true combined length across all constituent segments.

    Args:
        kml_path: Path to the KML file.
        min_track_length_m: Minimum candidate path length to retain (defaults to 50.0 m).
        endpoint_tol_m: Maximum endpoint distance to consider two segments connected.
        max_angle_diff_deg: Maximum tangent angle difference at junction to chain segments.
        include_coords: Whether to include UTM and WGS84 coordinates in the return objects.

    Returns:
        List of candidate track dictionaries sorted by length descending.
    """
    tree = ET.parse(kml_path)
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # 1. Parse styles & colors
    styles: dict[str, str] = {}
    for style_node in root.findall(".//kml:Style", ns) + root.findall(".//Style"):
        s_id = style_node.get("{http://www.opengis.net/kml/2.2}id") or style_node.get("id")
        line_style = (
            style_node.find(".//kml:LineStyle", ns)
            if style_node.find(".//kml:LineStyle", ns) is not None
            else style_node.find(".//LineStyle")
        )
        if line_style is not None and s_id:
            color_elem = (
                line_style.find(".//kml:color", ns)
                if line_style.find(".//kml:color", ns) is not None
                else line_style.find(".//color")
            )
            if color_elem is not None and color_elem.text:
                styles[f"#{s_id}"] = color_elem.text.strip()
                styles[s_id] = color_elem.text.strip()

    # 2. Extract Placemarks and LineStrings
    placemarks = root.findall(".//kml:Placemark", ns) or root.findall(".//Placemark")
    if not placemarks:
        placemarks = [root]

    raw_items: list[dict[str, Any]] = []
    all_lons: list[float] = []
    all_lats: list[float] = []

    for idx, pm in enumerate(placemarks, 1):
        name_elem = pm.find("kml:name", ns) if pm.find("kml:name", ns) is not None else pm.find("name")
        pm_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else f"Segment_{idx}"

        style_url = pm.find("kml:styleUrl", ns) if pm.find("kml:styleUrl", ns) is not None else pm.find("styleUrl")
        s_val = style_url.text.strip() if (style_url is not None and style_url.text) else None
        color_val = styles.get(s_val) if s_val else None

        linestrings = pm.findall(".//kml:LineString/kml:coordinates", ns) or pm.findall(".//LineString/coordinates")
        for ls_idx, ls in enumerate(linestrings):
            coord_text = ls.text.strip() if ls.text else ""
            pts: list[tuple[float, float]] = []
            for token in coord_text.split():
                parts = token.split(",")
                if len(parts) >= 2:
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                        pts.append((lon, lat))
                    except ValueError:
                        continue
            if len(pts) >= 2:
                # Exclude CAD origin scale/legend geometry near (0, 0)
                if all(abs(p[0]) < 1.0 and abs(p[1]) < 1.0 for p in pts):
                    continue
                for lon, lat in pts:
                    all_lons.append(lon)
                    all_lats.append(lat)
                seg_name = pm_name if len(linestrings) == 1 else f"{pm_name} ({ls_idx + 1})"
                raw_items.append({
                    "name": seg_name,
                    "style": s_val,
                    "color_raw": color_val,
                    "wgs84_pts": pts,
                })

    if not raw_items or not all_lons:
        return []

    # 3. UTM projection
    center_lon = sum(all_lons) / len(all_lons)
    center_lat = sum(all_lats) / len(all_lats)
    utm_zone = int((center_lon + 180) / 6) + 1
    hemisphere = "north" if center_lat >= 0 else "south"
    crs_to = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    transformer_fwd = Transformer.from_crs("EPSG:4326", crs_to, always_xy=True)
    transformer_inv = Transformer.from_crs(crs_to, "EPSG:4326", always_xy=True)

    # 4. Convert all items to metric coordinates.  CAD exports commonly split
    # one polyline into many short LineStrings; even a 1 m connector is part of
    # the alignment and must not be discarded.  Dropping it makes the chaining
    # pass bridge directly to the following 5 m chord, producing a visible
    # paired spike in the reconstructed track.
    has_cad_handles_raw = any(
        "[" in item["name"] and "]" in item["name"] for item in raw_items
    )
    min_segment_length = 0.01 if has_cad_handles_raw else 1.5
    metric_segments: list[dict[str, Any]] = []
    for item in raw_items:
        m_pts = [transformer_fwd.transform(lon, lat) for lon, lat in item["wgs84_pts"]]
        geom = LineString(m_pts)
        seg_len = float(geom.length)
        if seg_len >= min_segment_length:
            metric_segments.append({
                "id": len(metric_segments),
                "name": item["name"],
                "style": item["style"],
                "length": seg_len,
                "m_pts": m_pts,
                "wgs84_pts": item["wgs84_pts"],
            })

    # 5. Group by Placemark base handle/layer if CAD handles are present
    has_cad_handles = any("[" in seg["name"] and "]" in seg["name"] for seg in metric_segments)
    by_handle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if has_cad_handles:
        for seg in metric_segments:
            base_name = seg["name"].split(" (")[0].strip()
            by_handle[base_name].append(seg)
        for handle_name, segments in list(by_handle.items()):
            by_handle[handle_name] = _remove_short_transverse_steps(
                segments, transformer_inv
            )
    else:
        for seg in metric_segments:
            by_handle["all"].append(seg)

    # 6. Chain connected segments into complete continuous paths
    chained_paths: list[dict[str, Any]] = []

    for handle_name, group_segs in by_handle.items():
        used_in_group: set[int] = set()
        # Sort descending by segment length so long tangents anchor the chain
        sorted_indices = sorted(range(len(group_segs)), key=lambda i: group_segs[i]["length"], reverse=True)

        for idx in sorted_indices:
            if idx in used_in_group:
                continue
            used_in_group.add(idx)
            curr_m = list(group_segs[idx]["m_pts"])
            curr_wgs = list(group_segs[idx]["wgs84_pts"])
            curr_names = [group_segs[idx]["name"]]
            chain_count = 1

            # Extend forward from tail
            while True:
                best_i = None
                best_rev = False
                best_d = float("inf")
                tail = curr_m[-1]
                out_v = _tangent_vector(curr_m, at_start=False)

                for o_i in range(len(group_segs)):
                    if o_i in used_in_group:
                        continue
                    d_start = _dist(tail, group_segs[o_i]["m_pts"][0])
                    if d_start <= endpoint_tol_m:
                        in_v = _tangent_vector(group_segs[o_i]["m_pts"], at_start=True)
                        if _angle_diff_deg(out_v, in_v) <= max_angle_diff_deg and d_start < best_d:
                            best_i, best_rev, best_d = o_i, False, d_start

                    d_end = _dist(tail, group_segs[o_i]["m_pts"][-1])
                    if d_end <= endpoint_tol_m:
                        raw_v = _tangent_vector(group_segs[o_i]["m_pts"], at_start=False)
                        in_v = (-raw_v[0], -raw_v[1])
                        if _angle_diff_deg(out_v, in_v) <= max_angle_diff_deg and d_end < best_d:
                            best_i, best_rev, best_d = o_i, True, d_end

                if best_i is not None:
                    used_in_group.add(best_i)
                    chain_count += 1
                    nxt_m = list(reversed(group_segs[best_i]["m_pts"])) if best_rev else list(group_segs[best_i]["m_pts"])
                    nxt_wgs = list(reversed(group_segs[best_i]["wgs84_pts"])) if best_rev else list(group_segs[best_i]["wgs84_pts"])
                    curr_m.extend(nxt_m[1:])
                    curr_wgs.extend(nxt_wgs[1:])
                    curr_names.append(group_segs[best_i]["name"])
                else:
                    break

            # Extend backward from head
            while True:
                best_i = None
                best_rev = False
                best_d = float("inf")
                head = curr_m[0]
                raw_v = _tangent_vector(curr_m, at_start=True)
                in_v = (-raw_v[0], -raw_v[1])

                for o_i in range(len(group_segs)):
                    if o_i in used_in_group:
                        continue
                    d_end = _dist(head, group_segs[o_i]["m_pts"][-1])
                    if d_end <= endpoint_tol_m:
                        out_v = _tangent_vector(group_segs[o_i]["m_pts"], at_start=False)
                        if _angle_diff_deg(out_v, (-in_v[0], -in_v[1])) <= max_angle_diff_deg and d_end < best_d:
                            best_i, best_rev, best_d = o_i, False, d_end

                    d_start = _dist(head, group_segs[o_i]["m_pts"][0])
                    if d_start <= endpoint_tol_m:
                        raw_v2 = _tangent_vector(group_segs[o_i]["m_pts"], at_start=True)
                        out_v = (-raw_v2[0], -raw_v2[1])
                        if _angle_diff_deg(out_v, (-in_v[0], -in_v[1])) <= max_angle_diff_deg and d_start < best_d:
                            best_i, best_rev, best_d = o_i, True, d_start

                if best_i is not None:
                    used_in_group.add(best_i)
                    chain_count += 1
                    prev_m = list(reversed(group_segs[best_i]["m_pts"])) if best_rev else list(group_segs[best_i]["m_pts"])
                    prev_wgs = list(reversed(group_segs[best_i]["wgs84_pts"])) if best_rev else list(group_segs[best_i]["wgs84_pts"])
                    curr_m = prev_m[:-1] + curr_m
                    curr_wgs = prev_wgs[:-1] + curr_wgs
                    curr_names.insert(0, group_segs[best_i]["name"])
                else:
                    break

            total_length = float(LineString(curr_m).length)
            if total_length >= min_track_length_m:
                chained_paths.append({
                    "name": handle_name,
                    "m_pts": curr_m,
                    "wgs84_pts": curr_wgs,
                    "length_m": round(total_length, 2),
                    "segment_count": chain_count,
                    "source_names": curr_names,
                })

    # Sort descending by TRUE chained continuous length
    chained_paths.sort(key=lambda c: c["length_m"], reverse=True)

    # Filter out duplicate overlapping paths (matching endpoints within 1.0m)
    unique_candidates: list[dict[str, Any]] = []

    for p in chained_paths:
        is_dup = False
        for uc in unique_candidates:
            d_ff = _dist(p["m_pts"][0], uc["m_pts"][0])
            d_ll = _dist(p["m_pts"][-1], uc["m_pts"][-1])
            d_fl = _dist(p["m_pts"][0], uc["m_pts"][-1])
            d_lf = _dist(p["m_pts"][-1], uc["m_pts"][0])
            if (d_ff < 1.0 and d_ll < 1.0) or (d_fl < 1.0 and d_lf < 1.0):
                is_dup = True
                break
        if not is_dup:
            unique_candidates.append(p)
        if len(unique_candidates) >= max_candidates:
            break

    if not unique_candidates and chained_paths:
        unique_candidates = chained_paths[:max_candidates]

    result: list[dict[str, Any]] = []
    for idx, c in enumerate(unique_candidates[:max_candidates]):
        color = TRACK_PALETTE[idx % len(TRACK_PALETTE)]
        start_pt = c["wgs84_pts"][0]
        end_pt = c["wgs84_pts"][-1]
        cand: dict[str, Any] = {
            "candidate_id": f"path_{idx}",
            "id": idx,
            "name": f"Path {idx + 1}",
            "cad_name": c["name"] if c["name"] != "all" else "",
            "length_m": c["length_m"],
            "segment_count": c["segment_count"],
            "points_count": len(c["m_pts"]),
            "color": color,
            "classification": "Main Line" if idx == 0 else "Other",
            "start_coord": [round(start_pt[0], 6), round(start_pt[1], 6)],
            "end_coord": [round(end_pt[0], 6), round(end_pt[1], 6)],
            "source_names": c["source_names"][:5],
        }
        if include_coords:
            cand["pts_utm"] = c["m_pts"]
            cand["pts_wgs84"] = c["wgs84_pts"]
        result.append(cand)

    return result
