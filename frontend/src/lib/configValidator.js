/**
 * Client-side form validation rules.
 */

import { isBlank, numOr, strOr } from './formUtils.js';

/**
 * Validate form state before submission or preview generation.
 * Returns an array of human-readable error messages ([] = valid).
 */
export function validateForm(form, defaults, platformLayersFn, minTrackSpacing, minFobOffset, maxFobOffset) {
  const errors = [];
  const f = form || {};
  const at = (section, i, msg) => errors.push(`${section} ${i + 1}: ${msg}`);

  if (!f.kmlFile) errors.push('KML file: upload the track alignment (.kml).');
  else if (!String(f.kmlFile.name || '').toLowerCase().endsWith('.kml'))
    errors.push('KML file: must be a .kml file.');

  const names = new Set();
  (f.mainLines || []).forEach((l, i) => {
    const spacing = numOr(l.spacing, defaults.loopSpacing);
    if (!Number.isFinite(spacing) || spacing < minTrackSpacing)
      at('MAIN line', i, `spacing must be a number >= ${minTrackSpacing} m.`);
    const direction = strOr(l.direction, 'DN').toUpperCase();
    if (!['UP', 'DN'].includes(direction)) at('MAIN line', i, 'direction must be UP or DN.');
    const ref = l.referenceTrack || l.reference_track;
    if (ref) {
      const allowed = ['MAIN_LINE', ...f.mainLines.slice(0, i).map((_, idx) => `MAIN_LINE_${idx + 1}`)];
      if (!allowed.includes(ref)) {
        at('MAIN line', i, `reference track must be one of: ${allowed.join(', ')}.`);
      }
    }
  });
  if ((f.mainLines || []).length > 0) {
    const direction = strOr(f.mainLineDirection, 'UP').toUpperCase();
    if (!['UP', 'DN'].includes(direction)) errors.push('MAIN_LINE direction must be UP or DN.');
  }
  (f.loops || []).forEach((l, i) => {
    const name = strOr(l.name, `LOOP_${i + 1}`);
    if (names.has(name)) at('Loop', i, `duplicate name "${name}".`);
    names.add(name);
    // Both blank = auto-centre the 750 m loop on MAIN at submit time.
    if (isBlank(l.c1) && isBlank(l.c2)) {
      // nothing required here
    } else if (isBlank(l.c1) || !Number.isFinite(Number(l.c1)) || Number(l.c1) < 0) {
      at('Loop', i, 'C1 chainage is required (MAIN m, >= 0) — or leave C1+C2 blank to auto-centre.');
    } else if (!isBlank(l.c2) && (!Number.isFinite(Number(l.c2)) || Number(l.c2) <= Number(l.c1))) {
      at('Loop', i, 'C2 chainage must be a number greater than C1 (or blank for C1 + distance).');
    }
    const spacing = numOr(l.spacing, defaults.loopSpacing);
    if (!Number.isFinite(spacing) || spacing < minTrackSpacing)
      at('Loop', i, `spacing must be a number >= ${minTrackSpacing} m (blank = ${minTrackSpacing}).`);
    const dist = numOr(l.crossoverDistance, defaults.crossoverDistance);
    if (!Number.isFinite(dist) || dist <= 0)
      at('Loop', i, 'crossover distance must be > 0 (blank = 750).');
    for (const key of ['extStart', 'extEnd']) {
      const v = numOr(l[key], 0);
      if (!Number.isFinite(v) || v < 0) at('Loop', i, 'extensions must be >= 0.');
    }
  });

  (f.additionalLines || []).forEach((l, i) => {
    if (isBlank(l.name)) at('Additional line', i, 'name is required.');
    const spacing = numOr(l.spacing, defaults.loopSpacing);
    if (!Number.isFinite(spacing) || spacing < minTrackSpacing)
      at('Additional line', i, `spacing must be >= ${minTrackSpacing} m.`);
  });

  (f.platforms || []).forEach((p, i) => {
    if (isBlank(p.track)) at('Platform', i, 'track is required.');
    if (strOr(p.type, 'SIDE').toUpperCase() === 'ISLAND' && isBlank(p.track2))
      at('Platform', i, 'second track is required for ISLAND type.');
    for (const [key, label, min] of [
      ['clearance', 'clearance', 0],
      ['width', 'width', 0],
      ['length', 'length', 0],
      ['height', 'height', 0],
    ]) {
      const v = numOr(p[key], 1);
      if (!Number.isFinite(v) || v < min || (min === 0 && key !== 'clearance' && v <= 0))
        at('Platform', i, `${label} must be a valid number${min === 0 && key !== 'clearance' ? ' > 0' : ' >= 0'}.`);
    }
    const armVal = p.armLength ?? p.stairLength;
    if (!isBlank(armVal) && (!Number.isFinite(Number(armVal)) || Number(armVal) < 0))
      at('Platform', i, 'arm length must be >= 0 (blank = 16.999 m, 0 = none).');
  });

  if (f.crossoverMode === 'default') {
    const byName = {};
    (f.loops || []).forEach((l, i) => {
      byName[strOr(l.name, `LOOP_${i + 1}`)] = strOr(l.side, 'LEFT').toUpperCase();
    });
    if (!byName.LOOP_1 || !byName.LOOP_2)
      errors.push('Crossovers: DEFAULT preset needs loops named LOOP_1 and LOOP_2.');
    else if (byName.LOOP_1 === byName.LOOP_2)
      errors.push('Crossovers: DEFAULT preset needs LOOP_1 and LOOP_2 on opposite sides.');
  } else {
    (f.crossovers || []).forEach((x, i) => {
      if (isBlank(x.from) || isBlank(x.to)) at('Crossover', i, 'from/to tracks are required.');
      else if (strOr(x.from, '') === strOr(x.to, '')) at('Crossover', i, 'from/to tracks must differ.');
      const raw = strOr(x.chainage, '');
      if (isBlank(raw)) at('Crossover', i, 'chainage is required (number or AUTO).');
      else if (raw.toUpperCase() !== 'AUTO' && (!Number.isFinite(Number(raw)) || Number(raw) < 0))
        at('Crossover', i, 'chainage must be >= 0 or AUTO.');
    });
  }

  const layers = platformLayersFn ? platformLayersFn(f) : [];
  (f.stations || []).forEach((s, i) => {
    if (isBlank(s.platform)) at('Station', i, 'platform is required.');
    else if (layers.length > 0 && !layers.includes(strOr(s.platform, '')))
      at('Station', i, `unknown platform "${strOr(s.platform, '')}".`);
    for (const [key, label] of [['length', 'length'], ['width', 'width']]) {
      const v = numOr(s[key], 1);
      if (!Number.isFinite(v) || v <= 0) at('Station', i, `${label} must be > 0.`);
    }
  });

  (f.fobs || []).forEach((fb, i) => {
    if (isBlank(fb.refTrack)) at('FOB', i, 'reference track is required.');
    const isMc = isBlank(fb.chainage) || String(fb.chainage).trim().toUpperCase() === 'MAIN_CENTER';
    if (!isMc && (!Number.isFinite(Number(fb.chainage)) || Number(fb.chainage) < 0))
      at('FOB', i, 'reference chainage must be >= 0 (MAIN m), MAIN_CENTER, or blank.');
    if (!isBlank(fb.offset)) {
      const off = Number(fb.offset);
      if (!Number.isFinite(off) || off < minFobOffset || off > maxFobOffset)
        at('FOB', i, `offset from station edge must be between ${minFobOffset} m and ${maxFobOffset} m.`);
    }
    if ((fb.platforms || []).length < 2)
      at('FOB', i, 'select at least two platforms to connect.');
    const width = numOr(fb.width, defaults.fobWidth);
    if (!Number.isFinite(width) || width <= 0)
      at('FOB', i, `width must be > 0 (blank = ${defaults.fobWidth}).`);
    for (const arm of fb.arms || []) {
      if (isBlank(arm.platform) && isBlank(arm.length)) continue;
      if (!(fb.platforms || []).includes(strOr(arm.platform, '')))
        at('FOB', i, `arm for "${strOr(arm.platform, '')}" must name a connected platform.`);
      if (!isBlank(arm.length) && (!Number.isFinite(Number(arm.length)) || Number(arm.length) <= 0))
        at('FOB', i, 'arm length must be > 0.');
    }
  });

  (f.sidings || []).forEach((s, i) => {
    if (isBlank(s.sourceTrack)) at('Siding', i, 'source track is required.');
    if (isBlank(s.chainage) || !Number.isFinite(Number(s.chainage)) || Number(s.chainage) < 0)
      at('Siding', i, 'start chainage must be a number >= 0.');
    const csl = numOr(s.csl, defaults.sidingStandingLength);
    if (!Number.isFinite(csl) || csl <= 0)
      at('Siding', i, 'CSL (standing length) must be a number > 0.');
    const spacing = numOr(s.spacing, defaults.sidingSpacing);
    if (!Number.isFinite(spacing) || spacing < minTrackSpacing)
      at('Siding', i, `spacing must be >= ${minTrackSpacing} m.`);
  });

  (f.robs || []).forEach((rob, i) => {
    if ((f.platforms || []).length === 0) {
      at('ROB', i, 'requires at least one platform to be defined.');
    }
    if (isBlank(rob.platform)) {
      at('ROB', i, 'platform selection is required.');
    }
    const end = strOr(rob.referenceEnd, 'START').toUpperCase();
    if (end !== 'START' && end !== 'END') {
      at('ROB', i, 'platform end must be either START or END.');
    }
    if (!isBlank(rob.offset)) {
      const off = Number(rob.offset);
      if (!Number.isFinite(off) || off < 0) {
        at('ROB', i, 'offset must be a number >= 0.');
      }
    }
    const width = numOr(rob.width, defaults.robWidth || 10.0);
    if (!Number.isFinite(width) || width <= 0) {
      at('ROB', i, `width must be a number > 0 (blank = ${defaults.robWidth || 10.0}).`);
    }
  });

  (f.gradients || []).forEach((g, i) => {
    if (isBlank(g.chainage)) at('Gradient', i, 'chainage is required.');
    const leftVal = g.leftValue ?? g.left_gradient_value ?? '';
    const rightVal = g.rightValue ?? g.right_gradient_value ?? g.gradientValue ?? '';
    if (isBlank(leftVal) && isBlank(rightVal)) {
      at('Gradient', i, 'at least one gradient value (left or right) is required.');
    }
  });

  return errors;
}


