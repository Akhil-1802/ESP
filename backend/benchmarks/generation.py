"""Reproducible generation benchmark; no hosted service or Render settings needed.

python backend/benchmarks/generation.py --repeat 3 --reference baseline.json
python backend/benchmarks/generation.py --repeat 3 --compare baseline.json
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import statistics
import shutil
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ezdxf
from ezdxf.document import Drawing
from config.loader import ESPConfig, PlatformRequest, StationRequest
from fob.config import FOBConfig
from pipeline.orchestrator import ESPGenerator
from platform_gen.config import PlatformConfig
from rob.config import ROBConfig
from track.specs import CrossoverSpec, LoopSpec
from track.turnouts import select_turnout


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--save-sample", type=Path)
    parser.add_argument("--disk", action="store_true", help="Use diagnostic disk checkpoints for comparison")
    args = parser.parse_args()
    samples = []
    real_read, real_save = ezdxf.readfile, Drawing.saveas
    for _ in range(args.repeat):
        with tempfile.TemporaryDirectory() as folder:
            cfg = yard_config(Path(folder))
            counts = {"reads": 0, "writes": 0}
            def read(*a, **kw):
                counts["reads"] += 1
                return real_read(*a, **kw)
            def save(doc, *a, **kw):
                counts["writes"] += 1
                return real_save(doc, *a, **kw)
            generator = ESPGenerator(cfg)
            start = perf_counter()
            with patch("ezdxf.readfile", read), patch.object(Drawing, "saveas", save), redirect_stdout(io.StringIO()):
                generator.run(**({"in_memory": False} if args.disk else {}))
            elapsed = perf_counter() - start
            result = real_read(cfg.output_dxf)
            if args.save_sample:
                shutil.copyfile(cfg.output_dxf, args.save_sample)
            samples.append({"seconds": round(elapsed, 4), **counts,
                            "entities": len(result.modelspace()), "digest": geometry_digest(result)})
    report = {"median_seconds": round(statistics.median(s["seconds"] for s in samples), 4), "samples": samples}
    if args.compare:
        before = json.loads(args.compare.read_text())
        report["geometry_unchanged"] = samples[-1]["digest"] == before["samples"][-1]["digest"]
        report["speedup"] = round(before["median_seconds"] / report["median_seconds"], 2)
    if args.reference:
        args.reference.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
