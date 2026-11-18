import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getTrackCentre, loadKmlAlignment } from './kmlAlignment.js';
import { fillCentredChainages, fillFobCentres } from './config.js';

test('calculates chainage along every metric segment, rather than the endpoint distance', () => {
  const track = { pts_utm: [[500000, 3000000], [500000, 3000600], [500800, 3000600]] };
  assert.deepEqual(getTrackCentre(track), {
    main_length_m: 1400, main_center_m: 700,
    default_c1_m: 325, default_c2_m: 1075,
  });
});

test('uses full coordinate precision instead of the rounded detection label', () => {
  assert.deepEqual(getTrackCentre({ length_m: 1000, pts_utm: [[0, 0], [1000.0008, 0]] }), {
    main_length_m: 1000.001, main_center_m: 500,
    default_c1_m: 125, default_c2_m: 875,
  });
});

test('accepts the exact 750m boundary and ignores duplicate points and altitude', () => {
  assert.deepEqual(getTrackCentre({ pts_utm: [[0, 0, 10], [0, 0, 20], [450, 600, 100]] }), {
    main_length_m: 750, main_center_m: 375,
    default_c1_m: 0, default_c2_m: 750,
  });
});

test('rejects a short track before rounding, matching backend validation', () => {
  assert.throws(() => getTrackCentre({ length_m: 750, pts_utm: [[0, 0], [749.9996, 0]] }), /750m loop cannot fit/);
});

for (const points of [null, [], [[0, 0]], [[0, 0], null], [[0, 0], [NaN, 10]],
  [[0, 0], [Infinity, 0]], [[0, 0], ['1000', 0]], [[0, 0], [1000]]]) {
  test(`rejects missing or invalid coordinates: ${JSON.stringify(points)}`, () => {
    assert.throws(() => getTrackCentre({ pts_utm: points }), /No usable continuous track|invalid metric coordinates/);
  });
}

test('rejects non-finite length even when individual coordinates are finite', () => {
  assert.throws(() => getTrackCentre({ pts_utm: [[-1e308, 0], [1e308, 0]] }), /invalid length/);
});

test('retains automatic loop and FOB defaults without overwriting explicit chainages', () => {
  const centre = getTrackCentre({ pts_utm: [[0, 0], [2000, 0]] });
  const form = {
    loops: [{ c1: '', c2: '' }, { c1: '200', c2: '950' }],
    fobs: [{ chainage: '' }, { chainage: '900' }],
  };
  const filled = fillFobCentres(fillCentredChainages(form, centre), centre);
  assert.equal(Number(filled.loops[0].c1), 625);
  assert.equal(Number(filled.loops[0].c2), 1375);
  assert.equal(Number(filled.fobs[0].chainage), 1000);
  assert.deepEqual(filled.loops[1], form.loops[1]);
  assert.deepEqual(filled.fobs[1], form.fobs[1]);
});

test('uploads KML once and switches detected tracks without another request', async (t) => {
  const candidates = [
    { candidate_id: 'path_0', length_m: 2000, pts_utm: [[0, 0], [2000, 0]] },
    { candidate_id: 'path_1', length_m: 1000, pts_utm: [[0, 0], [0, 1000]] },
  ];
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    requests.push({ url, options });
    return Response.json({ candidate_tracks: candidates });
  });
  const file = new File(['<kml/>'], 'survey.kml', { type: 'application/vnd.google-earth.kml+xml' });
  const loaded = await loadKmlAlignment(file);
  assert.equal(requests.length, 1);
  assert.match(requests[0].url, /\/detect-tracks\?min_length=30$/);
  assert.equal(requests[0].options.method, 'POST');
  assert.equal(requests[0].options.body.get('kml').name, 'survey.kml');
  assert.equal(await requests[0].options.body.get('kml').text(), '<kml/>');
  assert.equal(loaded.track, loaded.tracks[0]);
  assert.equal(loaded.centre.main_length_m, 2000);
  assert.equal(getTrackCentre(loaded.tracks[1]).main_center_m, 500);
  assert.equal(getTrackCentre(loaded.tracks[0]).main_center_m, 1000);
  assert.equal(requests.length, 1);
});

test('does not upload again when detection fails', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json(
    { detail: 'invalid KML geometry' }, { status: 422 },
  ));
  await assert.rejects(loadKmlAlignment(new File(['bad'], 'bad.kml')), /invalid KML geometry/);
  assert.equal(fetch.mock.callCount(), 1);
});

test('reports missing candidate geometry without a fallback centre request', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({ candidate_tracks: [] }));
  await assert.rejects(loadKmlAlignment(new File(['<kml/>'], 'empty.kml')), /No usable continuous track/);
  assert.equal(fetch.mock.callCount(), 1);
});
