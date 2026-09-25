"""FOB wizard."""

from __future__ import annotations

from cli.base import (
    ask_choice,
    ask_count,
    ask_nonnegative,
    ask_positive,
)
from common.constants import (
    DEFAULT_FOB_WIDTH_M,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
)
from config.loader import PlatformRequest
from fob.config import FOBConfig


def _ask_fobs(track_names: list[str], platforms: list[PlatformRequest],
              main_center: float | None = None) -> list[FOBConfig]:
    """Step 4b: foot over bridges (needs platforms only).

    Only the reference track, platforms to connect, reference chainage
    and deck width are asked. Platforms are picked first so the prompt
    can show their approximate MAIN-datum extent; span, position and
    orientation are derived from the platform boundaries at generation
    time. The extent is approximate (centred lengths) - generation still
    validates the chainage strictly.
    """
    print("\nFoot Over Bridge Configuration")
    print("=" * 50)
    print("The deck span is derived from the platform boundaries -")
    print("no start/end coordinates are asked.")
    print(f"Design limits: {FOB_VERTICAL_CLEARANCE_M:g} m vertical "
          f"clearance above rail, {FOB_MAX_SPAN_M:g} m maximum span.")
    fobs: list[FOBConfig] = []
    available = [item.config.output_layer for item in platforms]
    if not available:
        print("  (no platforms - skipping FOBs)")
        return fobs
    by_layer = {item.config.output_layer: item.config for item in platforms}
    for number in range(1, ask_count("Number of foot over bridges") + 1):
        print(f"\nFOB {number}")
        reference_track = ask_choice("  Reference track", track_names, "MAIN_LINE")
        count = ask_count("  Number of platforms to connect", 2)
        while count < 2:
            print("  A FOB must connect at least two platforms.")
            count = ask_count("  Number of platforms to connect", 2)
        picked: list[str] = []
        for _ in range(count):
            layer = ask_choice("  Platform layer", available)
            if layer not in picked:
                picked.append(layer)
        extent_hint = ""
        if main_center:
            lengths = [float(getattr(by_layer[layer], "platform_length", 0.0) or 0.0)
                       for layer in picked]
            if max(lengths, default=0.0) > 0:
                half = max(lengths) / 2.0
                extent_hint = (f" (platforms approx "
                               f"[{main_center - half:.0f}-{main_center + half:.0f}])")
        reference_chainage = ask_nonnegative(
            f"  Reference chainage (MAIN m, blank = MAIN centre){extent_hint}",
            float(main_center) if main_center else 0.0)
        width = ask_positive("  FOB width (m)", DEFAULT_FOB_WIDTH_M)
        ext = ask_nonnegative("  Extend beyond platform edges (m, 0 = none)", 0.0)
        ext_start = ext_end = 0.0
        if ext > 0:
            side = ask_choice(f"  Extend FOB {number} from",
                              ["START", "END", "BOTH"], "BOTH")
            if side in ("START", "BOTH"):
                ext_start = ext
            if side in ("END", "BOTH"):
                ext_end = ext
        print("  Landing arms run parallel to the track from the deck "
              "edge over each platform (0 = none).")
        print("  Arm side LEFT = toward lower chainage, "
              "RIGHT = toward higher chainage.")
        arms: dict[str, dict] = {}
        for layer in picked:
            length = ask_nonnegative(f"  Arm along {layer} (m, 0 = none)", 0.0)
            if length <= 0:
                continue
            arms[layer] = {
                "length": length,
                "side": ask_choice(f"  Arm on {layer} to", ["LEFT", "RIGHT"],
                                   "LEFT"),
            }
        fobs.append(FOBConfig(
            reference_track=reference_track,
            reference_chainage=reference_chainage,
            platforms=picked,
            width=width,
            extend_start_m=ext_start,
            extend_end_m=ext_end,
            arms=arms,
        ))
    return fobs
