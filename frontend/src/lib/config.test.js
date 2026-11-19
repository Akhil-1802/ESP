import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULTS, buildConfig, calculateEndChainage, calculateEndChainageFromKmM, estimateFobSpan, fillCentredChainages, fillFobCentres, fobsNeedingCentre, formatStartChainage, getExtendedLoopEnds, getPlatformBounds, getStationTrackDistance, getTrackRange, loopsNeedingCentre, parseKmM, platformLayers, trackOptions, validateForm } from './config.js';

const base = () => ({
  kmlFile: { name: 'ESP.kml' },
  outputDxf: 'ESP_new6.dxf',
  trackSourceLayer: 'MAIN_TRACK',
  loops: [],
  mainLines: [],
  mainLineDirection: 'UP',
  additionalLines: [],
  platforms: [],
  crossovers: [],
  stations: [],
  fobs: [],
  bridges: [],
});

describe('defaults', () => {
  it('uses one bidirectional MAIN_LINE when no additional MAIN lines are selected', () => {
    const cfg = buildConfig(base());
    assert.deepEqual(cfg.main_directions, {});
    assert.deepEqual(cfg.additional_lines, []);
    assert.deepEqual(cfg.loops, []);
  });

  it('builds numbered MAIN lines with editable UP/DN directions', () => {
    const cfg = buildConfig({
      ...base(),
      mainLineDirection: 'DN',
      mainLines: [
        { spacing: '', side: 'LEFT', direction: '' },
        { spacing: '6.5', side: 'RIGHT', direction: 'UP' },
      ],
    });
    assert.deepEqual(cfg.additional_lines, [
      { name: 'MAIN_LINE_1', spacing: 5.3, side: 'LEFT', direction: 'DN' },
      { name: 'MAIN_LINE_2', spacing: 6.5, side: 'RIGHT', direction: 'UP' },
    ]);
    assert.deepEqual(cfg.main_directions, {
      MAIN_LINE: 'DN', MAIN_LINE_1: 'DN', MAIN_LINE_2: 'UP',
    });
  });

  it('builds MAIN lines with reference_track when specified', () => {
    const cfg = buildConfig({
      ...base(),
      mainLines: [
        { referenceTrack: 'MAIN_LINE', spacing: '5.3', side: 'LEFT', direction: 'DN' },
        { referenceTrack: 'MAIN_LINE_1', spacing: '5.3', side: 'LEFT', direction: 'DN' },
      ],
    });
    assert.deepEqual(cfg.additional_lines, [
      { name: 'MAIN_LINE_1', spacing: 5.3, side: 'LEFT', direction: 'DN', reference_track: 'MAIN_LINE' },
      { name: 'MAIN_LINE_2', spacing: 5.3, side: 'LEFT', direction: 'DN', reference_track: 'MAIN_LINE_1' },
    ]);
  });

  it('blank loop spacing/turnout fall back to 5.3 m / 1:12', () => {
    const cfg = buildConfig({
      ...base(),
      loops: [{ name: '', side: '', spacing: '', c1: '100', c2: '', turnout: '', turnoutVariant: '', crossoverDistance: '', extStart: '', extEnd: '' }],
    });
    assert.equal(cfg.loops.length, 1);
    const loop = cfg.loops[0];
    assert.equal(loop.name, 'LOOP_1');
    assert.equal(loop.spacing, 5.3);
    assert.equal(loop.side, 'LEFT');
    assert.equal(loop.first_crossover_chainage, 100);
    assert.ok(!('second_crossover_chainage' in loop), 'blank C2 is omitted (C1 + distance rule)');
    assert.equal(loop.turnout_designation, '1:12');
    assert.equal(loop.turnout_variant, 'standard');
    assert.equal(loop.crossover_distance_m, 750.0);
  });

  it('explicit values are kept verbatim', () => {
    const cfg = buildConfig({
      ...base(),
      loops: [{ name: 'LOOP_2', side: 'RIGHT', spacing: '6.3', c1: '175.709', c2: '925.709', turnout: '1:8.5', turnoutVariant: 'standard', crossoverDistance: '750', extStart: '120', extEnd: '120' }],
    });
    assert.deepEqual(cfg.loops[0], {
      name: 'LOOP_2',
      spacing: 6.3,
      side: 'RIGHT',
      reference_track: 'MAIN_LINE',
      first_crossover_chainage: 175.709,
      second_crossover_chainage: 925.709,
      turnout_designation: '1:8.5',
      turnout_variant: 'standard',
      crossover_distance_m: 750,
      extend_start_m: 120,
      extend_end_m: 120,
    });
  });

  it('crossover chainage passes AUTO through, turnout defaults to 1:12', () => {
    const cfg = buildConfig({
      ...base(),
      crossovers: [{ from: 'MAIN_LINE', to: 'LOOP_1', chainage: 'auto', direction: '', turnout: '' }],
    });
    assert.deepEqual(cfg.crossovers[0], {
      from_track: 'MAIN_LINE',
      to_track: 'LOOP_1',
      from_chainage_m: 'AUTO',
      turnout: '1:12',
      direction: 'FORWARD',
    });
  });

  it('FOB omits width only when blank is impossible: defaults to 3.0, arms shaped correctly', () => {
    const cfg = buildConfig({
      ...base(),
      fobs: [{
        refTrack: '', chainage: '650', platforms: ['PLATFORM_1', 'PLATFORM_2'],
        width: '', extStart: '', extEnd: '',
        arms: [{ platform: 'PLATFORM_1', length: '20', side: '' }],
      }],
    });
    assert.deepEqual(cfg.fobs[0], {
      reference_track: 'MAIN_LINE',
      reference_chainage: 650,
      platforms: ['PLATFORM_1', 'PLATFORM_2'],
      width: DEFAULTS.fobWidth,
      extend_start_m: 0,
      extend_end_m: 0,
      arms: { PLATFORM_1: { length: 20, side: 'LEFT' } },
    });
  });

  it('FOB arms with blank platform automatically infer unassigned connected platform', () => {
    const cfg = buildConfig({
      ...base(),
      fobs: [{
        refTrack: 'MAIN_LINE',
        chainage: '650',
        platforms: ['PLATFORM_1', 'PLATFORM_2'],
        arms: [
          { platform: '', length: '17', side: 'LEFT' },
          { platform: 'PLATFORM_2', length: '17', side: 'RIGHT' },
        ],
      }],
    });
    assert.deepEqual(cfg.fobs[0].arms, {
      PLATFORM_1: { length: 17, side: 'LEFT' },
      PLATFORM_2: { length: 17, side: 'RIGHT' },
    });
  });

  it('blank C1 previews as null instead of a misleading 0', () => {
    const cfg = buildConfig({ ...base(), loops: [{ name: '', c1: '', c2: '' }] });
    assert.equal(cfg.loops[0].first_crossover_chainage, null);
    assert.ok(!('second_crossover_chainage' in cfg.loops[0]));
  });

  it('platform arms/stairs default to 16.999 m, explicit 0 omits', () => {
    const cfg = buildConfig({
      ...base(),
      platforms: [{ track: 'LOOP_1', type: '', side: '', centerOnTrack: true, clearance: '', width: '', length: '', height: '', name: '', stairLength: '' }],
    });
    assert.equal(cfg.platforms[0].arm_length, 16.999);
    assert.equal(cfg.platforms[0].stair_length, 16.999);
    assert.equal(cfg.platforms[0].platform_width, 7.0);
    const none = buildConfig({
      ...base(),
      platforms: [{ track: 'LOOP_1', stairLength: '0' }],
    });
    assert.ok(!('stair_length' in none.platforms[0]));
    assert.ok(!('arm_length' in none.platforms[0]));
  });

  it('FOB supports dynamic offset and direction from station edge', () => {
    const cfg = buildConfig({
      ...base(),
      fobs: [{
        refTrack: 'MAIN_LINE', chainage: '', platforms: ['PLATFORM_1', 'PLATFORM_2'],
        offset: '50', direction: 'DECREASING',
      }],
    });
    assert.equal(cfg.fobs[0].reference_chainage, null);
    assert.equal(cfg.fobs[0].offset, 50);
    assert.equal(cfg.fobs[0].direction, 'DECREASING');
  });

  it('FOB serializes position_mode correctly for offset and fixed modes', () => {
    const cfgOffset = buildConfig({
      ...base(),
      fobs: [{
        placementMode: 'offset',
        refTrack: 'MAIN_LINE',
        chainage: '831.712', // should be ignored in offset mode
        offset: '40',
        direction: 'INCREASING',
        platforms: ['PLATFORM_1', 'PLATFORM_2'],
      }],
    });
    assert.equal(cfgOffset.fobs[0].position_mode, 'OFFSET');
    assert.equal(cfgOffset.fobs[0].reference_chainage, null);
    assert.equal(cfgOffset.fobs[0].offset, 40);

    const cfgFixed = buildConfig({
      ...base(),
      fobs: [{
        placementMode: 'fixed',
        refTrack: 'MAIN_LINE',
        chainage: '850.5',
        offset: '40', // should be omitted/ignored in fixed mode
        platforms: ['PLATFORM_1', 'PLATFORM_2'],
      }],
    });
    assert.equal(cfgFixed.fobs[0].position_mode, 'FIXED');
    assert.equal(cfgFixed.fobs[0].reference_chainage, null);
    assert.equal(cfgFixed.fobs[0].absolute_chainage, '850.5');
    assert.equal(cfgFixed.fobs[0].offset, undefined);
  });

  it('loop overruns default to 120 m', () => {
    const cfg = buildConfig({ ...base(), loops: [{ name: '', c1: '10', c2: '20' }] });
    assert.equal(cfg.loops[0].extend_start_m, 120);
    assert.equal(cfg.loops[0].extend_end_m, 120);
  });

  it('serializes station building with chainage if provided', () => {
    const cfg = buildConfig({
      ...base(),
      stations: [
        { platform: 'PLATFORM_1', length: '40', width: '10', side: 'RIGHT', name: 'STATION BUILDING', chainage: '68.48' },
        { platform: 'PLATFORM_2', length: '', width: '', side: 'LEFT', name: '', chainage: '' },
      ],
    });
    assert.deepEqual(cfg.stations[0], {
      platform_layer: 'PLATFORM_1',
      building_length: 40,
      building_width: 10,
      platform_side: 'RIGHT',
      building_name: 'STATION BUILDING',
      station_chainage: '68.48',
    });
    assert.deepEqual(cfg.stations[1], {
      platform_layer: 'PLATFORM_2',
      building_length: 40,
      building_width: 10,
      platform_side: 'LEFT',
      building_name: 'STATION 2',
    });
  });
});

describe('helpers', () => {
  it('trackOptions lists MAIN + loop/line names, autonaming blanks like the builder', () => {
    const form = { mainLines: [{}, {}], loops: [{ name: 'LOOP_1' }, { name: '' }], additionalLines: [{ name: 'PROPOSED_LINE_1' }] };
    assert.deepEqual(trackOptions(form), ['MAIN_LINE', 'MAIN_LINE_1', 'MAIN_LINE_2', 'LOOP_1', 'LOOP_2', 'PROPOSED_LINE_1']);
  });

  it('platformLayers enumerates in order', () => {
    assert.deepEqual(platformLayers({ platforms: [{}, {}] }), ['PLATFORM_1', 'PLATFORM_2']);
  });
});

describe('validateForm', () => {
  it('requires the KML file', () => {
    assert.match(validateForm({ ...base(), kmlFile: null }).join('\n'), /KML file/);
    assert.match(validateForm({ ...base(), kmlFile: { name: 'track.txt' } }).join('\n'), /\.kml/);
  });

  it('rejects loop spacing below the 5.3 m minimum', () => {
    const errors = validateForm({ ...base(), loops: [{ name: 'LOOP_1', c1: '10', c2: '20', spacing: '4.0' }] });
    assert.match(errors.join('\n'), /spacing/);
  });

  it('rejects inverted loop chainages', () => {
    const errors = validateForm({ ...base(), loops: [{ name: 'LOOP_1', c1: '500', c2: '100' }] });
    assert.match(errors.join('\n'), /C2/);
  });

  it('rejects an FOB connecting fewer than two platforms', () => {
    const errors = validateForm({
      ...base(),
      fobs: [{ refTrack: 'MAIN_LINE', chainage: '10', platforms: ['PLATFORM_1'], width: '' }],
    });
    assert.match(errors.join('\n'), /at least two platforms/);
  });

  it('accepts a complete valid form', () => {
    const form = {
      ...base(),
      loops: [
        { name: 'LOOP_1', side: 'LEFT', spacing: '', c1: '175.709', c2: '925.709', turnout: '', turnoutVariant: '', crossoverDistance: '', extStart: '120', extEnd: '120' },
        { name: 'LOOP_2', side: 'RIGHT', spacing: '6.3', c1: '175.709', c2: '925.709', turnout: '1:12', turnoutVariant: 'standard', crossoverDistance: '750', extStart: '', extEnd: '' },
      ],
      platforms: [
        { track: 'LOOP_1', type: 'SIDE', side: 'LEFT', centerOnTrack: true, clearance: '', width: '', length: '', height: '', name: '', stairLength: '' },
      ],
      crossovers: [{ from: 'LOOP_1', to: 'MAIN_LINE', chainage: '175.709', direction: 'REVERSE', turnout: '' }],
      fobs: [{ refTrack: 'MAIN_LINE', chainage: '650', platforms: ['PLATFORM_1', 'PLATFORM_2'], width: '', extStart: '', extEnd: '', arms: [] }],
    };
    assert.deepEqual(validateForm(form), []);
  });

  it('validates MAIN line reference tracks in creation order', () => {
    const bad = validateForm({
      ...base(),
      mainLines: [
        { referenceTrack: 'MAIN_LINE_2', spacing: '5.3', side: 'LEFT', direction: 'DN' },
      ],
    });
    assert.match(bad.join('\n'), /reference track must be one of: MAIN_LINE/);

    const good = validateForm({
      ...base(),
      mainLines: [
        { referenceTrack: 'MAIN_LINE', spacing: '5.3', side: 'LEFT', direction: 'DN' },
        { referenceTrack: 'MAIN_LINE_1', spacing: '5.3', side: 'LEFT', direction: 'DN' },
      ],
    });
    assert.equal(good.filter(e => e.includes('MAIN line')).length, 0);
  });

  it('blank C1+C2 is allowed (auto-centre), a single blank is rejected', () => {
    const bothBlank = validateForm({ ...base(), loops: [{ name: 'LOOP_1', c1: '', c2: '' }] });
    assert.deepEqual(bothBlank, []);
    const c2Only = validateForm({ ...base(), loops: [{ name: 'LOOP_1', c1: '', c2: '500' }] });
    assert.match(c2Only.join('\n'), /auto-centre/);
  });

  it('loopsNeedingCentre lists only fully-blank pairs', () => {
    const form = { loops: [{ c1: '', c2: '' }, { c1: '10', c2: '' }, { c1: '10', c2: '20' }] };
    assert.deepEqual(loopsNeedingCentre(form), [0]);
  });

  it('blank FOB chainage is allowed (MAIN centre), negative is rejected', () => {
    const blank = validateForm({
      ...base(),
      fobs: [{ refTrack: 'MAIN_LINE', chainage: '', platforms: ['PLATFORM_1', 'PLATFORM_2'], width: '' }],
    });
    assert.deepEqual(blank, []);
    const bad = validateForm({
      ...base(),
      fobs: [{ refTrack: 'MAIN_LINE', chainage: '-5', platforms: ['PLATFORM_1', 'PLATFORM_2'], width: '' }],
    });
    assert.match(bad.join('\n'), /reference chainage/);
  });

  it('blank FOB chainage previews as null instead of a misleading 0', () => {
    const cfg = buildConfig({
      ...base(),
      fobs: [{ refTrack: 'MAIN_LINE', chainage: '', platforms: ['PLATFORM_1', 'PLATFORM_2'], width: '' }],
    });
    assert.equal(cfg.fobs[0].reference_chainage, null);
  });

  it('fobsNeedingCentre + fillFobCentres use the MAIN centre', () => {
    const form = { fobs: [{ chainage: '' }, { chainage: '650' }] };
    assert.deepEqual(fobsNeedingCentre(form), [0]);
    const out = fillFobCentres(form, { main_center_m: 812.5 });
    assert.equal(out.fobs[0].chainage, '812.5');
    assert.equal(out.fobs[1].chainage, '650');
    const full = { fobs: [{ chainage: '650' }] };
    assert.equal(fillFobCentres(full, { main_center_m: 812.5 }), full);
  });
});

describe('fillCentredChainages', () => {
  const centre = { default_c1_m: 175.7094, default_c2_m: 925.7094 };

  it('fills only fully-blank pairs, formatted to 3 dp', () => {
    const form = { loops: [{ c1: '', c2: '' }, { c1: '10', c2: '' }, { c1: '10', c2: '20' }] };
    const out = fillCentredChainages(form, centre);
    assert.equal(out.loops[0].c1, '175.709');
    assert.equal(out.loops[0].c2, '925.709');
    assert.equal(out.loops[1].c1, '10');
    assert.equal(out.loops[1].c2, '');
    assert.equal(out.loops[2].c1, '10');
  });

  it('returns the form untouched when nothing is blank', () => {
    const form = { loops: [{ c1: '1', c2: '2' }] };
    assert.equal(fillCentredChainages(form, centre), form);
  });
});

describe('estimateFobSpan', () => {
  const spanForm = (widths) => ({
    loops: [
      { name: 'LOOP_1', side: 'LEFT', spacing: '5.3' },
      { name: 'LOOP_2', side: 'RIGHT', spacing: '5.3' },
    ],
    additionalLines: [],
    platforms: [
      { track: 'LOOP_1', type: 'SIDE', side: 'LEFT', clearance: '1.68', width: String(widths[0]) },
      { track: 'LOOP_2', type: 'SIDE', side: 'RIGHT', clearance: '1.68', width: String(widths[1]) },
    ],
    fobs: [{ refTrack: 'MAIN_LINE', platforms: ['PLATFORM_1', 'PLATFORM_2'] }],
  });

  it('matches the backend geometry on the standard layout (8.5 m -> 30.96 m)', () => {
    assert.equal(estimateFobSpan(spanForm([8.5, 8.5]), 0).toFixed(2), '30.96');
  });

  it('narrowed platforms fit the maximum (7.0 m -> 27.96 m)', () => {
    assert.equal(estimateFobSpan(spanForm([7.0, 7.0]), 0).toFixed(2), '27.96');
  });

  it('returns null when it cannot estimate', () => {
    assert.equal(estimateFobSpan({ loops: [], platforms: [], fobs: [] }, 0), null);
    const one = spanForm([8.5, 8.5]);
    one.fobs[0].platforms = ['PLATFORM_1'];
    assert.equal(estimateFobSpan(one, 0), null);
    const island = spanForm([8.5, 8.5]);
    island.platforms[0].type = 'ISLAND';
    assert.equal(estimateFobSpan(island, 0), null);
    const unknown = spanForm([8.5, 8.5]);
    unknown.platforms[0].track = 'NOPE';
    assert.equal(estimateFobSpan(unknown, 0), null);
  });
});

describe('sidings', () => {
  it('builds siding with engineering defaults (1:8.5, 120m CSL, 5.3m spacing)', () => {
    const cfg = buildConfig({
      ...base(),
      sidings: [
        { sourceTrack: 'LOOP_1', chainage: '300', side: 'LEFT', direction: 'FORWARD', turnout: '', csl: '', spacing: '' },
      ],
    });
    assert.equal(cfg.sidings.length, 1);
    const s = cfg.sidings[0];
    assert.equal(s.id, 'S1');
    assert.equal(s.source_track, 'LOOP_1');
    assert.equal(s.start_chainage_m, 300);
    assert.equal(s.side, 'LEFT');
    assert.equal(s.direction, 'FORWARD');
    assert.equal(s.turnout, '1:8.5');
    assert.equal(s.standing_length_m, 120);
    assert.equal(s.spacing, 5.3);
  });

  it('validates siding required fields and bounds', () => {
    const errs = validateForm({
      ...base(),
      sidings: [
        { sourceTrack: '', chainage: '-10', csl: '0', spacing: '4.0' },
      ],
    });
    assert.ok(errs.some((e) => e.includes('source track is required')));
    assert.ok(errs.some((e) => e.includes('start chainage must be a number >= 0')));
    assert.ok(errs.some((e) => e.includes('CSL (standing length) must be a number > 0')));
    assert.ok(errs.some((e) => e.includes('spacing must be >= 5.3 m')));
  });

  describe('getTrackRange', () => {
    it('returns exact range for loop with c1 and c2 (e.g. 450 - 1000)', () => {
      const f = {
        ...base(),
        loops: [
          { name: 'LOOP_1', c1: '450', c2: '1000' },
          { name: 'LOOP_2', c1: '1200', c2: '500' },
        ],
      };
      const r1 = getTrackRange('LOOP_1', f);
      assert.deepEqual(r1, { track: 'LOOP_1', c1: 450, c2: 1000, label: '450 – 1000' });

      // Handles reverse order c1/c2
      const r2 = getTrackRange('LOOP_2', f);
      assert.deepEqual(r2, { track: 'LOOP_2', c1: 500, c2: 1200, label: '500 – 1200' });
    });

    it('derives c2 from default crossover distance if c2 is blank', () => {
      const f = {
        ...base(),
        loops: [
          { name: '', c1: '450', c2: '' }, // default name is LOOP_1
        ],
      };
      const r = getTrackRange('LOOP_1', f);
      assert.deepEqual(r, { track: 'LOOP_1', c1: 450, c2: 1200, label: '450 – 1200' });
    });

    it('returns alignment range for MAIN_LINE and additional lines', () => {
      const f = {
        ...base(),
        mainLength: 2150.4,
        additionalLines: [
          { name: 'MAIN_LINE_2' },
        ],
      };
      const rMain = getTrackRange('MAIN_LINE', f);
      assert.deepEqual(rMain, { track: 'MAIN_LINE', c1: 0, c2: 2150, label: '0 – 2150' });

      const rAdd = getTrackRange('MAIN_LINE_2', f);
      assert.deepEqual(rAdd, { track: 'MAIN_LINE_2', c1: 0, c2: 2150, label: '0 – 2150' });
    });

    it('returns fallback label when mainLength is not yet loaded', () => {
      const r = getTrackRange('MAIN_LINE', base());
      assert.deepEqual(r, { track: 'MAIN_LINE', c1: 0, c2: null, label: '0 – Alignment end' });
    });

    it('returns null for unknown tracks or null trackName', () => {
      assert.equal(getTrackRange(null, base()), null);
      assert.equal(getTrackRange('', base()), null);
      assert.equal(getTrackRange('NONEXISTENT_TRACK', base()), null);
    });
  });

  describe('getExtendedLoopEnds', () => {
    it('dynamically extends inner loops by ladder step without overrun', () => {
      const f = {
        ...base(),
        loops: [
          { name: 'LOOP_1', side: 'LEFT', spacing: '5.3', c1: '500', c2: '1250' },
          { name: 'LOOP_2', side: 'LEFT', spacing: '10.6', c1: '500', c2: '1250' },
        ],
      };
      const ext = getExtendedLoopEnds(f);
      // LOOP_2 is outermost on LEFT: remains at base 500 to 1250
      assert.equal(ext.LOOP_2.c1, 500);
      assert.equal(ext.LOOP_2.c2, 1250);
      assert.equal(ext.LOOP_2.isExtended, false);

      // LOOP_1 is inner: extended by 1 ladder step (110.578 m) on both ends (no overrun stub)
      assert.equal(ext.LOOP_1.c1, 389.422);
      assert.equal(ext.LOOP_1.c2, 1360.578);
      assert.equal(ext.LOOP_1.isExtended, true);
      assert.equal(ext.LOOP_1.extendedLength, 971.156);
    });

    it('further extends running line if a crossover is placed outside base range', () => {
      const f = {
        ...base(),
        loops: [
          { name: 'LOOP_1', side: 'LEFT', spacing: '5.3', c1: '500', c2: '1250' },
        ],
        crossovers: [
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '350.0' },
        ],
      };
      const ext = getExtendedLoopEnds(f);
      assert.equal(ext.LOOP_1.c1, 350.0);
      assert.equal(ext.LOOP_1.c2, 1250);
      assert.equal(ext.LOOP_1.isExtended, true);
    });

    it('resolves colliding crossovers by pushing the second by 64m and adjusting loop extent', () => {
      const f = {
        ...base(),
        loops: [
          { name: 'LOOP_1', side: 'LEFT', spacing: '5.3', c1: '500', c2: '1250' },
        ],
        crossovers: [
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '350.0', direction: 'REVERSE' },
          // Second crossover collides at 350.0, pushed by -64m in REVERSE to 286.0
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '350.0', direction: 'REVERSE' },
        ],
      };
      const ext = getExtendedLoopEnds(f);
      assert.equal(ext.LOOP_1.c1, 286.0);
      assert.equal(ext.LOOP_1.c2, 1250);
      assert.equal(ext.LOOP_1.isExtended, true);
    });

    it('does not extend loop start to 0 when crossover chainage is blank, AUTO, or non-positive', () => {
      const f = {
        ...base(),
        loops: [
          { name: 'LOOP_1', side: 'LEFT', spacing: '5.3', c1: '456.712', c2: '1206.712' },
        ],
        crossovers: [
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '' },
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: 'AUTO' },
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '0' },
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '-10' },
        ],
      };
      const ext = getExtendedLoopEnds(f);
      assert.equal(ext.LOOP_1.c1, 456.712);
      assert.equal(ext.LOOP_1.c2, 1206.712);
      assert.equal(ext.LOOP_1.isExtended, false);
    });

    it('ignores the crossover being edited when excludeCrossoverIndex is provided', () => {
      const f = {
        ...base(),
        loops: [
          { name: 'LOOP_1', side: 'LEFT', spacing: '5.3', c1: '500', c2: '1250' },
        ],
        crossovers: [
          { from: 'LOOP_1', to: 'MAIN_LINE', chainage: '350.0' },
        ],
      };
      // When editing C1 (index 0), its own chainage 350.0 is excluded from its helper buttons
      const extEditing = getExtendedLoopEnds(f, 0);
      assert.equal(extEditing.LOOP_1.c1, 500);
      assert.equal(extEditing.LOOP_1.isExtended, false);
    });
  });
});

describe('gradients', () => {
  it('serializes absolute input and validates the alignment range across yards', () => {
    const form = { ...base(), startKm: '12', startM: '250', mainLength: 1500,
      gradients: ['12850', '13+750'].map((absoluteChainage, stationIndex) => ({
        absoluteChainage, stationIndex, rightValue: '260', direction: 'DN', rightDirection: 'RISE',
      })) };
    const gradients = buildConfig(form).gradients;
    assert.deepEqual(gradients.map(g => [g.station_index, g.absolute_chainage, g.direction, g.right_direction]),
      [[0, '12850', 'DN', 'RISE'], [1, '13+750', 'DN', 'RISE']]);
    for (const value of ['12+250', '13+750', '12850', '12+249', '13+751', '', 'bad']) {
      form.gradients[0].absoluteChainage = value;
      const invalid = validateForm(form).some(message => message.startsWith('Gradient'));
      assert.equal(invalid, !['12+250', '13+750', '12850'].includes(value), value);
    }
  });
  it('serializes gradients with defaults and custom values', () => {
    const form = {
      gradients: [
        {
          track: 'UP LINE',
          chainage: '125.400',
          leftValue: '525',
          leftDirection: 'STRAIGHT',
          rightValue: '260',
          rightDirection: 'RISE',
          rl: '102.45',
        },
      ],
    };
    const cfg = buildConfig(form);
    assert.equal(cfg.gradients.length, 1);
    assert.deepEqual(cfg.gradients[0], {
      track: 'UP LINE',
      chainage: '125.400',
      left_gradient_value: '525',
      left_direction: 'STRAIGHT',
      right_gradient_value: '260',
      right_direction: 'RISE',
      gradient_value: '260',
      direction: 'RISE',
      rl: '102.45',
    });
  });

  it('serializes stationIndex on gradients when attached to a station', () => {
    const form = {
      ...base(),
      stationMarkers: [{ name: 'KALESH', km: '', m: '800' }, { name: 'DELHI', km: '125', m: '400' }],
      gradients: [
        {
          chainage: '125.400',
          leftValue: '525',
          rightValue: '260',
          stationIndex: 1,
        },
        {
          chainage: '',
          leftValue: '20',
          rightValue: '40',
          stationIndex: 0,
        },
      ],
      stations: [
        {
          platform: 'PLATFORM_1',
          chainage: '',
          stationIndex: 0,
        },
      ],
    };
    const cfg = buildConfig(form);
    assert.equal(cfg.gradients[0].station_index, 1);
    assert.equal(cfg.gradients[0].chainage, '125.400');
    // Blank gradient chainage auto-filled from station 0 (0+800)
    assert.equal(cfg.gradients[1].station_index, 0);
    assert.equal(cfg.gradients[1].chainage, '0+800');
    // Blank station building chainage auto-filled from station 0 (0+800)
    assert.equal(cfg.stations[0].station_chainage, '0+800');
  });

  it('validates gradient required fields', () => {
    const form = {
      kmlFile: { name: 'test.kml' },
      gradients: [
        {
          track: 'MAIN_LINE',
          chainage: '',
          leftValue: '',
          rightValue: '',
        },
      ],
    };
    const errors = validateForm(form);
    assert(errors.some((e) => e.includes('chainage is required')));
    assert(errors.some((e) => e.includes('at least one gradient value')));
  });

  it('supports KM and M options for gradient chainages', () => {
    // Test parseKmM helper
    assert.deepEqual(parseKmM('70'), { km: '70', m: '' });
    assert.deepEqual(parseKmM('125+400'), { km: '125', m: '400' });
    assert.deepEqual(parseKmM('125.400'), { km: '125', m: '400' });
    assert.deepEqual(parseKmM('125.050'), { km: '125', m: '50' });
    assert.deepEqual(parseKmM('831 M'), { km: '', m: '831' });
    assert.deepEqual(parseKmM('831m'), { km: '', m: '831' });

    // Test buildConfig with km and m
    const form = {
      ...base(),
      gradients: [
        {
          km: '70',
          m: '400',
          leftValue: '525',
          rightValue: '260',
        },
      ],
    };
    const cfg = buildConfig(form);
    assert.equal(cfg.gradients[0].chainage, '70+400');
    assert.equal(cfg.gradients[0].km, 70);
    assert.equal(cfg.gradients[0].m, 400);
  });
});

describe('calculateEndChainage', () => {
  it('calculates end chainage from numeric start chainage', () => {
    assert.equal(calculateEndChainage('0.000', 1250.45), '1250.450');
    assert.equal(calculateEndChainage('100.00', 1250.45), '1350.45');
    assert.equal(calculateEndChainage('50', 500), '550.000');
  });

  it('calculates end chainage from plus notation (e.g. 125+400)', () => {
    assert.equal(calculateEndChainage('125+400', 650.0), '126+050.00');
    assert.equal(calculateEndChainage('0+000', 1000.0), '1+000.00');
  });

  it('calculates end chainage with units (KM, M)', () => {
    assert.equal(calculateEndChainage('12.5 KM', 1500), '14.000 KM');
    assert.equal(calculateEndChainage('200 M', 800), '1000.00 M');
  });

  it('returns null when length or start chainage is missing/invalid', () => {
    assert.equal(calculateEndChainage('0.000', null), null);
    assert.equal(calculateEndChainage('', 1000), null);
    assert.equal(calculateEndChainage(null, 1000), null);
    assert.equal(calculateEndChainage('invalid_str', 1000), null);
  });
});

describe('formatStartChainage & calculateEndChainageFromKmM', () => {
  it('formats start chainage with only KM (e.g. 4 -> "4")', () => {
    assert.equal(formatStartChainage(4, ''), '4');
    assert.equal(formatStartChainage('4', null), '4');
  });

  it('formats start chainage with KM and M (e.g. 1 KM and 900 M -> "1+900")', () => {
    assert.equal(formatStartChainage(1, 900), '1+900');
    assert.equal(formatStartChainage('2', '300'), '2+300');
    assert.equal(formatStartChainage(4, 0), '4+000');
  });

  it('defaults to 0.000 when both are blank', () => {
    assert.equal(formatStartChainage('', ''), '0.000');
  });

  it('calculates end chainage from KM and M with track length', () => {
    // 4 KM, no M, 1000m track length -> 5
    assert.equal(calculateEndChainageFromKmM(4, '', 1000), '5');
    // 4 KM, no M, 1250.45m track length -> 5+250.45
    assert.equal(calculateEndChainageFromKmM(4, '', 1250.45), '5+250.45');
    // 1 KM, 900 M, 500m track length -> 2+400.00
    assert.equal(calculateEndChainageFromKmM(1, 900, 500), '2+400.00');

    // Negative start chainages moving towards positive
    assert.equal(calculateEndChainageFromKmM(-4, '', 1663.42), '-2+336.58');
    assert.equal(calculateEndChainageFromKmM(-4, '', 100), '-3+900.00');
    assert.equal(calculateEndChainageFromKmM(-4, '', 4000), '0');
    assert.equal(calculateEndChainageFromKmM(-4, '', 4100), '0+100.00');
  });
});

describe('station markers', () => {
  it('serializes station markers with KM and M', () => {
    const form = {
      stationMarkers: [
        { name: 'DELHI JN', km: '2', m: '400' },
        { name: 'NEW DELHI', km: '3', m: '' },
      ],
    };
    const cfg = buildConfig(form);
    assert.equal(cfg.station_markers.length, 2);
    assert.deepEqual(cfg.station_markers[0], {
      name: 'DELHI JN',
      km: 2,
      m: 400,
      chainage: '2+400',
      show_flag: true,
    });
    assert.deepEqual(cfg.station_markers[1], {
      name: 'NEW DELHI',
      km: 3,
      m: null,
      chainage: '3',
      show_flag: true,
    });
  });

  it('hides alignment chainages and markers when loops or lines are added', () => {
    const formWithoutLoops = { loops: [] };
    assert.equal(buildConfig(formWithoutLoops).show_alignment_chainages, true);

    const formWithLoops = { loops: [{ name: 'LOOP_1' }] };
    assert.equal(buildConfig(formWithLoops).show_alignment_chainages, false);

    const formWithMainLines = { mainLines: [{ side: 'LEFT' }] };
    assert.equal(buildConfig(formWithMainLines).show_alignment_chainages, false);
  });

  it('calculates station distance along track alignment correctly', () => {
    // Start at KM 2 (2000m), Station at KM 4 M 500 (4500m) -> 2500m along track
    const stn1 = { km: '4', m: '500' };
    assert.equal(getStationTrackDistance(stn1, '2', ''), 2500);

    // Start at 0, Station at KM 6 (6000m) -> 6000m along track
    const stn2 = { km: '6', m: '' };
    assert.equal(getStationTrackDistance(stn2, '', ''), 6000);

    // Plus notation station: 10+200, start at 10+000 -> 200m along track
    const stn3 = { chainage: '10+200' };
    assert.equal(getStationTrackDistance(stn3, '10', '0'), 200);

    // Negative start chainage: Start at KM -4 (-4000m), Station at KM -3 M 900 (-3900m) -> 100m along track
    const stn4 = { km: '-3', m: '900' };
    assert.equal(getStationTrackDistance(stn4, '-4', ''), 100);

    // Optional KM: blank KM and 800 M -> 800m along track
    const stn5 = { km: '', m: '800' };
    assert.equal(getStationTrackDistance(stn5, '', ''), 800);
  });

  it('serializes stationIndex on platforms and centers platform bounds on station point', () => {
    const cfg = buildConfig({
      ...base(),
      stationMarkers: [{ name: 'DELHI', km: '3', m: '000' }],
      platforms: [{ track: 'MAIN_LINE', stationIndex: 0, length: '500' }],
    });
    assert.equal(cfg.platforms[0].station_index, 0);

    const f = {
      ...base(),
      startKm: '0',
      startM: '0',
      stationMarkers: [{ name: 'DELHI', km: '3', m: '000' }],
      platforms: [{ track: 'MAIN_LINE', stationIndex: 0, length: 500, centerOnTrack: true }],
    };
    // Station is at 3000m. Platform length is 500m -> start at 2750m, end at 3250m.
    const bounds = getPlatformBounds(f, 'PLATFORM_1');
    assert.ok(bounds);
    assert.equal(bounds.start, 2750);
    assert.equal(bounds.end, 3250);
    assert.equal(bounds.length, 500);
  });

  it('serializes stationIndex on loops and centers blank C1/C2 on station distance', () => {
    const form = {
      ...base(),
      startKm: '0',
      startM: '0',
      stationMarkers: [{ name: 'KALESH', km: '3', m: '000' }],
      loops: [{ name: 'LOOP_1', stationIndex: 0, c1: '', c2: '', overrun: '0' }],
    };
    const filled = fillCentredChainages(form, { default_c1_m: 500, default_c2_m: 1250 });
    // Station is at 3000m -> C1 is 3000 - 375 = 2625, C2 is 3000 + 375 = 3375
    assert.equal(filled.loops[0].c1, '2625');
    assert.equal(filled.loops[0].c2, '3375');

    const cfg = buildConfig(filled);
    assert.equal(cfg.loops[0].station_index, 0);
    assert.equal(cfg.loops[0].first_crossover_chainage, 2625);
    assert.equal(cfg.loops[0].second_crossover_chainage, 3375);
    assert.equal(cfg.loops[0].extend_start_m, 0);
    assert.equal(cfg.loops[0].extend_end_m, 0);
  });
});





