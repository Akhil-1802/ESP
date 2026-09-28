import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { buildConfig, getPlatformBounds, validateForm } from './config.js';

const base = () => ({
  kmlFile: { name: 'ESP.kml' },
  outputDxf: 'ESP_new6.dxf',
  trackSourceLayer: 'MAIN_TRACK',
  loops: [],
  mainLines: [],
  mainLineDirection: 'UP',
  additionalLines: [],
  platforms: [],
  crossoverMode: 'manual',
  crossovers: [],
  stations: [],
  fobs: [],
  robs: [],
});

describe('robs', () => {
  it('buildConfig serializes ROBs with defaults and custom values', () => {
    const f = {
      ...base(),
      platforms: [{ track: 'MAIN_LINE', length: 550 }],
      robs: [
        { platform: 'PLATFORM_1', referenceEnd: 'START', offset: '50.0', width: '10.0' },
        { platform: 'PLATFORM_1', referenceEnd: 'END', offset: '75.0', width: '14.0' },
      ],
    };
    const cfg = buildConfig(f);
    assert.equal(cfg.robs.length, 2);
    assert.deepEqual(cfg.robs[0], {
      id: 'ROB_1',
      platform: 'PLATFORM_1',
      reference_end: 'START',
      offset: 50,
      width: 10,
      reference_track: 'MAIN_LINE',
      block_name: 'SGFD',
      output_layer: 'SGFD',
      tracks: [],
      chainage: null,
      add_dimension: true,
      add_chainage: false,
    });
    assert.deepEqual(cfg.robs[1], {
      id: 'ROB_2',
      platform: 'PLATFORM_1',
      reference_end: 'END',
      offset: 75,
      width: 14,
      reference_track: 'MAIN_LINE',
      block_name: 'SGFD',
      output_layer: 'SGFD',
      tracks: [],
      chainage: null,
      add_dimension: true,
      add_chainage: false,
    });
  });

  it('getPlatformBounds derives start and end chainage for platform', () => {
    const f = {
      ...base(),
      mainLength: 1500,
      platforms: [
        { track: 'MAIN_LINE', length: 550, centerOnTrack: true },
        { track: 'MAIN_LINE', length: 400, centerOnTrack: false, startChainage: 200 },
      ],
    };
    const b1 = getPlatformBounds(f, 'PLATFORM_1');
    assert.ok(b1);
    assert.equal(b1.start, 475);
    assert.equal(b1.end, 1025);
    assert.equal(b1.length, 550);

    const b2 = getPlatformBounds(f, 'PLATFORM_2');
    assert.ok(b2);
    assert.equal(b2.start, 200);
    assert.equal(b2.end, 600);
    assert.equal(b2.length, 400);

    assert.equal(getPlatformBounds(f, 'NONEXISTENT'), null);
  });

  it('validateForm validates ROB fields', () => {
    const valid = {
      ...base(),
      platforms: [{ track: 'MAIN_LINE' }],
      robs: [{ platform: 'PLATFORM_1', referenceEnd: 'START', offset: '50', width: '10' }],
    };
    assert.deepEqual(validateForm(valid), []);

    const invalid = {
      ...base(),
      platforms: [],
      robs: [{ platform: '', referenceEnd: 'INVALID', offset: '-5', width: '0' }],
    };
    const errs = validateForm(invalid);
    assert.ok(errs.some((e) => e.includes('requires at least one platform')));
    assert.ok(errs.some((e) => e.includes('platform selection is required')));
    assert.ok(errs.some((e) => e.includes('platform end must be either START or END')));
    assert.ok(errs.some((e) => e.includes('offset must be a number >= 0')));
    assert.ok(errs.some((e) => e.includes('width must be a number > 0')));
  });
});
