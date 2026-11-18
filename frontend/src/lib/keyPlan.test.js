import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateDxf, generateKeyPlan } from './api.js';
import { dxfToSvg } from './dxfPreview.js';

test('finalized generation exposes its ID; key plan sends the ID and presentation options', async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return new Response('DXF', { headers: {
      'X-ESP-Generation-ID': 'a'.repeat(32),
      'Content-Disposition': 'attachment; filename="key.dxf"',
    } });
  };
  try {
    const final = await generateDxf({ config: { enable_main_line_trim: true }, kmlFile: new File(['kml'], 'track.kml') });
    assert.equal(final.generationId, 'a'.repeat(32));
    const options = { width: 840, height: 300 };
    const plan = await generateKeyPlan({ generationId: final.generationId, options });
    assert.ok(requests[1].url.endsWith('/key-plan'));
    assert.equal(requests[1].options.headers['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(requests[1].options.body), { generation_id: final.generationId, options });
    assert.equal(await plan.blob.text(), 'DXF');
    assert.equal(plan.filename, 'key.dxf');
  } finally {
    globalThis.fetch = original;
  }
});

test('expired snapshots surface the re-finalization message and HTTP status', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Finalize the ESP again.' }), {
    status: 410, headers: { 'Content-Type': 'application/json' },
  });
  try {
    await assert.rejects(generateKeyPlan({ generationId: 'a'.repeat(32), options: {} }),
      (error) => error.status === 410 && error.message === 'Finalize the ESP again.');
  } finally {
    globalThis.fetch = original;
  }
});

test('key-plan preview fits the frame and retains native text without duplicate crossover badges', () => {
  const dxf = [
    '0', 'SECTION', '2', 'ENTITIES',
    '0', 'LWPOLYLINE', '8', 'KEY_PLAN_FRAME', '90', '4', '70', '1',
    '10', '0', '20', '0', '10', '420', '20', '0',
    '10', '420', '20', '150', '10', '0', '20', '150',
    '0', 'LWPOLYLINE', '8', 'KEY_PLAN_CROSSOVER', '90', '2', '70', '0',
    '10', '50', '20', '60', '10', '150', '20', '90',
    '0', 'TEXT', '8', 'KEY_PLAN_TEXT', '10', '210', '20', '140', '40', '2',
    '1', 'KEY PLAN (NOT TO SCALE)', '50', '0',
    '0', 'LWPOLYLINE', '8', 'KEY_PLAN_OVERRUN', '90', '2', '70', '0',
    '10', '30', '20', '90', '10', '50', '20', '90',
    '0', 'LWPOLYLINE', '8', 'KEY_PLAN_DEAD_END', '90', '4', '70', '0',
    '10', '28', '20', '92', '10', '30', '20', '92',
    '10', '30', '20', '88', '10', '28', '20', '88',
    '0', 'TEXT', '8', 'KEY_PLAN_DIRECTION_TEXT', '10', '80', '20', '65', '40', '2',
    '1', 'UP MAIN LINE', '50', '0',
    '0', 'ENDSEC', '0', 'EOF', '',
  ].join('\n');
  const result = dxfToSvg(dxf, { keyPlan: true });
  assert.equal(result.w, 462);
  assert.equal(result.h, 165);
  assert.ok(result.svg.includes('KEY PLAN (NOT TO SCALE)'));
  assert.ok(!result.svg.includes('OVER RUN'));
  assert.ok(result.svg.includes('UP MAIN LINE'));
  assert.ok(result.layers.some((layer) => layer.name === 'KEY_PLAN_DEAD_END'));
  assert.ok(result.svg.includes('font-family: Arial'));
  assert.ok(!result.svg.includes('class="cad-crossover-tag"'));
});
