"""ESP pipeline orchestrator: tracks -> platforms -> crossovers -> stations."""

from __future__ import annotations

from pathlib import Path

from config.loader import ESPConfig
from platform_gen.kml_io import convert_kml_to_dxf

from .steps import (
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

    def _prepare_source(self) -> None:
        """Convert KML to DXF if needed."""
        if self.source_dxf.lower().endswith(".kml"):
            converted = f"{Path(self.source_dxf).with_suffix('')}_converted.dxf"
            track_id = getattr(self.config, "selected_track_id", None)
            convert_kml_to_dxf(self.source_dxf, converted, selected_track_id=track_id)
            self.source_dxf = str(converted)

    def run(self) -> str:
        """Execute the complete generation workflow: tracks -> platforms -> crossovers -> stations -> sidings."""
        print("🚂 ESP Generator - Clean Railway Drawing Generator")
        print("=" * 50)

        # Step 1: Prepare source
        print("\n📋 Preparing source...")
        self._prepare_source()

        # Step 2: Generate tracks
        print("🛤️  Generating tracks...")
        tracks = self.build_tracks()
        print(f"   ✓ Generated {len(tracks)} track(s)")

        # Step 3: Generate platforms
        print("🏗️  Generating platforms...")
        if self.config.platforms:
            self._generate_platforms(tracks)
            print(f"   ✓ Generated {len(self.config.platforms)} platform(s)")

        # Step 4: Generate crossovers
        print("🚧 Generating crossovers...")
        if self.config.crossovers or getattr(self.config, "crossover_preset", None):
            self._generate_crossovers(tracks)
            print(f"   ✓ Generated {len(self.config.crossovers)} crossover(s)")

        # Step 5: Generate stations
        print("🏢 Generating stations...")
        if self.config.stations:
            self._generate_stations()
            print(f"   ✓ Generated {len(self.config.stations)} station(s)")

        # Step 6: Generate sidings (needs crossover results + stations)
        if getattr(self.config, "sidings", None):
            print("🛤️  Generating sidings...")
            self._generate_sidings(tracks)
            print(f"   ✓ Generated {len(self.config.sidings)} siding(s)")

        # Step 6b: Automatic fouling marks (needs tracks + crossovers + sidings).
        print("🚩 Generating fouling marks (auto, < 5.3 m)...")
        self._generate_fouling_marks(tracks)

        # Step 7: Generate fencing (needs stations in place for exclusion)
        if getattr(self, "_fencing_jobs", None):
            self._generate_fencing()

        # Step 8: Generate foot over bridges (needs platforms in place)
        if getattr(self.config, "fobs", None):
            print("🌉 Generating foot over bridges...")
            self._generate_fobs(tracks)
            print(f"   ✓ Generated {len(self.config.fobs)} FOB(s)")

        # Step 8b: Generate road over bridges (needs tracks and platforms in place)
        if getattr(self.config, "robs", None):
            print("🌉 Generating road over bridges (ROB)...")
            self._generate_robs(tracks)
            print(f"   ✓ Generated {len(self.config.robs)} ROB(s)")

        # Step 8c: Generate gradient annotations
        if getattr(self.config, "gradients", None):
            print("📐 Generating gradient annotations...")
            self._generate_gradients(tracks)
            print(f"   ✓ Generated {len(self.config.gradients)} gradient annotation(s)")

        # Step 9: Station-relative & alignment interval chainage labels
        print("📏 Generating alignment interval chainages...")
        try:
            self._generate_alignment_interval_chainages(tracks)
        except Exception as exc:
            print(f"   ! Alignment interval chainages skipped ({exc})")

        print("📏 Generating station-relative chainage labels...")
        try:
            self._generate_station_chainage_labels(tracks)
        except Exception as exc:
            print(f"   ! Chainage labels skipped ({exc})")

        # Step 10: Trim main lines past outermost SRJs (50m margin - disabled by default)
        if getattr(self.config, "enable_main_line_trim", False):
            print("✂️  Trimming main lines past outermost SRJs...")
            try:
                self._trim_main_lines_to_srj(tracks)
            except Exception as exc:
                print(f"   ! Main line trim skipped ({exc})")

        # Step 11: LOOP end-to-end + MAIN FM-to-FM CAL callouts
        print("🏷️  Generating CAL labels...")
        try:
            self._generate_cal_labels(tracks)
        except Exception as exc:
            print(f"   ! CAL labels skipped ({exc})")

        print("\n" + "=" * 50)
        print(f"✅ Complete DXF written: {Path(self.config.output_dxf).absolute()}")
        return self.config.output_dxf
