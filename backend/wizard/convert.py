"""Component builders for converting wizard specs to config dicts."""

from __future__ import annotations

from typing import Tuple

from common.constants import DEFAULT_FOB_DIRECTION, DEFAULT_FOB_OFFSET_M, DEFAULT_FOB_WIDTH_M

from .helpers import (
    DEFAULT_EXTENSION,
    DEFAULT_TURNOUT,
    _centered_chainages,
    _choice,
    _count,
    _extensions,
    _fob_chainage,
    _parallel_list,
    _spacing,
    _turnout,
)

__all__ = [
    "_build_main_lines",
    "_explicit_loop",
    "_build_loops",
    "_build_proposed",
    "_build_crossovers",
    "_build_platforms",
    "_build_stations",
    "_build_fobs",
    "_build_sidings",
    "_build_gradients",
]


def _build_main_lines(raw: object) -> Tuple[list[dict], dict[str, str]]:
    if raw is None:
        return [], {}
    if not isinstance(raw, dict):
        raise ValueError("'main_lines' must be {\"count\": n, ...}.")
    count = _count(raw.get("count", 0), "main_lines")
    distances = _parallel_list(raw.get("distances"), count, "main_lines.distances")
    sides = _parallel_list(raw.get("sides"), count, "main_lines.sides")
    directions = _parallel_list(raw.get("directions"), count, "main_lines.directions")
    lines, main_directions = [], {}
    for number in range(1, count + 1):
        idx = number - 1
        if distances[idx] is None:
            raise ValueError(f"'main_lines.distances[{idx}]' is required (metres from MAIN_LINE).")
        lines.append({
            "name": f"MAIN_LINE_{number}",
            "spacing": _spacing(distances[idx], f"main_lines.distances[{idx}]"),
            "side": _choice(sides[idx] or "LEFT", ("LEFT", "RIGHT"), f"main_lines.sides[{idx}]"),
        })
    if lines:
        main_directions["MAIN_LINE"] = _choice(
            directions[0] or "UP", ("UP", "DN"), "main_lines.directions[0]"
        )
        opposite = "DN" if main_directions["MAIN_LINE"] == "UP" else "UP"
        for item, raw_direction in zip(lines, directions):
            direction = _choice(
                raw_direction or opposite, ("UP", "DN"), f"main_lines.directions for {item['name']}"
            )
            item["direction"] = direction
            main_directions[item["name"]] = direction
    return lines, main_directions


def _explicit_loop(
    item: dict, name: str, main_center: float | None, shared_ext: object = None
) -> dict:
    if not isinstance(item, dict):
        raise ValueError(f"loop '{name}' must be an object.")
    if "spacing" not in item and "distance" not in item:
        raise ValueError(f"loop '{name}' needs 'spacing' (or 'distance') in metres.")
    designation, variant = _turnout(item)
    start_ext, end_ext = _extensions(item, shared_ext)
    loop = {
        "name": name,
        "spacing": _spacing(item.get("spacing", item.get("distance")), f"loop '{name}' spacing"),
        "side": _choice(item.get("side", "LEFT"), ("LEFT", "RIGHT"), f"loop '{name}' side"),
        "turnout_designation": designation,
        "turnout_variant": variant,
        "crossover_distance_m": float(item.get("crossover_distance_m", 750.0) or 750.0),
        "extend_start_m": start_ext,
        "extend_end_m": end_ext,
    }
    c1 = item.get("first_crossover_chainage", item.get("first_chainage_m"))
    c2 = item.get("second_crossover_chainage", item.get("second_chainage_m"))
    if c1 is not None or c2 is not None:
        if c1 is None or c2 is None:
            raise ValueError(f"loop '{name}': give both chainages or neither (neither = 750 m centred).")
        loop["first_crossover_chainage"] = float(c1)
        loop["second_crossover_chainage"] = float(c2)
    elif item.get("centered", True):
        c1, c2 = _centered_chainages(main_center, f"loop '{name}'")
        loop["first_crossover_chainage"] = c1
        loop["second_crossover_chainage"] = c2
    return loop


def _build_loops(raw: object, main_center: float | None) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        loops = []
        for number, item in enumerate(raw, 1):
            name = (
                str(item.get("name", f"LOOP_{number}"))
                if isinstance(item, dict)
                else f"LOOP_{number}"
            )
            loops.append(_explicit_loop(item, name, main_center))
        return loops
    if not isinstance(raw, dict):
        raise ValueError("'loops' must be {\"count\": n, ...} or an explicit list.")
    count = _count(raw.get("count", 0), "loops")
    spacings = _parallel_list(raw.get("spacings", raw.get("distances")), count, "loops.spacings")
    sides = _parallel_list(raw.get("sides"), count, "loops.sides")
    ext_raw = raw.get("extensions")
    if ext_raw is None or isinstance(ext_raw, dict):
        extensions: list = [ext_raw] * count
    else:
        extensions = _parallel_list(ext_raw, count, "loops.extensions")
    shared_spacing = raw.get("spacing", raw.get("distance"))
    loops = []
    for number in range(1, count + 1):
        idx = number - 1
        spacing = spacings[idx] if spacings[idx] is not None else shared_spacing
        if spacing is None:
            raise ValueError(
                f"loop LOOP_{number}: give 'spacing' (or a shared loops.spacing) in metres."
            )
        item: dict = {"spacing": spacing, "side": sides[idx] or "LEFT"}
        if "turnout" in raw:
            item["turnout"] = raw["turnout"]
        if "turnout_variant" in raw:
            item["turnout_variant"] = raw["turnout_variant"]
        if "crossover_distance_m" in raw:
            item["crossover_distance_m"] = raw["crossover_distance_m"]
        loops.append(_explicit_loop(item, f"LOOP_{number}", main_center, shared_ext=extensions[idx]))
    return loops


def _build_proposed(raw: object, kind: str, main_center: float | None) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"'{kind}' must be a list.")
    items = []
    prefix = "PROPOSED_LINE" if kind == "proposed_lines" else "PROPOSED_LOOP_LINE"
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"'{kind}[{number - 1}]' must be an object.")
        name = str(item.get("name", f"{prefix}_{number}"))
        if "spacing" not in item and "distance" not in item:
            raise ValueError(f"'{kind}' item '{name}' needs 'spacing' (or 'distance').")
        entry: dict = {
            "name": name,
            "spacing": _spacing(item.get("spacing", item.get("distance")), f"'{kind}' item '{name}'"),
            "side": _choice(item.get("side", "LEFT"), ("LEFT", "RIGHT"), f"'{kind}' item '{name}' side"),
        }
        if kind == "proposed_loops":
            designation, variant = _turnout(item)
            start_ext, end_ext = _extensions(item)
            c1 = item.get("first_crossover_chainage", item.get("first_chainage_m"))
            c2 = item.get("second_crossover_chainage", item.get("second_chainage_m"))
            if c1 is None or c2 is None:
                c1, c2 = _centered_chainages(main_center, f"'{kind}' item '{name}'")
            entry.update({
                "turnout_designation": designation,
                "turnout_variant": variant,
                "crossover_distance_m": float(item.get("crossover_distance_m", 750.0) or 750.0),
                "extend_start_m": start_ext,
                "extend_end_m": end_ext,
                "first_crossover_chainage": float(c1),
                "second_crossover_chainage": float(c2),
            })
        else:
            if "direction" in item:
                entry["direction"] = _choice(
                    item["direction"], ("UP", "DN", ""), f"'{kind}' item '{name}' direction"
                )
        items.append(entry)
    return items


def _build_crossovers(raw: object) -> Tuple[list[dict], str | None, str]:
    if raw is None:
        return [], None, DEFAULT_TURNOUT
    if isinstance(raw, str):
        if raw.strip().upper() != "DEFAULT":
            raise ValueError("'crossovers' string must be \"DEFAULT\" or a list.")
        return [], "DEFAULT", DEFAULT_TURNOUT
    if isinstance(raw, dict):
        if str(raw.get("preset", "")).strip().upper() != "DEFAULT":
            raise ValueError("'crossovers.preset' must be \"DEFAULT\" or give a list instead.")
        return [], "DEFAULT", str(raw.get("turnout", DEFAULT_TURNOUT))
    if not isinstance(raw, list):
        raise ValueError("'crossovers' must be \"DEFAULT\" or a list.")
    items = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"crossovers[{number - 1}] must be an object.")
        for key in ("from_track", "to_track"):
            if not item.get(key):
                raise ValueError(f"crossovers[{number - 1}] needs '{key}'.")
        entry = {
            "from_track": str(item["from_track"]),
            "to_track": str(item["to_track"]),
        }
        for key in (
            "from_chainage_m", "chainage_m", "chainage", "start_chainage_m",
            "direction", "turnout", "position_mode",
            "auto_anchor_id", "autoAnchor", "auto_anchor",
        ):
            if key in item:
                entry[key] = item[key]
        if "auto_anchor_id" not in entry:
            for alias in ("autoAnchor", "auto_anchor"):
                if entry.get(alias):
                    entry["auto_anchor_id"] = str(entry.pop(alias))
                    break
            else:
                for alias in ("autoAnchor", "auto_anchor"):
                    entry.pop(alias, None)
        else:
            for alias in ("autoAnchor", "auto_anchor"):
                entry.pop(alias, None)
        if entry.get("auto_anchor_id") is not None:
            entry["auto_anchor_id"] = str(entry["auto_anchor_id"]).strip() or None
            if not entry["auto_anchor_id"]:
                entry.pop("auto_anchor_id", None)
        items.append(entry)
    return items, None, DEFAULT_TURNOUT


def _build_platforms(raw: object) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'platforms' must be a list.")
    items = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"platforms[{number - 1}] must be an object.")
        entry = {
            "track_layer": str(item.get("track", item.get("track_layer", "MAIN_LINE"))),
            "platform_type": _choice(
                item.get("type", item.get("platform_type", "SIDE")),
                ("SIDE", "ISLAND"),
                f"platforms[{number - 1}].type",
            ),
            "side": _choice(
                item.get("side", "LEFT"),
                ("LEFT", "RIGHT"),
                f"platforms[{number - 1}].side",
            ),
            "center_on_track": bool(item.get("center_on_track", True)),
            "clearance": float(item.get("clearance", 1.68)),
            "platform_width": float(item.get("width", item.get("platform_width", 8.5))),
            "platform_length": float(item.get("length", item.get("platform_length", 550.0))),
            "platform_height": float(item.get("height", item.get("platform_height", 0.84))),
            "platform_name": str(item.get("name", item.get("platform_name", f"PLATFORM {number}"))),
        }
        if item.get("second_track", item.get("second_track_layer")):
            entry["second_track_layer"] = str(item.get("second_track", item.get("second_track_layer")))
        if item.get("stairs", item.get("stair_length")):
            entry["stair_length"] = float(item.get("stairs", item.get("stair_length")))
        items.append(entry)
    return items


def _build_stations(raw: object) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'stations' must be a list.")
    items = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"stations[{number - 1}] must be an object.")
        entry = {
            "platform_layer": str(item.get("platform", item.get("platform_layer", "PLATFORM_1"))),
            "building_length": float(item.get("length", item.get("building_length", 40.0))),
            "building_width": float(item.get("width", item.get("building_width", 10.0))),
            "platform_side": _choice(
                item.get("side", item.get("platform_side", "RIGHT")),
                ("LEFT", "RIGHT"),
                f"stations[{number - 1}].side",
            ),
            "building_name": str(item.get("name", item.get("building_name", "STATION BUILDING"))),
        }
        ch = item.get("station_chainage", item.get("chainage", None))
        if ch is not None and str(ch).strip() != "":
            entry["station_chainage"] = str(ch).strip()
        items.append(entry)
    return items


def _build_fobs(raw: object, main_center: float | None = None) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'fobs' must be a list.")
    items = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"fobs[{number - 1}] must be an object.")
        platforms = item.get("platforms", [])
        if not isinstance(platforms, list) or len(platforms) < 2:
            raise ValueError(f"fobs[{number - 1}] must connect at least two 'platforms'.")
        entry = {
            "reference_track": str(item.get("reference_track", "MAIN_LINE")),
            "reference_chainage": _fob_chainage(
                item.get("reference_chainage", None), main_center, number
            ),
            "platforms": [str(layer) for layer in platforms],
            "width": float(item.get("width", DEFAULT_FOB_WIDTH_M)),
            "offset": (
                float(item["offset"])
                if item.get("offset") is not None and str(item.get("offset")).strip() != ""
                else DEFAULT_FOB_OFFSET_M
            ),
            "direction": str(item.get("direction", DEFAULT_FOB_DIRECTION)).strip().upper(),
        }
        if "vertical_clearance_m" in item:
            entry["vertical_clearance_m"] = float(item["vertical_clearance_m"])
        start_ext, end_ext = _extensions(item, {"length": 0.0, "side": "BOTH"})
        entry["extend_start_m"] = start_ext
        entry["extend_end_m"] = end_ext
        arms = {}
        for layer, arm in (item.get("arms") or {}).items():
            if not isinstance(arm, dict) or "length" not in arm:
                raise ValueError(f"fobs[{number - 1}].arms[{layer}] needs {{\"length\": m}}.")
            arms[str(layer)] = {
                "length": float(arm["length"]),
                "side": _choice(arm.get("side", "LEFT"), ("LEFT", "RIGHT"), f"fobs[{number - 1}].arms[{layer}].side"),
            }
        entry["arms"] = arms
        items.append(entry)
    return items


def _build_sidings(raw: object) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'sidings' must be a list.")
    items = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"sidings[{number - 1}] must be an object.")
        if not item.get("source_track"):
            raise ValueError(f"sidings[{number - 1}] needs 'source_track'.")
        if (
            "start_chainage_m" not in item
            and "chainage_m" not in item
            and "chainage" not in item
        ):
            raise ValueError(f"sidings[{number - 1}] needs 'start_chainage_m'.")
        designation, variant = _turnout(item)
        items.append({
            "source_track": str(item["source_track"]),
            "start_chainage_m": float(
                item.get("start_chainage_m", item.get("chainage_m", item.get("chainage")))
            ),
            "direction": _choice(
                item.get("direction", "FORWARD"), ("FORWARD", "REVERSE"), f"sidings[{number - 1}].direction"
            ),
            "side": _choice(
                item.get("side", "LEFT"), ("LEFT", "RIGHT"), f"sidings[{number - 1}].side"
            ),
            "turnout": designation,
            "turnout_variant": variant,
            "standing_length_m": float(item.get("standing_length_m", 200.0)),
        })
    return items


def _build_gradients(raw: object) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'gradients' must be a list.")
    items = []
    for number, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError(f"gradients[{number - 1}] must be an object.")
        
        left_val = item.get("left_gradient_value", item.get("left_value", ""))
        right_val = item.get("right_gradient_value", item.get("right_value", item.get("gradient_value", item.get("value", ""))))
        left_dir = item.get("left_direction", item.get("left_slope", "STRAIGHT"))
        right_dir = item.get("right_direction", item.get("right_slope", item.get("direction", "RISE")))

        entry = {
            "track_designation": str(item.get("track_designation", item.get("track", "MAIN_LINE"))),
            "gradient_value": str(item.get("gradient_value", item.get("value", ""))).strip(),
            "direction": _choice(
                str(item.get("direction", "UP")).strip().upper(),
                ("UP", "DOWN", "DN", "LEVEL", "RISE", "STRAIGHT"),
                f"gradients[{number - 1}].direction",
            ),
            "left_gradient_value": str(left_val).strip() if left_val is not None else None,
            "left_direction": _choice(
                str(left_dir).strip().upper(),
                ("RISE", "DOWN", "DN", "STRAIGHT", "UP", "LEVEL"),
                f"gradients[{number - 1}].left_direction",
            ),
            "right_gradient_value": str(right_val).strip() if right_val is not None else None,
            "right_direction": _choice(
                str(right_dir).strip().upper(),
                ("RISE", "DOWN", "DN", "STRAIGHT", "UP", "LEVEL"),
                f"gradients[{number - 1}].right_direction",
            ),
            "line_length": 10.0,
        }
        ch = item.get("chainage")
        if ch is not None and str(ch).strip() != "":
            entry["chainage"] = str(ch).strip()
        offset = item.get("offset")
        if offset is not None and str(offset).strip() != "":
            entry["offset"] = float(offset)
        rl = item.get("rl")
        if rl is not None and str(rl).strip() != "":
            entry["rl"] = str(rl).strip()
        items.append(entry)
    return items

