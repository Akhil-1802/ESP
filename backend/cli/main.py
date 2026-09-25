"""ESP CLI entry point: argparse + interactive orchestration."""

from __future__ import annotations

import argparse
import os
import sys

import ezdxf

from cli.base import UserAbort, ask, ask_choice, polyline_length
from cli.crossover_checks import _validate_candidate_live  # noqa: F401 (re-export for tests)
from cli.crossovers import _ask_crossovers_live
from cli.fobs import _ask_fobs
from cli.platforms import _ask_platforms
from cli.sidings import _ask_sidings
from cli.stations import _ask_stations
from cli.tracks import _ask_loop_extensions, _ask_tracks, _loop_extent_info
from common.constants import LOOP_CROSSOVER_DISTANCE_M
from config.loader import ESPConfig, load_config_from_json
from pipeline.orchestrator import ESPGenerator
from platform_gen.kml_io import convert_kml_to_dxf
from track.crossover.conflicts import (
    platforms_to_restricted_regions,
    stations_to_restricted_regions,
)
from track.generator import TrackGenerationConfig, TrackGenerator
from track.specs import LoopSpec


def _get_dxf_layers(path: str) -> list[str]:
    """Extract drawable layers from a DXF file."""
    doc = ezdxf.readfile(path)
    return sorted({e.dxf.layer for e in doc.modelspace() if e.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE", "SPLINE")})


def _main_center(source_dxf: str, layer: str) -> float:
    """Centre chainage of the MAIN track (half its length)."""
    doc = ezdxf.readfile(source_dxf)
    best: list = []
    best_len = 0.0
    for entity in doc.modelspace():
        if entity.dxf.layer != layer:
            continue
        if entity.dxftype() == "LINE":
            pts = [(entity.dxf.start.x, entity.dxf.start.y),
                   (entity.dxf.end.x, entity.dxf.end.y)]
        elif entity.dxftype() == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in entity.get_points()]
        else:
            continue
        if len(pts) < 2:
            continue
        length = polyline_length(pts)
        if length > best_len:
            best, best_len = pts, length
    if best_len < LOOP_CROSSOVER_DISTANCE_M:
        raise ValueError(
            f"MAIN track on layer {layer!r} is only {best_len:.1f}m - "
            f"a fixed {LOOP_CROSSOVER_DISTANCE_M:.0f}m loop cannot fit."
        )
    return best_len / 2.0


def _interactive_mode() -> ESPConfig:
    """Gather configuration interactively, in dependency order."""
    print("\nESP - Interactive Configuration Mode")
    print("=" * 50)

    # --- source + output ---
    source = ask("Input KML or DXF path")
    if source.lower().endswith(".kml"):
        converted = f"{os.path.splitext(source)[0]}_converted.dxf"
        convert_kml_to_dxf(source, converted)
        source_layer = "MAIN_TRACK"
        print(f"KML converted to DXF: {converted}")
    else:
        converted_layers = _get_dxf_layers(source)
        source_layer = ask_choice("Source main track layer", converted_layers,
                                  converted_layers[0] if converted_layers else "MAIN_TRACK")

    output = ask("Output DXF path", f"{os.path.splitext(source)[0]}_complete.dxf")
    if not output.lower().endswith(".dxf"):
        output = f"{os.path.splitext(output)[0]}.dxf"

    # --- step 1: tracks (loops fixed 750m about the MAIN centre) ---
    if source.lower().endswith(".kml"):
        main_center = _main_center(converted, "MAIN_TRACK")
    else:
        main_center = _main_center(source, source_layer)
    additional_main_lines, loops, additional, main_directions = _ask_tracks(main_center)

    track_names = ["MAIN_LINE"] + [item.name for item in loops + additional_main_lines + additional]

    # --- step 2: loop extensions (overruns) ---
    bounded = [
        item for item in loops + additional
        if isinstance(item, LoopSpec) and item.first_crossover_chainage is not None
    ]
    _ask_loop_extensions(bounded)

    # --- step 2b: dead-end sidings ---
    _siding_extents, _ = _loop_extent_info(loops + additional)
    sidings = _ask_sidings(track_names, main_center, _siding_extents)

    # --- step 3: platforms ---
    platforms = _ask_platforms(track_names, source_dxf=output, output_dxf=output)

    # --- step 4: stations ---
    stations = _ask_stations(platforms)

    # --- step 4b: foot over bridges ---
    fobs = _ask_fobs(track_names, platforms, main_center)

    # --- build tracks in memory (no files written) for live geometry ---
    build_source = converted if source.lower().endswith(".kml") else source
    built = TrackGenerator(TrackGenerationConfig(
        build_source,
        output,
        source_layer,
        loops,
        additional_main_lines + additional,
        main_directions=main_directions,
    )).build_tracks(quiet=True)
    tracks = built.tracks
    main_length = polyline_length(tracks["MAIN_LINE"])

    # --- final loop extents and defined START ranges ---
    loop_extents, start_ranges = _loop_extent_info(loops + additional)
    track_metas: list[tuple] = [("MAIN_LINE", None, None)]
    for item in loops + additional_main_lines + additional:
        track_metas.append((
            item.name,
            getattr(item, "spacing", None),
            str(getattr(item, "side", "LEFT")),
        ))

    # --- restricted regions (platforms + stations, MAIN datum) ---
    restrictions = platforms_to_restricted_regions(
        platforms, tracks, loop_extents)
    restrictions += stations_to_restricted_regions(
        stations, platforms, tracks, loop_extents)
    if restrictions:
        print("\nRestricted regions (crossover footprints are checked):")
        for region in restrictions:
            print(f"  {region.track}: "
                  f"[{min(region.start_chainage, region.end_chainage):.1f}, "
                  f"{max(region.start_chainage, region.end_chainage):.1f}] "
                  f"MAIN m -- {region.reason}")

    # --- step 5: crossovers (live calculate + validate + retry) ---
    crossovers = _ask_crossovers_live(
        track_names, tracks, loop_extents, track_metas, main_length,
        restrictions, start_ranges)

    return ESPConfig(
        source_path=source,
        output_dxf=output,
        track_source_layer=source_layer,
        loops=loops,
        additional_lines=additional_main_lines + additional,
        platforms=platforms,
        stations=stations,
        crossovers=crossovers,
        main_directions=main_directions,
        fobs=fobs,
        sidings=sidings,
    )


def main(argv=None) -> int:
    """CLI entry point."""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="ESP - Clean Railway Drawing Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config config.json
  python main.py
        """,
    )
    parser.add_argument("--config", default=None, help="JSON configuration file")
    args = parser.parse_args(argv)

    try:
        if args.config:
            print(f"Loading configuration from: {args.config}")
            config = load_config_from_json(args.config)
        else:
            config = _interactive_mode()

        generator = ESPGenerator(config)
        generator.run()
        return 0
    except UserAbort as exc:
        print(f"\n{exc}")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
