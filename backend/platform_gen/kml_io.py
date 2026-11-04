"""Convert KML track centerlines into a local metre-based DXF."""

from __future__ import annotations

import math
from pathlib import Path
import xml.etree.ElementTree as ET

import ezdxf

try:
    from pyproj import Transformer
    from shapely.geometry import LineString
    from shapely.ops import linemerge, snap, unary_union
except ImportError:
    Transformer = None

JOIN_TOLERANCE_M = 0.01


def _calculate_track_angle(points):
    """Calculate the angle of the track from start to end point.
    Returns the angle in radians."""
    if len(points) < 2:
        return 0.0
    start = points[0]
    end = points[-1]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return math.atan2(dy, dx)


def _rotate_point(point, angle, origin=(0, 0)):
    """Rotate a point around an origin by the given angle (radians)."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    px = point[0] - origin[0]
    py = point[1] - origin[1]
    rotated_x = px * cos_a - py * sin_a
    rotated_y = px * sin_a + py * cos_a
    return (rotated_x + origin[0], rotated_y + origin[1])


def _align_to_x_axis(points_list):
    """Rotate all points so that the track is parallel to the x-axis.
    
    Args:
        points_list: List of point sequences (each sequence is a list of (x, y) tuples)
    
    Returns:
        Tuple of (rotated_points_list, rotation_angle, rotation_origin)
    """
    if not points_list or not points_list[0]:
        return points_list, 0.0, (0, 0)
    
    all_points = []
    for points in points_list:
        all_points.extend(points)
    
    if not all_points:
        return points_list, 0.0, (0, 0)
    
    origin = points_list[0][0]
    track_angle = _calculate_track_angle(points_list[0])
    rotation_angle = -track_angle
    
    rotated_list = []
    for points in points_list:
        rotated_points = [_rotate_point(p, rotation_angle, origin) for p in points]
        rotated_list.append(rotated_points)
    
    return rotated_list, rotation_angle, origin


def convert_kml_to_dxf(kml_path: str, dxf_path: str, layer_name: str = "MAIN_TRACK", align_horizontal: bool = True) -> str:
    """Convert KML file containing LineString(s) to a DXF file with LWPOLYLINE.
    
    Coordinates are transformed from WGS84 (lat/lon) to a local UTM projection
    (metres). If multiple connected LineStrings exist, they are merged.
    By default, the track is rotated so it lies parallel to the horizontal (X) axis.
    """
    if Transformer is None:
        raise ImportError("pyproj and shapely are required for KML conversion")

    tree = ET.parse(kml_path)
    root = tree.getroot()

    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    linestrings = root.findall(".//kml:LineString/kml:coordinates", ns)
    if not linestrings:
        linestrings = root.findall(".//LineString/coordinates")
    if not linestrings:
        raise ValueError(f"No LineString coordinates found in {kml_path}")

    raw_lines = []
    all_lons = []
    all_lats = []
    for ls in linestrings:
        coord_text = ls.text.strip()
        pts = []
        for token in coord_text.split():
            parts = token.split(",")
            if len(parts) >= 2:
                lon, lat = float(parts[0]), float(parts[1])
                pts.append((lon, lat))
                all_lons.append(lon)
                all_lats.append(lat)
        if len(pts) >= 2:
            raw_lines.append(pts)

    if not raw_lines:
        raise ValueError("No valid coordinates parsed from KML")

    center_lon = sum(all_lons) / len(all_lons)
    center_lat = sum(all_lats) / len(all_lats)
    utm_zone = int((center_lon + 180) / 6) + 1
    hemisphere = "north" if center_lat >= 0 else "south"
    crs_to = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"

    transformer = Transformer.from_crs("EPSG:4326", crs_to, always_xy=True)

    projected_lines = []
    for line in raw_lines:
        proj_pts = []
        for lon, lat in line:
            x, y = transformer.transform(lon, lat)
            proj_pts.append((x, y))
        projected_lines.append(LineString(proj_pts))

    if len(projected_lines) == 1:
        merged = projected_lines[0]
    else:
        snapped_lines = [projected_lines[0]]
        for line in projected_lines[1:]:
            snapped = snap(line, snapped_lines[-1], JOIN_TOLERANCE_M)
            snapped_lines.append(snapped)
        multi = unary_union(snapped_lines)
        merged = linemerge(multi)

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add(layer_name, color=1)

    points_to_write = []
    if merged.geom_type == "LineString":
        points_to_write.append(list(merged.coords))
    elif merged.geom_type == "MultiLineString":
        longest = max(merged.geoms, key=lambda g: g.length)
        points_to_write.append(list(longest.coords))

    if align_horizontal:
        points_to_write, rot_angle, rot_origin = _align_to_x_axis(points_to_write)
        print(f"   Track aligned to horizontal (rotated by {math.degrees(rot_angle):.1f} deg)")

    for pts in points_to_write:
        msp.add_lwpolyline(pts, dxfattribs={"layer": layer_name, "color": 1})

    out = Path(dxf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))
    return str(out)


def convert_kml_direct(kml_path: str, dxf_path: str) -> str:
    """Convert a KML file directly 1:1 into a metric DXF file (North-up / geographic orientation).

    Preserves all Placemarks, LineStrings, MultiGeometries, layer names, and line colors.
    Does not drop secondary lines, does not take only the main line, and does not rotate.
    """
    if Transformer is None:
        raise ImportError("pyproj and shapely are required for KML conversion")

    tree = ET.parse(kml_path)
    root = tree.getroot()

    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # 1. Parse styles for line colors
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
                val = color_elem.text.strip()
                styles[f"#{s_id}"] = val
                styles[s_id] = val

    # 2. Extract all features and coordinates
    features: list[dict] = []
    all_lons: list[float] = []
    all_lats: list[float] = []

    placemarks = root.findall(".//kml:Placemark", ns) or root.findall(".//Placemark")
    if not placemarks:
        placemarks = [root]

    for idx, pm in enumerate(placemarks, 1):
        name_elem = pm.find("kml:name", ns) if pm.find("kml:name", ns) is not None else pm.find("name")
        pm_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else f"KML_LINE_{idx}"

        color_hex = None
        style_url = pm.find("kml:styleUrl", ns) if pm.find("kml:styleUrl", ns) is not None else pm.find("styleUrl")
        if style_url is not None and style_url.text:
            color_hex = styles.get(style_url.text.strip())
        if not color_hex:
            inline_color = (
                pm.find(".//kml:LineStyle/kml:color", ns)
                if pm.find(".//kml:LineStyle/kml:color", ns) is not None
                else pm.find(".//LineStyle/color")
            )
            if inline_color is not None and inline_color.text:
                color_hex = inline_color.text.strip()

        linestrings = pm.findall(".//kml:LineString/kml:coordinates", ns) or pm.findall(".//LineString/coordinates")
        for ls in linestrings:
            coord_text = ls.text.strip() if ls.text else ""
            pts: list[tuple[float, float]] = []
            for token in coord_text.split():
                parts = token.split(",")
                if len(parts) >= 2:
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                        pts.append((lon, lat))
                        all_lons.append(lon)
                        all_lats.append(lat)
                    except ValueError:
                        continue
            if len(pts) >= 2:
                features.append({
                    "name": pm_name,
                    "color_hex": color_hex,
                    "points": pts,
                })

    if not features or not all_lons:
        raise ValueError(f"No valid coordinate lines found in KML {kml_path}")

    # 3. Local UTM projection (metres)
    center_lon = sum(all_lons) / len(all_lons)
    center_lat = sum(all_lats) / len(all_lats)
    utm_zone = int((center_lon + 180) / 6) + 1
    hemisphere = "north" if center_lat >= 0 else "south"
    crs_to = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"

    transformer = Transformer.from_crs("EPSG:4326", crs_to, always_xy=True)

    # 4. Create DXF and write all lines
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    def _kml_color_to_rgb(hex_str: str | None) -> tuple[int, int, int] | None:
        if not hex_str or len(hex_str) < 6:
            return None
        hex_str = hex_str.strip().lower()
        if len(hex_str) == 8:
            # aabbggrr
            try:
                b = int(hex_str[2:4], 16)
                g = int(hex_str[4:6], 16)
                r = int(hex_str[6:8], 16)
                return (r, g, b)
            except ValueError:
                return None
        elif len(hex_str) == 6:
            try:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                return (r, g, b)
            except ValueError:
                return None
        return None

    def _sanitize_layer_name(name: str) -> str:
        for ch in '<>/\\":;?*|=`':
            name = name.replace(ch, "_")
        return name[:255].strip() or "KML_TRACK"

    created_layers: set[str] = set()

    # 4. Transform all points to metric UTM coordinates and normalize to origin (0, 0)
    transformed_features: list[dict] = []
    min_x = float("inf")
    min_y = float("inf")
    for feat in features:
        proj_pts: list[tuple[float, float]] = []
        for lon, lat in feat["points"]:
            x, y = transformer.transform(lon, lat)
            fx, fy = float(x), float(y)
            proj_pts.append((fx, fy))
            if fx < min_x:
                min_x = fx
            if fy < min_y:
                min_y = fy
        transformed_features.append({
            "name": feat["name"],
            "color_hex": feat["color_hex"],
            "points": proj_pts,
        })

    for feat in transformed_features:
        raw_name = feat["name"]
        layer_name = _sanitize_layer_name(raw_name)
        rgb = _kml_color_to_rgb(feat["color_hex"])

        if layer_name not in created_layers:
            if layer_name not in doc.layers:
                layer = doc.layers.add(layer_name, color=7)
                if rgb:
                    layer.rgb = rgb
            created_layers.add(layer_name)

        norm_pts = [(x - min_x, y - min_y) for x, y in feat["points"]]

        attribs: dict = {"layer": layer_name}
        if rgb:
            attribs["true_color"] = ezdxf.rgb2int(rgb)
        msp.add_lwpolyline(norm_pts, dxfattribs=attribs)

    out = Path(dxf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))
    return str(out)

