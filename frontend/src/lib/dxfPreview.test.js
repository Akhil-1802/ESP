import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { dxfToSvg } from './dxfPreview.js';

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

  it('rejects input with no drawable entities', () => {
    assert.throws(() => dxfToSvg('0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n'), /No drawable/);
  });
});
