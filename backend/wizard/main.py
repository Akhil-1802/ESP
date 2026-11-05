"""Interactive-style wizard entry points and main converter."""

from __future__ import annotations

from pathlib import Path

from platform_gen.kml_io import convert_kml_to_dxf

from .convert import (
    _build_crossovers,
    _build_fobs,
    _build_loops,
    _build_main_lines,
    _build_platforms,
    _build_proposed,
    _build_sidings,
    _build_stations,
    _build_gradients,
)
from .helpers import _KNOWN_TOP_LEVEL, _count

__all__ = [
    "wizard_needs_center",
    "wizard_main_center",
    "wizard_to_config_dict",
]


def wizard_needs_center(spec: dict) -> bool:
    """True when the spec needs the MAIN midpoint (centred loops/FOBs)."""
    loops = spec.get("loops", {"count": 0})
    if isinstance(loops, dict) and _count(loops.get("count", 0), "loops") > 0:
        return True
    if isinstance(spec.get("proposed_loops"), list) and spec["proposed_loops"]:
        return True
    for item in spec.get("fobs") or []:
        if isinstance(item, dict):
            value = item.get("reference_chainage", None)
            if value is None or (
                isinstance(value, str)
                and value.strip() in ("", "AUTO", "auto", "MAIN_CENTER", "main_center")
            ):
                return True
    return False


def wizard_main_center(
    kml_path: Path,
    workdir: Path,
    layer: str = "MAIN_TRACK",
    selected_track_id: int | str | None = None,
) -> float:
    """MAIN midpoint chainage of the uploaded KML."""
    from cli.main import _main_center

    converted = workdir / f"{kml_path.stem}_converted.dxf"
    convert_kml_to_dxf(str(kml_path), str(converted), selected_track_id=selected_track_id)
    return _main_center(str(converted), layer)


def wizard_to_config_dict(spec: dict, main_center: float | None = None) -> dict:
    """Convert a wizard spec to an inputconfig dict."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object.")
    unknown = set(spec) - _KNOWN_TOP_LEVEL
    if unknown:
        raise ValueError(f"unknown spec key(s): {sorted(unknown)}.")

    main_lines, main_directions = _build_main_lines(spec.get("main_lines"))
    loops = _build_loops(spec.get("loops"), main_center)
    proposed_lines = _build_proposed(spec.get("proposed_lines"), "proposed_lines", main_center)
    proposed_loops = _build_proposed(spec.get("proposed_loops"), "proposed_loops", main_center)
    crossovers, preset, preset_turnout = _build_crossovers(spec.get("crossovers"))

    config: dict = {
        "output_dxf": str(spec.get("output_dxf", "ESP_wizard.dxf")),
        "track_source_layer": str(spec.get("track_source_layer", "MAIN_TRACK")),
        "loops": [
            {
                "name": loop["name"],
                "spacing": loop["spacing"],
                "side": loop["side"],
                "first_crossover_chainage": loop.get("first_crossover_chainage"),
                "second_crossover_chainage": loop.get("second_crossover_chainage"),
                "turnout_designation": loop["turnout_designation"],
                "turnout_variant": loop["turnout_variant"],
                "crossover_distance_m": loop["crossover_distance_m"],
                "extend_start_m": loop["extend_start_m"],
                "extend_end_m": loop["extend_end_m"],
            }
            for loop in loops
        ],
        "additional_lines": [
            *[
                {
                    "name": line["name"],
                    "spacing": line["spacing"],
                    "side": line["side"],
                    **({"direction": line["direction"]} if line.get("direction") else {}),
                }
                for line in main_lines
            ],
            *[
                {"name": line["name"], "spacing": line["spacing"], "side": line["side"]}
                for line in proposed_lines
            ],
            *[
                {
                    "name": loop["name"],
                    "spacing": loop["spacing"],
                    "side": loop["side"],
                    "first_crossover_chainage": loop["first_crossover_chainage"],
                    "second_crossover_chainage": loop["second_crossover_chainage"],
                    "turnout_designation": loop["turnout_designation"],
                    "turnout_variant": loop["turnout_variant"],
                    "crossover_distance_m": loop["crossover_distance_m"],
                    "extend_start_m": loop["extend_start_m"],
                    "extend_end_m": loop["extend_end_m"],
                }
                for loop in proposed_loops
            ],
        ],
        "platforms": _build_platforms(spec.get("platforms")),
        "stations": _build_stations(spec.get("stations")),
        "crossovers": crossovers,
        "main_directions": main_directions,
        "fobs": _build_fobs(spec.get("fobs"), main_center),
        "sidings": _build_sidings(spec.get("sidings")),
        "gradients": _build_gradients(spec.get("gradients")),
    }
    if preset is not None:
        config["crossover_preset"] = preset
        config["crossover_preset_turnout"] = preset_turnout
    return config
