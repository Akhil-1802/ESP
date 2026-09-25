"""Platform wizard."""

from __future__ import annotations

from cli.base import (
    ask_choice,
    ask_count,
    ask_nonnegative,
    ask_positive,
)
from config.loader import PlatformRequest
from platform_gen.config import PlatformConfig


def _ask_platforms(track_names: list[str], source_dxf: str, output_dxf: str) -> list[PlatformRequest]:
    """Step 2: ask about each platform (before crossovers, so crossover
    footprints can be checked against them)."""
    print("\nPlatform Configuration")
    print("=" * 50)

    platforms: list[PlatformRequest] = []
    for number in range(1, ask_count("Number of platforms", 1) + 1):
        print(f"\nPlatform {number}")
        track = ask_choice("  Track", track_names, "MAIN_LINE")
        platform_type = ask_choice("  Type", ["SIDE", "ISLAND"], "SIDE")
        second = None
        if platform_type == "ISLAND":
            second = ask_choice("  Second track", [name for name in track_names if name != track])

        layer = f"PLATFORM_{number}"
        cfg = PlatformConfig(
            source_dxf, output_dxf, track,
            second_track_layer=second,
            platform_type=platform_type,
            side=ask_choice("  Side", ["LEFT", "RIGHT"], "LEFT"),
            center_on_track=True,
            clearance=ask_positive("  Clearance from track center (m)", 1.68),
            platform_width=ask_positive("  Width (m)", 8.5),
            platform_length=ask_positive("  Length (m)", 550),
            platform_height=ask_positive("  Height above rail (m)", 0.84),
            platform_name="HIGH LEVEL PASSENGER PLATFORM",
            output_layer=layer,
            text_layer=f"{layer}_TEXT",
            stair_length=ask_nonnegative("  Stair length (m, 0 = none)", 0.0) or None,
            stair_width=ask_nonnegative("  Stair width (m, 0 = use platform width)", 0.0) or None,
        )
        platforms.append(PlatformRequest(track, cfg))
    return platforms
