
import hashlib
import json
from pathlib import Path

import ezdxf
from app.features.drawing_generation.config import (
    ESPConfig,
    PlatformRequest,
    StationRequest,
)
from app.features.drawing_generation.domain.bridges.fob.config import FOBConfig
from app.features.drawing_generation.domain.bridges.rob.config import ROBConfig
from app.features.drawing_generation.domain.platform.config import PlatformConfig
from app.features.drawing_generation.domain.track.specs import CrossoverSpec, LoopSpec
from app.features.drawing_generation.domain.track.turnouts import select_turnout


def yard_config(folder: Path) -> ESPConfig:
    source, output = folder / "source.dxf", folder / "output.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0), (2500, 0)], dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)
    loops = [LoopSpec("LOOP_1", 5.3, "LEFT", 500, 1800),
             LoopSpec("LOOP_2", 5.3, "RIGHT", 500, 1800)]
    platforms = [PlatformRequest(track_layer=loop.name, config=PlatformConfig(
        source_dxf=str(source), output_dxf=str(output), track_layer=loop.name,
        side=loop.side, platform_length=500, platform_width=6,
        arm_length=16.999, output_layer=f"PLATFORM_{i}",
    )) for i, loop in enumerate(loops, 1)]
    return ESPConfig(
        source_path=str(source), output_dxf=str(output), track_source_layer="MAIN_TRACK",
        loops=loops, platforms=platforms,
        stations=[StationRequest(platform_layer="PLATFORM_1", platform_side="LEFT", building_length=40, building_width=10)],
        crossovers=[CrossoverSpec("MAIN_LINE", "LOOP_1", 500, None, select_turnout("1:12"),
                                 "AHEAD", id="C1", direction="FORWARD", position_mode="FIXED"),
                    CrossoverSpec("MAIN_LINE", "LOOP_1", 1800, None, select_turnout("1:12"),
                                 "AHEAD", id="C2", direction="REVERSE", position_mode="FIXED")],
        fobs=[FOBConfig(reference_chainage=1050, position_mode="FIXED",
                        platforms=["PLATFORM_1", "PLATFORM_2"])],
        robs=[ROBConfig(platform="PLATFORM_2")],
        enable_main_line_trim=True, align_final_plan_to_x_axis=True,
    )


def geometry_digest(doc):
    entity_indexes = {entity.dxf.handle: i for i, entity in enumerate(doc.modelspace())}
    def encode(value):
        if isinstance(value, float):
            return round(value, 7)
        if isinstance(value, (list, tuple)) or hasattr(value, "__iter__") and not isinstance(value, (str, dict)):
            return [encode(v) for v in value]
        if isinstance(value, dict):
            return {k: (entity_indexes.get(v, "external") if k == "annotation_handle" else encode(v))
                    for k, v in value.items() if k not in ("handle", "owner")}
        return value
    items = []
    for entity in doc.modelspace():
        record = {"type": entity.dxftype(), "attributes": encode(entity.dxfattribs())}
        if entity.dxftype() == "LWPOLYLINE":
            record["points"] = encode(list(entity.get_points()))
        elif entity.dxftype() == "SPLINE":
            record["control"] = encode(entity.control_points)
            record["fit"] = encode(entity.fit_points)
        elif entity.dxftype() == "MTEXT":
            record["text"] = entity.text
        items.append(record)
    text = json.dumps(items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()
