"""Keep the key plan independent from metre-based ESP modelspace geometry."""

import ezdxf
from ezdxf.enums import TextEntityAlignment


def draw_scene(scene):
    doc = ezdxf.new("R2010")
    doc.units = 4  # Millimetres for this separate schematic/template drawing.
    doc.styles.new("KEY_PLAN", dxfattribs={"font": "Arial.ttf"})
    msp = doc.modelspace()
    for item in scene.lines + scene.polygons + scene.texts:
        if item["layer"] not in doc.layers:
            doc.layers.add(item["layer"], color=1)
    for item in scene.lines:
        msp.add_lwpolyline(item["points"], dxfattribs={"layer": item["layer"], "color": 1, "linetype": "CONTINUOUS"})
    for item in scene.polygons:
        msp.add_lwpolyline(item["points"], close=True, dxfattribs={"layer": item["layer"], "color": 1, "linetype": "CONTINUOUS"})
    for item in scene.texts:
        msp.add_text(item["text"], dxfattribs={"height": item["height"], "style": "KEY_PLAN",
            "layer": item["layer"], "color": 1}).set_placement(
                (item["x"], item["y"]), align=TextEntityAlignment.MIDDLE_CENTER)
    doc.set_modelspace_vport(height=scene.height*1.1, center=(scene.width/2, scene.height/2))
    return doc
