"""Tests for Gradient Annotation feature."""

import ezdxf
from app.features.drawing_generation.config import (
    ESPConfig,
    GradientRequest,
    PlatformRequest,
    StationRequest,
)
from app.features.drawing_generation.domain.platform.config import PlatformConfig
from app.features.drawing_generation.pipeline.generator import ESPGenerator


def _get_grad_lines(doc):
    lines = []
    for e in doc.modelspace():
        if e.dxf.layer == "GRADIENT":
            if e.dxftype() == "LINE":
                lines.append(e)
            elif e.dxftype() == "INSERT":
                lines.extend([sub for sub in e.virtual_entities() if sub.dxftype() == "LINE"])
    return lines


def _get_grad_texts(doc):
    texts = []
    for e in doc.modelspace():
        if e.dxf.layer == "GRADIENT":
            if e.dxftype() == "TEXT":
                texts.append(e)
            elif e.dxftype() == "INSERT":
                texts.extend([sub for sub in e.virtual_entities() if sub.dxftype() == "TEXT"])
    return texts


def _make_sample_pipeline(
    tmp_path,
    gradients: list[GradientRequest],
    track_coords=((0.0, 0.0), (2000.0, 0.0)),
    station_chainage="125",
):
    src = tmp_path / "src.dxf"
    out = tmp_path / "out.dxf"
    doc = ezdxf.new()
    if len(track_coords) == 2:
        doc.modelspace().add_line(
            track_coords[0], track_coords[1], dxfattribs={"layer": "MAIN_TRACK"}
        )
    else:
        doc.modelspace().add_lwpolyline(
            list(track_coords), dxfattribs={"layer": "MAIN_TRACK"}
        )
    doc.saveas(str(src))

    pcfg = PlatformConfig(
        source_dxf=str(src),
        output_dxf=str(out),
        track_layer="MAIN_LINE",
        platform_type="SIDE",
        side="LEFT",
        center_on_track=True,
        clearance=1.68,
        platform_width=7.0,
        platform_length=550.0,
        platform_name="PLATFORM 1",
        output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT",
    )
    stations = []
    if station_chainage is not None:
        stations.append(
            StationRequest(
                platform_layer="PLATFORM_1",
                building_length=40.0,
                building_width=10.0,
                platform_side="LEFT",
                building_name="STATION BUILDING",
                station_chainage=station_chainage,
            )
        )

    return ESPGenerator(
        ESPConfig(
            source_path=str(src),
            output_dxf=str(out),
            track_source_layer="MAIN_TRACK",
            loops=[],
            additional_lines=[],
            platforms=[PlatformRequest(track_layer="MAIN_LINE", config=pcfg)],
            stations=stations,
            crossovers=[],
            main_directions={"MAIN_LINE": "UP"},
            gradients=gradients,
        )
    ), out
