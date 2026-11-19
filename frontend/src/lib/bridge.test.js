import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { buildConfig, validateForm } from './config.js';
import { parseAbsoluteChainage, alignmentStartMetres, resolveBridgeDistance, bridgeTypeLabel } from './bridgePlacement.js';
import { generateDynamicPreview } from './dynamicPreview.js';

const base = () => ({
  kmlFile: { name: 'ESP.kml' }, loops: [], platforms: [], stations: [], bridges: [],
  startKm: '12', startM: '0', mainLength: 2000,
});
describe('bridges', () => {
  it('serializes fixed placement without stale offset fields', () => {
    const cfg = buildConfig({ ...base(), bridges: [{
      bridgeType: 'RCC_BOX', placementMode: 'fixed', chainage: '12+850',
      offset: '-1', stationBuildingIndex: 99, width: '12',
    }] });
    assert.equal(cfg.bridges[0].chainage, '12+850');
    assert.equal(cfg.bridges[0].position_mode, 'FIXED');
    assert.equal(cfg.bridges[0].bridge_type, 'RCC_BOX');
    assert.equal(cfg.bridges[0].width, 12);
    assert.equal('station_index' in cfg.bridges[0], false);
    assert.equal('offset' in cfg.bridges[0], false);
  });
  it('serializes offset with explicit building identity and custom type', () => {
    const cfg = buildConfig({ ...base(), bridges: [{
      bridgeType: 'OTHER', customType: 'Steel girder', placementMode: 'offset',
      stationBuildingIndex: 1, offset: '100', direction: 'DECREASING',
    }] });
    assert.equal(cfg.bridges[0].station_index, 1);
    assert.equal(cfg.bridges[0].custom_type, 'Steel girder');
    assert.equal(cfg.bridges[0].offset, 100);
    assert.equal('chainage' in cfg.bridges[0], false);
  });
  it('accepts fixed placement without a platform or station', () => {
    assert.deepEqual(validateForm({ ...base(), bridges: [{
      placementMode: 'fixed', bridgeType: 'PSC_SLAB', chainage: '12+850',
    }] }), []);
  });
  it('validates missing station, custom type and offset', () => {
    const errors = validateForm({ ...base(), bridges: [{
      bridgeType: 'OTHER', placementMode: 'offset', offset: '-1', width: '0',
    }] });
    assert.ok(errors.some(e => e.includes('type/name')));
    assert.ok(errors.some(e => e.includes('reference station building')));
    assert.ok(errors.some(e => e.includes('offset must')));
    assert.ok(errors.some(e => e.includes('width must')));
  });
  it('rejects invalid or out-of-range chainage', () => {
    for (const chainage of ['nan', '', '12+1000', '11+999', '14+001']) {
      assert.ok(validateForm({ ...base(), bridges: [{ placementMode: 'fixed', chainage }] }).length);
    }
    assert.equal(parseAbsoluteChainage('-0+100'), -100);
    assert.equal(parseAbsoluteChainage('12.850 KM'), 12850);
    assert.equal(alignmentStartMetres({ startKm: '-0', startM: '100' }), -100);
    assert.equal(buildConfig({ ...base(), startKm: '-0', startM: '100' }).start_km, '-0');
    assert.equal(alignmentStartMetres({ startKm: '', startM: '100' }), 100);
  });
  it('resolves both offset directions and absolute chainage consistently', () => {
    assert.equal(resolveBridgeDistance(base(), { placementMode: 'fixed', chainage: '12+850' }), 850);
    assert.equal(resolveBridgeDistance(base(), { offset: 100, direction: 'INCREASING' }, { start: 480, end: 520 }), 620);
    assert.equal(resolveBridgeDistance(base(), { offset: 100, direction: 'DECREASING' }, { start: 480, end: 520 }), 380);
    assert.equal(bridgeTypeLabel({ bridgeType: 'OTHER', customType: 'Steel girder' }), 'Steel girder');
  });
  it('previews type captions and keeps fixed mode independent of stale station inputs', () => {
    const preview = generateDynamicPreview({ ...base(), bridges: [
      { placementMode: 'fixed', chainage: '12+850', bridgeType: 'PSC_SLAB' },
      { placementMode: 'fixed', chainage: '13+000', bridgeType: 'OTHER', customType: 'Steel girder' },
    ] });
    assert.ok(preview.svg.includes('PSC SLAB BRIDGE'));
    assert.ok(preview.svg.includes('Steel girder BRIDGE'));
    assert.ok(preview.layers.includes('BRIDGE_1'));
    assert.ok(preview.layers.includes('BRIDGE_2'));
  });
});
