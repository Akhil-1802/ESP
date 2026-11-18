import math

import ezdxf
import pytest

from common.final_plan import align_final_plan
from common.dxf_primitives import draw_arrow_dimension
from config.loader import ESPConfig
from pipeline.orchestrator import ESPGenerator
from track.cal_layout import _draw_cal_row


def test_final_rotation_preserves_relative_geometry_and_blocks(tmp_path):
    path = tmp_path / 'final.dxf'
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(10, 20), (110, 120)], dxfattribs={'layer': 'MAIN_LINE'})
    msp.add_line((10, 30), (20, 40))
    msp.add_text('Station', dxfattribs={'insert': (10, 30), 'rotation': 45})
    block = doc.blocks.new('MARKER')
    block.add_line((0, 0), (5, 0))
    msp.add_blockref('MARKER', (10, 30))
    doc.saveas(path)
    assert align_final_plan(str(path)) == pytest.approx(-math.pi/4)
    result = ezdxf.readfile(path).modelspace()
    pts = list(result.query('LWPOLYLINE')[0])
    assert pts[0][:2] == pytest.approx((10, 20))
    assert pts[1][:2] == pytest.approx((10+math.sqrt(20000), 20))
    line = result.query('LINE')[0]
    assert line.dxf.start.distance(line.dxf.end) == pytest.approx(math.sqrt(200))
    assert result.query('TEXT')[0].dxf.rotation % 360 == pytest.approx(0, abs=1e-8)
    insert = result.query('INSERT')[0]
    assert insert.dxf.insert.isclose(line.dxf.start)
    assert insert.dxf.rotation % 360 == pytest.approx(315)


def test_final_labels_are_horizontal_including_nested_block_instances(tmp_path):
    path = tmp_path / 'labels.dxf'
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 100)], dxfattribs={'layer': 'MAIN_LINE'})
    msp.add_text('Vertical', dxfattribs={'rotation': 90, 'insert': (20, 30)})
    msp.add_mtext('Multiline', dxfattribs={'text_direction': (0, 1, 0)})
    block = doc.blocks.new('LABEL')
    block.add_text('Block label', dxfattribs={'rotation': 30})
    block.add_line((0, 0), (5, 0))
    parent = doc.blocks.new('PARENT')
    parent.add_blockref('LABEL', (5, 0), dxfattribs={'rotation': 20})
    msp.add_blockref('PARENT', (10, 20), dxfattribs={'rotation': 15})
    msp.add_blockref('PARENT', (40, 60), dxfattribs={'rotation': 70})
    doc.saveas(path)
    align_final_plan(str(path))
    result = ezdxf.readfile(path).modelspace()
    assert len(result.query('TEXT')) == 3
    assert all(e.dxf.rotation == pytest.approx(0) for e in result.query('TEXT'))
    assert result.query('MTEXT')[0].get_rotation() == pytest.approx(0)
    assert len(result.query('LINE')) == 2
    assert all(e.dxf.start.distance(e.dxf.end) == pytest.approx(5) for e in result.query('LINE'))


def test_fob_label_keeps_deck_orientation(tmp_path):
    path = tmp_path / 'fob.dxf'
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 100)], dxfattribs={'layer': 'MAIN_LINE'})
    msp.add_text('FOOT OVER BRIDGE', dxfattribs={
        'layer': 'CUSTOM_FOB', 'rotation': 135, 'insert': (20, 30)})
    msp.add_text('Platform', dxfattribs={'rotation': 135})
    from platform_gen.dxf_io import _add_label
    from platform_gen.models import LabelSpec
    _add_label(doc, LabelSpec((20, 30), 'Custom platform name', 1, rotation=50), 'CUSTOM', 1)
    doc.saveas(path)
    align_final_plan(str(path))
    labels = {e.dxf.text: e for e in ezdxf.readfile(path).modelspace().query('TEXT')}
    assert labels['FOOT OVER BRIDGE'].dxf.rotation == pytest.approx(90)
    assert labels['Platform'].dxf.rotation == pytest.approx(0)
    caption = ezdxf.readfile(path).modelspace().query('MTEXT')[0]
    assert caption.get_rotation() == pytest.approx(5)


def test_chainage_labels_keep_marker_orientation(tmp_path):
    path = tmp_path / 'chainages.dxf'
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 100)], dxfattribs={'layer': 'MAIN_LINE'})
    for label, layer in [('100 M', 'CHAINAGE'), ('CH: 1+000', 'STATION'),
                         ('Ch. 1000 M', 'STATION'), ('STATION: TEST', 'STATION'),
                         ('Platform', 'PLATFORM')]:
        msp.add_text(label, dxfattribs={'layer': layer, 'rotation': 135})
    msp.add_line((0, 0), (-10, 10), dxfattribs={'layer': 'CHAINAGE'})
    doc.saveas(path)
    align_final_plan(str(path))
    result = ezdxf.readfile(path).modelspace()
    labels = {e.dxf.text: e.dxf.rotation for e in result.query('TEXT')}
    for caption in ('100 M', 'CH: 1+000', 'Ch. 1000 M'):
        assert labels[caption] == pytest.approx(90)
    assert labels['STATION: TEST'] == pytest.approx(0)
    assert labels['Platform'] == pytest.approx(0)
    marker = result.query('LINE')[0]
    assert marker.dxf.start.x == pytest.approx(marker.dxf.end.x, abs=1e-8)


@pytest.mark.parametrize('angle', [-30, 12, 145])
@pytest.mark.parametrize('in_memory', [False, True])
def test_final_tc_dimensions_stay_horizontal_after_reload_and_regeneration(
    tmp_path, angle, in_memory,
):
    path = tmp_path / 'tc.dxf'
    doc = ezdxf.new('R2010')
    a = math.radians(angle)
    tx, ty = math.cos(a), math.sin(a)
    pa = (20 * tx, 20 * ty)
    pb = (pa[0] - 5.3 * ty, pa[1] + 5.3 * tx)
    doc.modelspace().add_lwpolyline(
        [(0, 0), (100 * tx, 100 * ty)], dxfattribs={'layer': 'MAIN_LINE'})
    draw_arrow_dimension(doc, pa, pb, text='T.C=5.3M', layer='TRACK_CENTERS')
    draw_arrow_dimension(doc, pa, pb, dim_offset=2, layer='PLATFORM-DIM')
    if in_memory:
        align_final_plan(str(path), document=doc)
        doc.saveas(path)
    else:
        doc.saveas(path)
        align_final_plan(str(path))
    result = ezdxf.readfile(path)
    dims = result.modelspace().query('DIMENSION[layer=="TRACK_CENTERS"]')
    assert len(dims) == 1
    dim = dims[0]
    assert tuple(dim.dxf.defpoint2) == pytest.approx((20, 0, 0), abs=1e-8)
    assert tuple(dim.dxf.defpoint3) == pytest.approx((20, 5.3, 0), abs=1e-8)
    assert dim.get_measurement() == pytest.approx(5.3)
    assert dim.dxf.text == 'T.C=<>M'
    assert dim.dxf.text_rotation == 0
    other = result.modelspace().query('DIMENSION[layer=="PLATFORM-DIM"]')[0]
    assert not other.dxf.hasattr('text_rotation')
    # Check both the saved graphical block and a fresh CAD-style rebuild.
    for regenerate in (False, True):
        if regenerate:
            dim.render()
        block = result.blocks[dim.dxf.geometry]
        text = block.query('MTEXT')[0]
        assert text.get_rotation() == pytest.approx(0, abs=1e-8)
        assert '5.3' in text.plain_text()
        assert len(block.query('INSERT[name=="_OBLIQUE"]')) == 2


@pytest.mark.parametrize('angle', [-30, 12])
@pytest.mark.parametrize('local_bend', [0, 23])
def test_final_cal_landing_follows_horizontal_text_and_preserves_tip(
    tmp_path, angle, local_bend,
):
    path = tmp_path / 'cal.dxf'
    doc = ezdxf.new('R2010')
    a = math.radians(angle)
    doc.modelspace().add_lwpolyline(
        [(0, 0), (100 * math.cos(a), 100 * math.sin(a))],
        dxfattribs={'layer': 'MAIN_LINE'})
    local = math.radians(angle + local_bend)
    tangent = (math.cos(local), math.sin(local))
    normal = (-tangent[1], tangent[0])
    assert _draw_cal_row(
        doc, 'LOOP LINE NO-1', 'CAL 750.000M (FM TO FM)',
        (30 * math.cos(a), 30 * math.sin(a)), tangent, normal,
        angle + local_bend, 0, 0, (0, 0), (0, 0), (0, 0), delta_v=1.4,
    )
    original = doc.modelspace().query('LEADER')[0]
    run = original.vertices[1].distance(original.vertices[2])
    label = doc.entitydb[original.dxf.annotation_handle]
    clearance = (label.dxf.align_point - original.vertices[2]).magnitude
    align_final_plan(str(path), document=doc)
    doc.saveas(path)
    result = ezdxf.readfile(path)
    leader = result.modelspace().query('LEADER')[0]
    tip, elbow, landing = leader.vertices
    text = result.entitydb[leader.dxf.annotation_handle]
    assert tuple(tip) == pytest.approx((30, 0, 0), abs=1e-8)
    assert text.dxf.rotation == 0
    assert elbow[1] == pytest.approx(text.dxf.align_point.y)
    assert landing[1] == pytest.approx(text.dxf.align_point.y)
    assert landing[0] - elbow[0] == pytest.approx(run)
    assert text.dxf.align_point.x - landing[0] == pytest.approx(clearance)
    # A third virtual LINE would be the unwanted automatic hook.
    assert len([e for e in leader.virtual_entities() if e.dxftype() == 'LINE']) == 2


@pytest.mark.parametrize('finalized', [False, True])
def test_pipeline_applies_alignment_only_when_requested(tmp_path, finalized):
    source = tmp_path / 'source.dxf'
    output = tmp_path / 'output.dxf'
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (1000, 1000), dxfattribs={'layer': 'MAIN_TRACK'})
    doc.saveas(source)
    ESPGenerator(ESPConfig(source_path=str(source), output_dxf=str(output),
                           track_source_layer='MAIN_TRACK',
                           align_final_plan_to_x_axis=finalized)).run()
    pts = list(ezdxf.readfile(output).modelspace().query('LWPOLYLINE[layer=="MAIN_LINE"]')[0])
    if finalized:
        assert pts[-1][1] == pytest.approx(pts[0][1], abs=1e-7)
        assert pts[-1][0] > pts[0][0]
    else:
        assert abs(pts[-1][1]-pts[0][1]) > 900
