import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { dxfToSvg, getLayerStyle, FORCE_STROKE_COLOR } from './dxfPreview.js';

const DXF = [
  '0', 'SECTION', '2', 'ENTITIES',
  '0', 'LINE', '8', 'MAIN_LINE',
  '10', '0.0', '20', '0.0', '30', '0.0',
  '11', '10.0', '21', '5.0', '31', '0.0',
  '0', 'LWPOLYLINE', '8', 'PLATFORM_1',
  '90', '3', '70', '1',
  '10', '0.0', '20', '0.0',
  '10', '10.0', '20', '0.0',
  '10', '10.0', '20', '5.0',
  '0', 'CIRCLE', '8', 'SRJ',
  '10', '20.0', '20', '20.0', '40', '1.0',
  '0', 'TEXT', '8', 'LABELS',
  '10', '5.0', '20', '2.5', '40', '1.0', '1', 'F.O.B.', '50', '0.0',
  '0', 'ENDSEC', '0', 'EOF', '',
].join('\n');

function boundaryDxf(lineType = 'ESP_LAND_BOUNDARY_DASHED', globalScale = 1, entityScale = 1) {
  return [
    '0', 'SECTION', '2', 'HEADER', '9', '$LTSCALE', '40', String(globalScale), '0', 'ENDSEC',
    '0', 'SECTION', '2', 'TABLES',
    '0', 'TABLE', '2', 'LTYPE', '70', '1',
    '0', 'LTYPE', '2', 'ESP_LAND_BOUNDARY_DASHED', '70', '0',
    '3', 'Land boundary: 8m dash, 5m gap', '72', '65', '73', '2', '40', '13',
    '49', '8', '74', '0', '49', '-5', '74', '0',
    '0', 'ENDTAB', '0', 'ENDSEC',
    '0', 'SECTION', '2', 'ENTITIES',
    '0', 'LWPOLYLINE', '8', 'LAND_BOUNDARY', '62', '3',
    ...(lineType ? ['6', lineType] : []), '48', String(entityScale),
    '90', '2', '70', '128', '10', '0', '20', '70', '10', '1000', '20', '70',
    '0', 'ENDSEC', '0', 'EOF', '',
  ].join('\n');
}

describe('dxfToSvg', () => {
  it('flattens LINE / LWPOLYLINE / CIRCLE / TEXT into one SVG', () => {
    const out = dxfToSvg(DXF);
    assert.ok(out.svg.includes('<svg'));
    assert.ok(out.svg.includes('<line '));
    assert.ok(out.svg.includes('<path '));
    assert.ok(out.svg.includes('F.O.B.'));
    assert.ok(out.svg.includes('viewBox'));
    assert.ok(out.w > 0 && out.h > 0);
    assert.equal(out.entities, 4);
  });

  it('applies red stroke color preview matching engineering CAD standard', () => {
    assert.equal(FORCE_STROKE_COLOR, '#ff0000');
    assert.equal(getLayerStyle('MAIN_LINE').color, '#ff0000');
    assert.equal(getLayerStyle('MAIN_LINE').category, 'track');
    assert.equal(getLayerStyle('PLATFORM_1').color, '#ff0000');
    assert.equal(getLayerStyle('TURNOUT').color, '#ff0000');
  });

  it('renders green boundary dashes from the DXF linetype definition', () => {
    const out = dxfToSvg(boundaryDxf());
    assert.ok(out.svg.includes('data-layer="LAND_BOUNDARY"'));
    assert.ok(out.svg.includes(`stroke="${getLayerStyle('LAND_BOUNDARY').color}"`));
    assert.equal(getLayerStyle('LAND_BOUNDARY').color, '#22c55e');
    assert.ok(out.svg.includes('stroke-dasharray="8 5"'));
  });

  it('honours a continuous boundary instead of masking an old solid DXF with preview dashes', () => {
    const out = dxfToSvg(boundaryDxf('CONTINUOUS'));
    assert.ok(!out.svg.includes('stroke-dasharray'));
    assert.ok(out.svg.includes('stroke="#22c55e"'));
  });

  it('combines global and entity linetype scales when previewing exported dashes', () => {
    const compensated = dxfToSvg(boundaryDxf('ESP_LAND_BOUNDARY_DASHED', 100, 0.01));
    assert.ok(compensated.svg.includes('stroke-dasharray="8 5"'));
    const scaled = dxfToSvg(boundaryDxf('ESP_LAND_BOUNDARY_DASHED', 2, 3));
    assert.ok(scaled.svg.includes('stroke-dasharray="48 30"'));
  });

  it('retains the default dashed boundary style for previews without explicit DXF linetypes', () => {
    assert.ok(dxfToSvg(boundaryDxf('')).svg.includes('stroke-dasharray="8 5"'));
  });

  it('rejects input with no drawable entities', () => {
    assert.throws(() => dxfToSvg('0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n'), /No drawable/);
  });

  it('renders crossover overlay labels C1, C2 over crossover curves in frontend preview', () => {
    const crossoverDxf = [
      '0', 'SECTION', '2', 'ENTITIES',
      '0', 'LINE', '8', 'MAIN_LINE',
      '10', '0.0', '20', '0.0', '30', '0.0',
      '11', '200.0', '21', '0.0', '31', '0.0',
      // Crossover 1 (> 15m)
      '0', 'LWPOLYLINE', '8', 'CROSSOVERS',
      '90', '2', '70', '0',
      '10', '20.0', '20', '0.0',
      '10', '80.0', '20', '5.3',
      // Crossover 2 (> 15m)
      '0', 'LWPOLYLINE', '8', 'CROSSOVERS',
      '90', '2', '70', '0',
      '10', '100.0', '20', '5.3',
      '10', '160.0', '20', '0.0',
      '0', 'ENDSEC', '0', 'EOF', '',
    ].join('\n');

    // Default numbering
    const outDefault = dxfToSvg(crossoverDxf);
    assert.ok(outDefault.svg.includes('class="crossover-badge-text">C1</text>'));
    assert.ok(outDefault.svg.includes('class="crossover-badge-text">C2</text>'));
    assert.ok(outDefault.svg.includes('class="crossover-badge-bg"'));

    // Custom options
    const outCustom = dxfToSvg(crossoverDxf, { crossoverLabels: ['C1_UP', 'C2_DN'] });
    assert.ok(outCustom.svg.includes('class="crossover-badge-text">C1_UP</text>'));
    assert.ok(outCustom.svg.includes('class="crossover-badge-text">C2_DN</text>'));
  });
});
