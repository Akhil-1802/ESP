"""Generate only the schematic; never rerun ESP generation or AUTO planning."""

from ...formats.dxf.key_plan import draw_scene
from .config import KeyPlanOptions
from .layout import build_scene


def generate_key_plan(snapshot, options: KeyPlanOptions | None = None):
    scene = build_scene(snapshot, options or KeyPlanOptions())
    return draw_scene(scene)
