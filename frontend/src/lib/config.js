/**
 * Pure helpers: form state -> inputconfig-schema JSON.
 * Re-exports validation and defaults.
 */

import { fmt, isBlank, numOr, strOr } from './formUtils.js';
import { validateForm as runValidation } from './configValidator.js';

export const DEFAULTS = {
  outputDxf: 'ESP_frontend.dxf',
  trackSourceLayer: 'MAIN_TRACK',
  loopSpacing: 5.3,
  loopSide: 'LEFT',
  turnout: '1:12',
  turnoutVariant: 'standard',
  crossoverDistance: 750.0,
  extension: 0.0,
  loopOverrun: 120.0,
  armLength: 16.999,
  stairLength: 16.999,
  platformType: 'SIDE',
  platformSide: 'LEFT',
  clearance: 1.68,
  platformWidth: 7.0,
  platformLength: 550.0,
  platformHeight: 0.84,
  platformName: 'HIGH LEVEL PASSENGER PLATFORM',
  crossoverDirection: 'FORWARD',
  stationLength: 40.0,
  stationWidth: 10.0,
  stationSide: 'RIGHT',
  stationName: 'STATION BUILDING',
  fobWidth: 3.0,
  fobOffset: 40.0,
  fobDirection: 'INCREASING',
  armSide: 'LEFT',
  sidingStandingLength: 120.0,
  sidingSpacing: 5.3,
  sidingDirection: 'FORWARD',
  sidingSide: 'LEFT',
  sidingTurnout: '1:8.5',
  robWidth: 10.0,
  robOffset: 50.0,
  robReferenceEnd: 'START',
};

export const MIN_TRACK_SPACING_M = 5.3;
export const DEFAULT_PLATFORM_ARM_LENGTH_M = 16.999;
export const MIN_FOB_OFFSET_M = 40.0;
export const MAX_FOB_OFFSET_M = 60.0;
export const FOB_MAX_SPAN_M = 30.0;

/** Track names available for dropdowns: MAIN + loop/additional-line names. */
export function trackOptions(form) {
  const names = ['MAIN_LINE'];
  (form.mainLines || []).forEach((_, i) => {
    const n = `MAIN_LINE_${i + 1}`;
    if (!names.includes(n)) names.push(n);
  });
  (form.loops || []).forEach((loop, i) => {
    const n = strOr(loop.name, `LOOP_${i + 1}`);
    if (!names.includes(n)) names.push(n);
  });
  (form.additionalLines || []).forEach((line, i) => {
    const n = strOr(line.name, `PROPOSED_LINE_${i + 1}`);
    if (!names.includes(n)) names.push(n);
  });
  return names;
}

/** Tracks available to one loop: only lines completed before that loop. */
export function loopReferenceOptions(form, loopIndex) {
  return [
    'MAIN_LINE',
    ...((form.mainLines || []).map((_, i) => `MAIN_LINE_${i + 1}`)),
    ...((form.loops || []).slice(0, loopIndex).map((l, i) => strOr(l.name, `LOOP_${i + 1}`))),
  ];
}

/** Platform output layers, in order: PLATFORM_1, PLATFORM_2, ... */
export function platformLayers(form) {
  return (form.platforms || []).map((_, i) => `PLATFORM_${i + 1}`);
}

/** Get start and end chainage bounds for a referenced platform in form state. */
export function getPlatformBounds(form, platformLayer) {
  const platforms = form?.platforms || [];
  let pIdx = -1;
  if (typeof platformLayer === 'number') {
    pIdx = platformLayer;
  } else if (platformLayer) {
    const m = String(platformLayer).match(/PLATFORM_(\d+)/i);
    if (m) {
      pIdx = parseInt(m[1], 10) - 1;
    } else {
      pIdx = platforms.findIndex((_, idx) => `PLATFORM_${idx + 1}` === platformLayer);
    }
  }
  if (pIdx < 0 || pIdx >= platforms.length) {
    return null;
  }
  const p = platforms[pIdx];
  const pLen = numOr(p.length, DEFAULTS.platformLength);
  const trackName = p.track || 'MAIN_LINE';
  const range = getTrackRange(trackName, form);
  const trackLen = range && Number.isFinite(range.c2) ? range.c2 - range.c1 : (form?.mainLength ? Number(form.mainLength) : 1500.0);

  let startCh = 0.0;
  if (p.centerOnTrack !== false) {
    startCh = Math.max(0.0, (trackLen - pLen) / 2.0);
    if (range && Number.isFinite(range.c1)) {
      startCh += range.c1;
    }
  } else {
    startCh = numOr(p.startChainage, 0.0);
  }
  const endCh = startCh + pLen;
  return {
    platform: `PLATFORM_${pIdx + 1}`,
    track: trackName,
    start: startCh,
    end: endCh,
    length: pLen,
  };
}

/** Indices of loops with BOTH chainages blank (auto-centre on MAIN at submit). */
export function loopsNeedingCentre(form) {
  return (form.loops || [])
    .map((l, i) => (isBlank(l.c1) && isBlank(l.c2) ? i : -1))
    .filter((i) => i >= 0);
}

/** Indices of FOBs with a blank reference chainage (auto-centre on MAIN). */
export function fobsNeedingCentre(form) {
  return ((form || {}).fobs || [])
    .map((fb, i) => (isBlank(fb.chainage) || String(fb.chainage).trim().toUpperCase() === 'MAIN_CENTER' ? i : -1))
    .filter((i) => i >= 0);
}

/** Fill every blank FOB chainage from a /main-center response. */
export function fillFobCentres(form, centre) {
  const idx = fobsNeedingCentre(form || {});
  if (idx.length === 0) return form;
  const ch = fmt(centre.main_center_m);
  return {
    ...form,
    fobs: (form.fobs || []).map((fb, i) =>
      idx.includes(i) ? { ...fb, chainage: ch } : fb,
    ),
  };
}

/** Fill every fully-blank C1/C2 pair from a /main-center response. */
export function fillCentredChainages(form, centre) {
  const idx = loopsNeedingCentre(form || {});
  if (idx.length === 0) return form;
  const c1 = fmt(centre.default_c1_m);
  const c2 = fmt(centre.default_c2_m);
  return {
    ...form,
    loops: (form.loops || []).map((l, i) =>
      idx.includes(i) ? { ...l, c1, c2 } : l,
    ),
  };
}

/** Find the valid chainage range [c1, c2] for a chosen track in form state. */
export function getTrackRange(trackName, form) {
  if (!trackName) return null;
  const tn = String(trackName).trim();
  const f = form || {};

  const loops = f.loops || [];
  for (let i = 0; i < loops.length; i++) {
    const l = loops[i];
    const name = String(l.name || '').trim() || `LOOP_${i + 1}`;
    if (name.toUpperCase() === tn.toUpperCase()) {
      const c1Raw = l.c1 !== undefined && l.c1 !== null ? String(l.c1).trim() : '';
      const c2Raw = l.c2 !== undefined && l.c2 !== null ? String(l.c2).trim() : '';
      const c1 = c1Raw !== '' ? Number(c1Raw) : NaN;
      let c2 = c2Raw !== '' ? Number(c2Raw) : NaN;

      const dist = numOr(l.crossoverDistance, DEFAULTS.crossoverDistance);
      if (Number.isFinite(c1) && !Number.isFinite(c2) && Number.isFinite(dist)) {
        c2 = c1 + dist;
      }

      if (Number.isFinite(c1) && Number.isFinite(c2)) {
        const start = Math.min(c1, c2);
        const end = Math.max(c1, c2);
        return { track: name, c1: start, c2: end, label: `${start} – ${end}` };
      }
    }
  }

  const mainLines = f.mainLines || [];
  for (let i = 0; i < mainLines.length; i++) {
    const name = `MAIN_LINE_${i + 1}`;
    if (name.toUpperCase() === tn.toUpperCase()) {
      const len = f.mainLength ? Math.round(Number(f.mainLength)) : null;
      return { track: name, c1: 0, c2: len, label: len ? `0 – ${len}` : '0 – Alignment end' };
    }
  }

  const lines = f.additionalLines || [];
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    const name = String(l.name || '').trim() || `PROPOSED_LINE_${i + 1}`;
    if (name.toUpperCase() === tn.toUpperCase()) {
      const len = f.mainLength ? Math.round(Number(f.mainLength)) : null;
      return { track: name, c1: 0, c2: len, label: len ? `0 – ${len}` : '0 – Alignment end' };
    }
  }

  if (tn.toUpperCase().includes('MAIN')) {
    const len = f.mainLength ? Math.round(Number(f.mainLength)) : null;
    return { track: tn, c1: 0, c2: len, label: len ? `0 – ${len}` : '0 – Alignment end' };
  }

  return null;
}

/** Estimated FOB deck span (m) from form state alone. */
export function estimateFobSpan(form, fobIndex) {
  const f = form || {};
  const fb = (f.fobs || [])[fobIndex];
  if (!fb || (fb.platforms || []).length < 2) return null;
  const pos = { MAIN_LINE: 0 };
  const place = (name, spacing, side, refTrack = 'MAIN_LINE') => {
    if (!name || pos[name] !== undefined) return;
    const s = Number(spacing);
    if (!Number.isFinite(s)) return;
    const refPos = pos[refTrack] !== undefined ? pos[refTrack] : 0;
    pos[name] = refPos + (String(side).toUpperCase() === 'RIGHT' ? -s : s);
  };
  (f.mainLines || []).forEach((l, i) =>
    place(`MAIN_LINE_${i + 1}`, numOr(l.spacing, DEFAULTS.loopSpacing), strOr(l.side, 'LEFT'), strOr(l.referenceTrack || l.reference_track, 'MAIN_LINE')));
  (f.loops || []).forEach((l, i) =>
    place(strOr(l.name, `LOOP_${i + 1}`), numOr(l.spacing, DEFAULTS.loopSpacing), strOr(l.side, 'LEFT'), strOr(l.referenceTrack, 'MAIN_LINE')));
  (f.additionalLines || []).forEach((l, i) =>
    place(strOr(l.name, `PROPOSED_LINE_${i + 1}`), numOr(l.spacing, DEFAULTS.loopSpacing), strOr(l.side, 'LEFT')));
  const ref = pos[strOr(fb.refTrack, 'MAIN_LINE')];
  if (ref === undefined) return null;
  const byLayer = {};
  (f.platforms || []).forEach((p, i) => {
    byLayer[`PLATFORM_${i + 1}`] = p;
  });
  let lo = Infinity;
  let hi = -Infinity;
  for (const layer of fb.platforms) {
    const p = byLayer[layer];
    if (!p) return null;
    if (strOr(p.type, 'SIDE').toUpperCase() !== 'SIDE') return null;
    const t = pos[strOr(p.track, '')];
    if (t === undefined) return null;
    const clearance = numOr(p.clearance, DEFAULTS.clearance);
    const width = numOr(p.width, DEFAULTS.platformWidth);
    if (!Number.isFinite(clearance) || !Number.isFinite(width)) return null;
    const rel = t - ref;
    const edge =
      strOr(p.side, 'LEFT').toUpperCase() === 'LEFT'
        ? [rel + clearance, rel + clearance + width]
        : [rel - clearance - width, rel - clearance];
    lo = Math.min(lo, edge[0]);
    hi = Math.max(hi, edge[1]);
  }
  return hi - lo;
}

function buildLoop(loop, index) {
  const entry = {
    name: strOr(loop.name, `LOOP_${index + 1}`),
    spacing: numOr(loop.spacing, DEFAULTS.loopSpacing),
    side: strOr(loop.side, DEFAULTS.loopSide).toUpperCase(),
    reference_track: strOr(loop.referenceTrack, 'MAIN_LINE'),
    first_crossover_chainage: isBlank(loop.c1) ? null : Number(loop.c1),
  };
  if (!isBlank(loop.c2)) entry.second_crossover_chainage = Number(loop.c2);
  entry.turnout_designation = strOr(loop.turnout, DEFAULTS.turnout);
  entry.turnout_variant = strOr(loop.turnoutVariant, DEFAULTS.turnoutVariant);
  entry.crossover_distance_m = numOr(loop.crossoverDistance, DEFAULTS.crossoverDistance);
  entry.extend_start_m = numOr(loop.extStart, DEFAULTS.loopOverrun);
  entry.extend_end_m = numOr(loop.extEnd, DEFAULTS.loopOverrun);
  return entry;
}

function buildCrossover(x) {
  const raw = strOr(x.chainage, '');
  const chainage = raw.toUpperCase() === 'AUTO' ? 'AUTO' : Number(raw);
  return {
    from_track: strOr(x.from, ''),
    to_track: strOr(x.to, ''),
    from_chainage_m: chainage,
    turnout: strOr(x.turnout, DEFAULTS.turnout),
    direction: strOr(x.direction, DEFAULTS.crossoverDirection).toUpperCase(),
    ...(raw.toUpperCase() === 'AUTO' && !isBlank(x.autoAnchor) ? { auto_anchor_id: strOr(x.autoAnchor, '') } : {}),
  };
}

function buildPlatform(p) {
  const entry = {
    track_layer: strOr(p.track, ''),
    platform_type: strOr(p.type, DEFAULTS.platformType).toUpperCase(),
    ...(strOr(p.type, DEFAULTS.platformType).toUpperCase() === 'ISLAND' && !isBlank(p.track2)
      ? { second_track_layer: strOr(p.track2, '') }
      : {}),
    side: strOr(p.side, DEFAULTS.platformSide).toUpperCase(),
    center_on_track: p.centerOnTrack !== false,
    clearance: numOr(p.clearance, DEFAULTS.clearance),
    platform_width: numOr(p.width, DEFAULTS.platformWidth),
    platform_length: numOr(p.length, DEFAULTS.platformLength),
    platform_height: numOr(p.height, DEFAULTS.platformHeight),
    platform_name: strOr(p.name, DEFAULTS.platformName),
  };
  const armVal = p.armLength ?? p.stairLength;
  if (!(!isBlank(armVal) && Number(armVal) === 0)) {
    const len = numOr(armVal, DEFAULTS.armLength);
    entry.arm_length = len;
    entry.stair_length = len;
  }
  return entry;
}

function buildStation(s, index) {
  const entry = {
    platform_layer: strOr(s.platform, ''),
    building_length: numOr(s.length, DEFAULTS.stationLength),
    building_width: numOr(s.width, DEFAULTS.stationWidth),
    platform_side: strOr(s.side, DEFAULTS.stationSide).toUpperCase(),
    building_name: strOr(s.name, index === 0 ? DEFAULTS.stationName : `STATION ${index + 1}`),
  };
  const ch = !isBlank(s.chainage) ? s.chainage : s.station_chainage;
  if (!isBlank(ch)) {
    entry.station_chainage = String(ch).trim();
  }
  return entry;
}

function buildFob(f) {
  const rawCh = String(f.chainage ?? '').trim().toUpperCase();
  let refCh = null;
  if (!isBlank(f.chainage)) {
    refCh = rawCh === 'MAIN_CENTER' ? 'MAIN_CENTER' : Number(f.chainage);
  }
  const entry = {
    reference_track: strOr(f.refTrack, 'MAIN_LINE'),
    reference_chainage: refCh,
    platforms: [...(f.platforms || [])],
    width: numOr(f.width, DEFAULTS.fobWidth),
    extend_start_m: numOr(f.extStart, DEFAULTS.extension),
    extend_end_m: numOr(f.extEnd, DEFAULTS.extension),
  };
  if (!isBlank(f.offset) || isBlank(f.chainage) || rawCh === 'MAIN_CENTER' || !isBlank(f.direction)) {
    entry.offset = numOr(f.offset, DEFAULTS.fobOffset);
    entry.direction = strOr(f.direction, DEFAULTS.fobDirection).toUpperCase();
  }
  const arms = {};
  for (const arm of f.arms || []) {
    if (isBlank(arm.platform)) continue;
    arms[String(arm.platform).trim()] = {
      length: numOr(arm.length, DEFAULTS.armLength),
      side: strOr(arm.side, DEFAULTS.armSide).toUpperCase(),
    };
  }
  if (Object.keys(arms).length > 0) entry.arms = arms;
  return entry;
}

function buildSiding(s, index) {
  return {
    id: strOr(s.id, `S${index + 1}`),
    source_track: strOr(s.sourceTrack, 'MAIN_LINE'),
    start_chainage_m: numOr(s.chainage, 0.0),
    direction: strOr(s.direction, DEFAULTS.sidingDirection).toUpperCase(),
    side: strOr(s.side, DEFAULTS.sidingSide).toUpperCase(),
    turnout: strOr(s.turnout, DEFAULTS.sidingTurnout),
    standing_length_m: numOr(s.csl, DEFAULTS.sidingStandingLength),
    spacing: numOr(s.spacing, DEFAULTS.sidingSpacing),
  };
}

function buildRob(r, index) {
  const blockName = strOr(r.blockName, 'SGFD');
  const tracksList = Array.isArray(r.tracks)
    ? r.tracks.filter(Boolean)
    : typeof r.tracks === 'string' && r.tracks.trim()
      ? r.tracks.split(',').map((t) => t.trim()).filter(Boolean)
      : [];
  return {
    id: strOr(r.id, `ROB_${index + 1}`),
    platform: strOr(r.platform, 'PLATFORM_1'),
    reference_end: strOr(r.referenceEnd, DEFAULTS.robReferenceEnd).toUpperCase(),
    offset: numOr(r.offset, DEFAULTS.robOffset),
    width: numOr(r.width, DEFAULTS.robWidth),
    reference_track: strOr(r.referenceTrack, 'MAIN_LINE'),
    block_name: blockName,
    output_layer: strOr(r.outputLayer, blockName),
    tracks: tracksList,
    chainage: r.chainage ? String(r.chainage).trim() : null,
    add_dimension: true,
    add_chainage: false,
  };
}

function buildGradient(g) {
  const leftVal = g.leftValue ?? g.left_gradient_value ?? '';
  const rightVal = g.rightValue ?? g.right_gradient_value ?? g.gradientValue ?? '';
  const dir = g.direction
    ? String(g.direction).trim().toUpperCase()
    : strOr(g.rightDirection || g.right_direction, 'UP').toUpperCase();
  return {
    track: strOr(g.track, 'MAIN_LINE'),
    chainage: String(g.chainage ?? '').trim(),
    direction: dir,
    left_gradient_value: String(leftVal).trim(),
    left_direction: strOr(g.leftDirection || g.left_direction, 'STRAIGHT').toUpperCase(),
    right_gradient_value: String(rightVal).trim(),
    right_direction: strOr(g.rightDirection || g.right_direction, 'RISE').toUpperCase(),
    // Backward-compatible alias
    gradient_value: String(rightVal).trim(),
    rl: !isBlank(g.rl) ? String(g.rl).trim() : null,
  };
}

/** Build full inputconfig-schema JSON from form state. */
export function buildConfig(form) {
  const f = form || {};
  const mainLines = f.mainLines || [];
  return {
    source_path: (f.kmlFile && f.kmlFile.name) || 'upload.kml',
    output_dxf: strOr(f.outputDxf, DEFAULTS.outputDxf),
    track_source_layer: strOr(f.trackSourceLayer, DEFAULTS.trackSourceLayer),
    loops: (f.loops || []).map(buildLoop),
    additional_lines: [
      ...mainLines.map((l, i) => {
        const item = {
          name: `MAIN_LINE_${i + 1}`,
          spacing: numOr(l.spacing, DEFAULTS.loopSpacing),
          side: strOr(l.side, DEFAULTS.loopSide).toUpperCase(),
          direction: strOr(l.direction, 'DN').toUpperCase(),
        };
        const ref = l.referenceTrack || l.reference_track;
        if (ref) {
          item.reference_track = strOr(ref, 'MAIN_LINE');
        }
        return item;
      }),
      ...(f.additionalLines || []).map((l, i) => ({
        name: strOr(l.name, `PROPOSED_LINE_${i + 1}`),
        spacing: numOr(l.spacing, DEFAULTS.loopSpacing),
        side: strOr(l.side, DEFAULTS.loopSide).toUpperCase(),
      })),
    ],
    platforms: (f.platforms || []).map(buildPlatform),
    crossovers:
      f.crossoverMode === 'default'
        ? 'DEFAULT'
        : (f.crossovers || []).map(buildCrossover),
    stations: (f.stations || []).map(buildStation),
    fobs: (f.fobs || []).map(buildFob),
    robs: (f.robs || []).map(buildRob),
    sidings: (f.sidings || []).map(buildSiding),
    gradients: (f.gradients || []).map(buildGradient),
    main_directions: mainLines.length > 0
      ? {
          MAIN_LINE: strOr(f.mainLineDirection, 'UP').toUpperCase(),
          ...Object.fromEntries(mainLines.map((l, i) => [
            `MAIN_LINE_${i + 1}`,
            strOr(l.direction, 'DN').toUpperCase(),
          ])),
        }
      : {},
  };
}

/** Validate form state. */
export function validateForm(form) {
  return runValidation(form, DEFAULTS, platformLayers, MIN_TRACK_SPACING_M, MIN_FOB_OFFSET_M, MAX_FOB_OFFSET_M);
}
