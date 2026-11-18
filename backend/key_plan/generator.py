"""Generate only the schematic; never rerun ESP generation or AUTO planning."""

from .config import KeyPlanOptions
from .drawing import draw_scene
from .layout import build_scene


def generate_key_plan(snapshot, options: KeyPlanOptions | None = None):
    scene = build_scene(snapshot, options or KeyPlanOptions())
    return draw_scene(scene)
