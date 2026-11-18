"""ESP pipeline orchestrator: tracks -> platforms -> crossovers -> stations."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

import ezdxf

from config.loader import ESPConfig
from common.final_plan import align_final_plan
from platform_gen.kml_io import build_kml_document, convert_kml_to_dxf
from .context import GenerationContext

from .steps import (
    BoundaryMixin,
    CalLabelMixin,
    ChainageMixin,
    CrossoverMixin,
    FencingMixin,
    FobMixin,
    GradientMixin,
    RobMixin,
    FoulingMixin,
    PlatformMixin,
    SidingMixin,
    StationMixin,
    TrackMixin,
)

__all__ = ["ESPGenerator"]


class ESPGenerator(
    TrackMixin,
    PlatformMixin,
    CrossoverMixin,
    StationMixin,
    SidingMixin,
    FoulingMixin,
    FencingMixin,
    FobMixin,
    RobMixin,
    GradientMixin,
    ChainageMixin,
    CalLabelMixin,
    BoundaryMixin,
):
    """Main orchestrator for track, platform, crossover, and station generation."""

    def __init__(self, config: ESPConfig):
        self.config = config
        self.source_dxf = config.source_path
        self.platform_layers: list[str] = []
        self._fencing_jobs: list = []
        self._crossover_results: list = []
        self._siding_results: list = []
        self._fouling_marks: list = []
        self._loop_cuts: dict = {}
        self._loop_trim_extents: dict = {}
        self._loop_full_lines: dict = {}
        self._main_line_trim_range: tuple[float, float] | None = None
        self.context = None
        self.timings: dict[str, float] = {}
        self.key_plan_snapshot = None
        self._key_plan_platform_results = []
        self._key_plan_building_results = []
        self._key_plan_fob_outlines = []
        self._key_plan_original_tracks = {}
        self._cal_summary = {}

    def _run_stage(self, name, action, *args, **kwargs):
        start = perf_counter()
        try:
            return action(*args, **kwargs)
        finally:
            self.timings[name] = perf_counter() - start
            print(f"   [timing] {name}: {self.timings[name]:.3f}s")

    def _prepare_source(self) -> None:
        """Convert KML to DXF if needed."""
        if self.context is not None and self.context.in_memory and self.source_dxf.lower().endswith(".kml"):
            self.context.document = build_kml_document(
                self.source_dxf, selected_track_id=getattr(self.config, "selected_track_id", None))
            hit = self.context.document._esp_kml_cache_hit
            print(f"   [cache] KML alignment: {'hit' if hit else 'miss'}")
            return
        if self.source_dxf.lower().endswith(".kml"):
            converted = f"{Path(self.source_dxf).with_suffix('')}_converted.dxf"
            track_id = getattr(self.config, "selected_track_id", None)
            convert_kml_to_dxf(self.source_dxf, converted, selected_track_id=track_id)
            self.source_dxf = str(converted)
        if self.context is not None and self.context.in_memory:
            self.context.document = ezdxf.readfile(self.source_dxf)
            self.context.source_dxf = self.source_dxf

    def run(self, *, in_memory: bool = True) -> str:
        """Save once by default; disk checkpoints remain for diagnostic comparisons."""
        self.context = GenerationContext(config=self.config, source_dxf=self.source_dxf, in_memory=in_memory)
        self.timings = self.context.timings
        self.key_plan_snapshot = None
        self._key_plan_platform_results = []
        self._key_plan_building_results = []
        self._key_plan_fob_outlines = []
        self._cal_summary = {}
        start = perf_counter()
        try:
            return self._run_pipeline()
        finally:
            self.timings["total"] = perf_counter() - start
            print(f"   [timing] total: {self.timings['total']:.3f}s")
            self.context.in_memory = False
            self.context.document = None
            self.context.polygon_cache.clear()
            self.context.tracks.clear()
            self._key_plan_original_tracks.clear()
            self._key_plan_platform_results.clear()
            self._key_plan_building_results.clear()
            self._key_plan_fob_outlines.clear()

    def _run_pipeline(self) -> str:
        """Execute the complete generation workflow: tracks -> platforms -> crossovers -> stations -> sidings."""
        print("🚂 ESP Generator - Clean Railway Drawing Generator")
        print("=" * 50)

        # Step 1: Prepare source
        print("\n📋 Preparing source...")
        self._run_stage("source", self._prepare_source)

        # Step 2: Generate tracks
        print("🛤️  Generating tracks...")
        tracks = self._run_stage("tracks", self.build_tracks)
        if self.config.enable_main_line_trim and self.config.align_final_plan_to_x_axis:
            self._key_plan_original_tracks = {name: list(points) for name, points in tracks.items()}
        print(f"   ✓ Generated {len(tracks)} track(s)")

        # Step 3: Generate platforms
        print("🏗️  Generating platforms...")
        if self.config.platforms:
            self._run_stage("platforms", self._generate_platforms, tracks)
            print(f"   ✓ Generated {len(self.config.platforms)} platform(s)")

        # Step 4: Generate crossovers
        print("🚧 Generating crossovers...")
        if self.config.crossovers or getattr(self.config, "crossover_preset", None):
            self._run_stage("crossovers", self._generate_crossovers, tracks)
            print(f"   ✓ Generated {len(self.config.crossovers)} crossover(s)")

        # Step 5: Generate stations
        print("🏢 Generating stations...")
        if self.config.stations:
            self._run_stage("stations", self._generate_stations)
            print(f"   ✓ Generated {len(self.config.stations)} station(s)")

        # Step 6: Generate sidings (needs crossover results + stations)
        if getattr(self.config, "sidings", None):
            print("🛤️  Generating sidings...")
            self._run_stage("sidings", self._generate_sidings, tracks)
            print(f"   ✓ Generated {len(self.config.sidings)} siding(s)")

        # Step 6b: Automatic fouling marks (needs tracks + crossovers + sidings).
        print("🚩 Generating fouling marks (auto, < 5.3 m)...")
        self._run_stage("fouling", self._generate_fouling_marks, tracks)

        # Step 7: Generate fencing (needs stations in place for exclusion)
        if getattr(self, "_fencing_jobs", None):
            self._run_stage("fencing", self._generate_fencing)

        # Step 8: Generate foot over bridges (needs platforms in place)
        if getattr(self.config, "fobs", None):
            print("🌉 Generating foot over bridges...")
            self._run_stage("fobs", self._generate_fobs, tracks)
            print(f"   ✓ Generated {len(self.config.fobs)} FOB(s)")

        # Step 8b: Generate road over bridges (needs tracks and platforms in place)
        if getattr(self.config, "robs", None):
            print("🌉 Generating road over bridges (ROB)...")
            self._run_stage("robs", self._generate_robs, tracks)
            print(f"   ✓ Generated {len(self.config.robs)} ROB(s)")

        # Step 8c: Generate gradient annotations
        if getattr(self.config, "gradients", None):
            print("📐 Generating gradient annotations...")
            self._run_stage("gradients", self._generate_gradients, tracks)
            print(f"   ✓ Generated {len(self.config.gradients)} gradient annotation(s)")

        # Step 9: Station-relative & alignment interval chainage labels
        print("📏 Generating alignment interval chainages...")
        try:
            self._run_stage("alignment_chainages", self._generate_alignment_interval_chainages, tracks)
        except Exception as exc:
            print(f"   ! Alignment interval chainages skipped ({exc})")

        print("📏 Generating station-relative chainage labels...")
        try:
            self._run_stage("station_chainages", self._generate_station_chainage_labels, tracks)
        except Exception as exc:
            print(f"   ! Chainage labels skipped ({exc})")

        # Step 10: Trim main lines past outermost SRJs (50m margin - disabled by default)
        if getattr(self.config, "enable_main_line_trim", False):
            print("✂️  Trimming main lines past outermost SRJs...")
            try:
                self._run_stage("trim", self._trim_main_lines_to_srj, tracks)
            except Exception as exc:
                print(f"   ! Main line trim skipped ({exc})")

        # Step 11: LOOP end-to-end + MAIN FM-to-FM CAL callouts
        print("🏷️  Generating CAL labels...")
        try:
            self._run_stage("cal_labels", self._generate_cal_labels, tracks)
        except Exception as exc:
            print(f"   ! CAL labels skipped ({exc})")

        # Step 12: Land boundary (green dashed line, 40m from station / 70m from last entity)
        print("🗺️  Generating land boundary...")
        try:
            self._run_stage("boundary", self._generate_land_boundary, tracks)
        except Exception as exc:
            print(f"   ! Land boundary skipped ({exc})")

        if getattr(self.config, "align_final_plan_to_x_axis", False):
            if getattr(self.config, "enable_main_line_trim", False):
                from key_plan.snapshot import capture_snapshot
                self.key_plan_snapshot = self._run_stage(
                    "key_plan_snapshot", capture_snapshot, self, tracks, self._load_document(),
                    self._key_plan_original_tracks["MAIN_LINE"],
                )
            self._run_stage("rotation", align_final_plan, self.config.output_dxf,
                            document=self._load_document() if self.context.in_memory else None)

        if self.context.in_memory:
            Path(self.config.output_dxf).parent.mkdir(parents=True, exist_ok=True)
            self._run_stage("save", self.context.document.saveas, self.config.output_dxf)

        print("\n" + "=" * 50)
        print(f"✅ Complete DXF written: {Path(self.config.output_dxf).absolute()}")
        return self.config.output_dxf
