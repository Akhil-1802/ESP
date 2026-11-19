import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildConfig, validateForm, fobsNeedingCentre } from './config.js';
import { absoluteChainageAtDistance } from './chainageRange.js';
import { generateDynamicPreview } from './dynamicPreview.js';

const form = () => ({
  kmlFile: { name: 'alignment.kml' }, startKm: '12', startM: '0', mainLength: 2000,
  platforms: [{ track: 'MAIN_LINE' }, { track: 'MAIN_LINE', side: 'RIGHT' }],
  fobs: [{ placementMode: 'fixed', refTrack: 'MAIN_LINE', chainage: '12+850',
    platforms: ['PLATFORM_1', 'PLATFORM_2'] }],
});

test('fixed FOB submits raw absolute chainage instead of a local distance', () => {
  const cfg = buildConfig(form()).fobs[0];
  assert.equal(cfg.position_mode, 'FIXED');
  assert.equal(cfg.absolute_chainage, '12+850');
  assert.equal(cfg.reference_chainage, null);
  assert.deepEqual(validateForm(form()), []);
});

test('absolute FOB validates its datum range and malformed input', () => {
  for (const chainage of ['', 'nan', '12+1000', '11+999', '14+001']) {
    const f = form();
    f.fobs[0].chainage = chainage;
    assert.ok(validateForm(f).some(e => e.startsWith('FOB')));
  }
  const f = form();
  f.startKm = '-0'; f.startM = '100'; f.fobs[0].chainage = '0+050';
  assert.deepEqual(validateForm(f), []);
});

test('fixed FOB is not overwritten with a local centre value before submission', () => {
  assert.deepEqual(fobsNeedingCentre({ fobs: [{ placementMode: 'fixed', chainage: '' }] }), []);
  assert.equal(absoluteChainageAtDistance(form(), 850), '12+850');
  assert.equal(absoluteChainageAtDistance({ startKm: '-0', startM: 100 }, 150), '0+050');
  assert.equal(absoluteChainageAtDistance(form(), null), '');
});

test('live FOB preview converts absolute input to MAIN distance', () => {
  const absolute = generateDynamicPreview(form());
  const zeroDatum = form();
  zeroDatum.startKm = '0';
  zeroDatum.fobs[0].chainage = '850';
  const localEquivalent = generateDynamicPreview(zeroDatum);
  const fobGeometry = (result) => result.svg.match(/<g data-layer="FOB"[\s\S]*?<\/g>/)?.[0];
  assert.ok(absolute.layers.includes('FOB'));
  // Matching SVG geometry proves the nonzero datum is subtracted in the live preview.
  assert.ok(fobGeometry(absolute));
  assert.equal(fobGeometry(absolute), fobGeometry(localEquivalent));
});
