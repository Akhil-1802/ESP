"""Capture the actual pipeline results before final rotation and cleanup."""

import math

from ..geometry.operations import (
    nearest_point_on_alignment,
    point_at_chainage,
    polyline_length,
)
from ..track.cal_calc import assign_line_numbers
from ..track.directions import resolved_main_directions
from ..track.overrun_metadata import resolved_overruns


def _start_chainage(config):
    """Use the same datum convention as alignment chainage annotations."""
    km = getattr(config, "start_km", None)
    metres = getattr(config, "start_m", None)
    if km is not None:
        sign = -1 if str(km).startswith("-") else 1
        return sign * (abs(float(km))*1000 + abs(float(metres or 0)))
    raw = str(getattr(config, "start_chainage", None) or "0")
    if "+" in raw:
        km, metres = raw.split("+", 1)
        return (-1 if km.startswith("-") else 1) * (abs(float(km or 0))*1000 + abs(float(metres or 0)))
    value = float(raw)
    return value*1000 if abs(value) <= 50 and "." not in raw else value


def capture_snapshot(generator, tracks, doc, main):
    def ch(point):
        return float(nearest_point_on_alignment(main, point).chainage)

    def lateral(point):
        projection = nearest_point_on_alignment(main, point)
        tangent = point_at_chainage(main, projection.chainage).tangent
        dx, dy = point[0] - projection.point[0], point[1] - projection.point[1]
        return -tangent[1] * dx + tangent[0] * dy

    def span(points):
        values = [ch(p) for p in points]
        return [min(values), max(values)]

    result = dict(version=1, tracks=[], platforms=[], crossovers=[], stations=[],
                  buildings=[], bridges=[], overruns=[], north_angle=getattr(doc, "_esp_north_angle_deg", None))
    directions = resolved_main_directions(generator.config, tracks)
    for overrun in resolved_overruns(doc):
        if overrun["track"] in tracks and overrun["length_m"] > 1e-6:
            result["overruns"].append(dict(track=overrun["track"], at_start=overrun["at_start"],
                srj_chainage=ch(overrun["srj"]), tip_chainage=ch(overrun["tip"]),
                length_m=overrun["length_m"]))
    labels = getattr(generator, "_cal_summary", {})
    numbered = {name: (kind, number) for name, kind, number in assign_line_numbers(tracks)}
    for name, points in tracks.items():
        # Use displayed running track geometry after SRJ/overrun cuts and trimming.
        drawn = [list(e.get_points("xy")) for e in doc.modelspace().query("LWPOLYLINE")
                 if e.dxf.layer == name]
        # Extents need segment endpoints, not an O(vertices x MAIN vertices)
        # projection of every sampled point in an already ordered track.
        visible = [p for line in drawn if line for p in (line[0], line[-1])] or [points[0], points[-1]]
        midpoint = point_at_chainage(points, polyline_length(points) / 2).point
        kind, number = numbered.get(name, ("TRACK", len(result["tracks"]) + 1))
        label = labels.get(name)
        start, end = span(visible)
        for overrun in result["overruns"]:
            if overrun["track"] == name:
                if overrun["at_start"]:
                    start = max(start, overrun["srj_chainage"])
                else:
                    end = min(end, overrun["srj_chainage"])
        result["tracks"].append(dict(
            name=name, kind=kind, number=number, offset=lateral(midpoint),
            start=start, end=end,
            label=label[0] if label else name.replace("_", " "),
            length_m=float(label[1]) if label else polyline_length(points),
            direction=directions.get(name, ""),
        ))
    for request, platform in getattr(generator, "_key_plan_platform_results", []):
        cfg = request.config
        start, end = span(platform.near_edge or platform.outline)
        centre = tuple(sum(p[i] for p in platform.outline) / len(platform.outline) for i in (0, 1))
        result["platforms"].append(dict(
            name=cfg.output_layer, track=cfg.track_layer, second_track=cfg.second_track_layer,
            type=getattr(cfg.platform_type, "value", str(cfg.platform_type)),
            side=getattr(cfg.side, "value", str(cfg.side)), start=start, end=end,
            offset=lateral(centre), length_m=platform.computed_length,
            width_m=platform.computed_width, label=cfg.platform_name,
        ))
    for crossover in generator._crossover_results:
        if not crossover.geometry:
            continue
        result["crossovers"].append(dict(
            id=crossover.id, from_track=crossover.from_track, to_track=crossover.to_track,
            start=ch(crossover.geometry[0]), end=ch(crossover.geometry[-1]),
            turnout=crossover.turnout_type or "", position_mode="resolved",
        ))
    # Sidings receive their own schematic level and a connection to the host.
    for i, (spec, siding) in enumerate(getattr(generator, "_siding_results", []), 1):
        name = f"SIDING_{i}"
        result["tracks"].append(dict(
            name=name, kind="SIDING", number=i, offset=lateral(siding.tip),
            start=ch(siding.points[0]), end=ch(siding.tip),
            label=f"SIDING {i} STANDING LENGTH={siding.standing_length_m:.2f}M",
            length_m=siding.standing_length_m, direction="",
        ))
        heel = point_at_chainage(siding.points, siding.ladder_length_m).point
        # Only the standing portion is horizontal; connect its heel to the source.
        result["tracks"][-1]["start"] = ch(heel)
        result["crossovers"].append(dict(id=f"S{i}", from_track=spec.source_track,
            to_track=name, start=ch(siding.points[0]), end=ch(heel), turnout=siding.turnout_label))
    for request, building in getattr(generator, "_key_plan_building_results", []):
        result["buildings"].append(dict(name=request.building_name, platform=request.platform_layer,
            chainage=ch(building.center), length_m=request.building_length,
            width_m=request.building_width, offset=lateral(building.center)))
    start_m = _start_chainage(generator.config)
    parsed = generator._parse_alignment_station_markers(main, start_m, polyline_length(main))
    result["stations"] = [dict(name=s["name"], chainage=s["d"], chainage_m=s["ch_m"])
                          for s in parsed]
    for cfg, outline in getattr(generator, "_key_plan_fob_outlines", []):
        # Use the generated deck, whose reference may be a bounded loop with
        # a different chainage origin from MAIN. Never reinterpret its input.
        point = tuple(sum(p[i] for p in outline) / len(outline) for i in (0, 1))
        result["bridges"].append(dict(kind="FOB", chainage=ch(point), platforms=list(cfg.platforms)))
    for cfg in getattr(generator.config, "bridges", []) or []:
        geometry = getattr(cfg, "_geom", None)
        if geometry:
            result["bridges"].append(dict(kind="BRIDGE", id=cfg.id, bridge_type=cfg.bridge_type, label=cfg.type_label,
                chainage=ch(geometry.center_point), absolute_chainage=cfg._absolute_chainage, platforms=[]))
    bounds = [v for t in result["tracks"] for v in (t["start"], t["end"])]
    bounds += [v for p in result["platforms"] for v in (p["start"], p["end"])]
    bounds += [v for c in result["crossovers"] for v in (c["start"], c["end"])]
    bounds += [s["chainage"] for s in result["stations"] + result["buildings"] + result["bridges"]]
    bounds += [value for overrun in result["overruns"] for value in (overrun["srj_chainage"], overrun["tip_chainage"])]
    result.update(start=min(bounds), end=max(bounds), start_chainage_m=start_m)
    if not math.isfinite(result["end"] - result["start"]) or result["end"] <= result["start"]:
        raise ValueError("Key plan requires a nonzero finite yard extent.")
    return result
