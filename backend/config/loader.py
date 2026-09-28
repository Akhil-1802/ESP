"""Load user-editable JSON configuration."""

from __future__ import annotations

import dataclasses as _dc
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from fob.config import FOBConfig
from platform_gen.config import PlatformConfig
from rob.config import ROBConfig
from track.specs import CrossoverSpec, LineSpec, LoopSpec, SidingSpec
from track.turnouts import default_crossing_angle_rad, get_turnout_parameters, select_turnout as _select_turnout


@dataclass
class PlatformRequest:
    track_layer: str
    config: PlatformConfig


@dataclass
class StationRequest:
    platform_layer: str
    building_length: float
    building_width: float
    platform_side: str = "RIGHT"
    building_name: str = "STATION BUILDING"


@dataclass
class ESPConfig:
    """Root configuration for the entire workflow."""
    source_path: str
    output_dxf: str
    track_source_layer: str
    loops: list = None
    additional_lines: list = None
    platforms: list[PlatformRequest] = None
    stations: list[StationRequest] = None
    crossovers: list = None
    main_directions: dict = None
    crossover_preset: str | None = None
    crossover_preset_turnout: str = "1:12"
    fobs: list = None
    sidings: list = None
    robs: list = None

    def __post_init__(self):
        if self.loops is None:
            self.loops = []
        if self.additional_lines is None:
            self.additional_lines = []
        if self.platforms is None:
            self.platforms = []
        if self.stations is None:
            self.stations = []
        if self.crossovers is None:
            self.crossovers = []
        if self.fobs is None:
            self.fobs = []
        if self.sidings is None:
            self.sidings = []
        if self.robs is None:
            self.robs = []
        if self.main_directions is None:
            self.main_directions = {}
        if self.crossover_preset is not None:
            self.crossover_preset = str(self.crossover_preset).strip().upper() or None
        if self.crossover_preset_turnout is None:
            self.crossover_preset_turnout = "1:12"
        else:
            self.crossover_preset_turnout = str(self.crossover_preset_turnout).strip() or "1:12"


def _resolve_path(value: str, config_path: Path) -> str:
    """Resolve relative paths from the config file location."""
    candidate = Path(value).expanduser()
    return str(candidate if candidate.is_absolute() else (config_path.parent / candidate).resolve())


def _strip_comments(mapping: dict[str, Any]) -> dict[str, Any]:
    """Drop user-reference comment keys (`"_note..."`, `"//..."`)."""
    return {key: value for key, value in mapping.items()
            if not key.startswith(("_", "//"))}


def _load_siding(item: dict[str, Any], index: int = 0):
    """Convert JSON siding entry to SidingSpec (endpoint auto-derived)."""
    values = _strip_comments(dict(item))
    if not values.get("id"):
        values["id"] = f"S{index + 1}"
    for alias in ("chainage", "chainage_m", "start_chainage"):
        if alias in values and "start_chainage_m" not in values:
            values["start_chainage_m"] = values.pop(alias)
        else:
            values.pop(alias, None)
    turnout_values = values.pop("turnout", None)
    if isinstance(turnout_values, str):
        values["turnout_designation"] = turnout_values
    elif isinstance(turnout_values, dict):
        if "designation" in turnout_values:
            values["turnout_designation"] = turnout_values["designation"]
        if "variant" in turnout_values:
            values["turnout_variant"] = turnout_values["variant"]
    for key in ("start_chainage_m", "standing_length_m", "spacing"):
        if key in values and not isinstance(values[key], (int, float)):
            try:
                values[key] = float(str(values[key]).strip())
            except ValueError:
                pass
    if values.get("direction") is not None:
        values["direction"] = str(values["direction"]).strip().upper()
    if values.get("side") is not None:
        values["side"] = str(values["side"]).strip().upper()
    allowed = {"source_track", "start_chainage_m", "direction", "side",
               "turnout_designation", "turnout_variant", "standing_length_m",
               "spacing", "id"}
    values = {k: v for k, v in values.items() if k in allowed}
    return SidingSpec(**values)


def _load_fob(item: dict[str, Any], number: int = 1):
    """Convert JSON FOB entry to FOBConfig (span auto-derived later)."""
    values = _strip_comments(dict(item))
    values.setdefault("output_layer", f"FOB_{number}")
    return FOBConfig(**values)


def _load_rob(item: dict[str, Any], number: int = 1):
    """Convert JSON ROB entry to ROBConfig."""
    values = _strip_comments(dict(item))
    if not values.get("id"):
        values["id"] = f"ROB_{number}"
    values.setdefault("output_layer", f"ROB_{number}")
    allowed = {f.name for f in _dc.fields(ROBConfig)}
    values = {k: v for k, v in values.items() if k in allowed}
    return ROBConfig(**values)


def _load_platform(item: dict[str, Any], source: str, output: str, number: int) -> PlatformRequest:
    """Convert JSON platform entry to PlatformRequest."""
    values = _strip_comments(dict(item))
    track_layer = values.pop("track_layer")
    values.setdefault("output_layer", f"PLATFORM_{number}")
    values.setdefault("text_layer", f"PLATFORM_{number}_TEXT")
    values["source_dxf"] = source
    values["output_dxf"] = output
    config = PlatformConfig(track_layer=track_layer, **values)
    return PlatformRequest(track_layer, config)


def _load_crossover(item: dict[str, Any], index: int = 0) -> CrossoverSpec:
    """Convert JSON crossover entry to CrossoverSpec."""
    values = _strip_comments(dict(item))
    for alias in ("chainage", "chainage_m", "start_chainage_m"):
        if alias in values and "from_chainage_m" not in values:
            values["from_chainage_m"] = values.pop(alias)
        else:
            values.pop(alias, None)
    if "from_chainage_m" in values and isinstance(values["from_chainage_m"], str):
        s = values["from_chainage_m"].strip()
        if s.upper() == "AUTO":
            values["from_chainage_m"] = None
            values.setdefault("position_mode", "AUTO")
        else:
            try:
                values["from_chainage_m"] = float(s)
            except ValueError:
                pass
    if "dir" in values and "direction" not in values:
        values["direction"] = values.pop("dir")
    if "mode" in values and "position_mode" not in values:
        values["position_mode"] = values.pop("mode")
    if values.get("direction") is not None:
        values["direction"] = str(values["direction"]).strip().upper()
    if values.get("position_mode") is not None:
        values["position_mode"] = str(values["position_mode"]).strip().upper()
    values.pop("placement", None)
    if values.get("from_chainage_m") is None:
        values.setdefault("position_mode", "AUTO")
    if not values.get("id"):
        values["id"] = f"C{index + 1}" if index else values.pop("id", None) or "C1"
    turnout_values = values.pop("turnout", None)
    if turnout_values is not None:
        if isinstance(turnout_values, str):
            turnout = _select_turnout(turnout_values)
        else:
            designation = turnout_values["designation"]
            variant = turnout_values.get("variant", "standard")
            turnout = get_turnout_parameters(designation, variant)

            if "crossing_angle_degrees" in turnout_values:
                turnout = replace(turnout, crossing_angle_rad=math.radians(turnout_values["crossing_angle_degrees"]))
            elif turnout.crossing_angle_rad is None:
                turnout = replace(turnout, crossing_angle_rad=default_crossing_angle_rad())

            if "radius_m" in turnout_values:
                turnout = replace(turnout, radius_mm=turnout_values["radius_m"] * 1000.0)
        values["turnout"] = turnout

    if "position" in values:
        values["after_platform"] = values.pop("position").upper() == "AFTER"

    allowed = {f.name for f in _dc.fields(CrossoverSpec)}
    values = {k: v for k, v in values.items() if k in allowed}

    return CrossoverSpec(**values)


def load_config_from_json(filename: str) -> ESPConfig:
    """Load configuration from a JSON file."""
    config_path = Path(filename).expanduser().resolve()
    
    with config_path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    
    source = _resolve_path(data["source_path"], config_path)
    output = _resolve_path(data["output_dxf"], config_path)

    platforms = [_load_platform(item, output, output, idx) for idx, item in enumerate(data.get("platforms", []), 1)]
    stations = [StationRequest(**_strip_comments(item)) for item in data.get("stations", [])]
    loops = [LoopSpec(**_strip_comments(item)) for item in data.get("loops", [])]
    additional_lines = [LineSpec(**_strip_comments(item)) for item in data.get("additional_lines", [])]
    raw_crossovers = data.get("crossovers", [])
    preset = data.get("crossover_preset", None)
    preset_turnout = data.get("crossover_preset_turnout", "1:12")
    if isinstance(raw_crossovers, str) and raw_crossovers.strip().upper() == "DEFAULT":
        preset, raw_crossovers = "DEFAULT", []
    elif isinstance(raw_crossovers, dict) and str(raw_crossovers.get("preset", "")).strip().upper() == "DEFAULT":
        preset = "DEFAULT"
        preset_turnout = raw_crossovers.get("turnout", preset_turnout)
        raw_crossovers = []
    if preset is not None:
        preset = str(preset).strip().upper()
        if preset not in ("DEFAULT", "NONE", ""):
            raise ValueError(
                f"Unknown crossover_preset {preset!r} - use \"DEFAULT\" or omit it.")
        if preset in ("NONE", ""):
            preset = None
    if isinstance(preset_turnout, dict):
        preset_turnout = preset_turnout.get("designation", "1:12")
    crossovers = [_load_crossover(item, idx) for idx, item in enumerate(raw_crossovers or [])]
    fobs = [_load_fob(item, idx) for idx, item in enumerate(data.get("fobs", []) or [], 1)]
    sidings = [_load_siding(item, idx) for idx, item in enumerate(data.get("sidings", []) or [])]
    robs = [_load_rob(item, idx) for idx, item in enumerate(data.get("robs", []) or [], 1)]

    return ESPConfig(
        source_path=source,
        output_dxf=output,
        track_source_layer=data.get("track_source_layer", "MAIN_TRACK"),
        loops=loops,
        additional_lines=additional_lines,
        platforms=platforms,
        stations=stations,
        crossovers=crossovers,
        main_directions=data.get("main_directions", {}),
        crossover_preset=preset,
        crossover_preset_turnout=str(preset_turnout or "1:12"),
        fobs=fobs,
        sidings=sidings,
        robs=robs,
    )
