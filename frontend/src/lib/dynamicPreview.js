import { bridgeTypeLabel, resolveBridgeDistance } from './bridgePlacement.js';
/**
 * Dynamic Client-Side DXF/SVG Plan-View Generator.
 *
 * Renders the railway schematic dynamically in real-time as the user edits the
 * form (loops, platforms, stations, FOBs, bridges, sidings, crossovers) without
 * calling the backend API on every keystroke.
 */

import { esc, polylinePathD, r3 } from './dxfPathUtils.js';
import { BG_DARK, getLayerStyle } from './dxfPreview.js';
import { formatStartChainage, getStationTrackDistance, parseKmM } from './config.js';
import { isBlank } from './formUtils.js';

/**
 * Sampling step along track alignment in metres.
 */
const SAMPLE_STEP_M = 15.0;

/**
 * Safe numeric parser with fallback for empty strings, 'auto', or invalid values.
 */
function parseNum(val, fallback = 0.0) {
  if (val === '' || val == null) return fallback;
  const str = String(val).trim().toLowerCase();
  if (str === 'auto' || str === 'nan' || str === 'undefined' || str === 'null') return fallback;
  const n = Number(val);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * Calculate Euclidean distance between two 2D points.
 */
function dist2d(p1, p2) {
  return Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
}

/**
 * Prepare an alignment helper from coordinate points.
 * Normalizes any survey alignment to horizontal local ESP coordinates (0, 0) -> (L, 0).
 */
function buildAlignmentHelper(points, fallbackLength = 1600.0) {
  let pts = Array.isArray(points) && points.length >= 2 ? points : null;
  if (!pts) {
    const L = Math.max(parseNum(fallbackLength, 1600.0), 500.0);
    pts = [
      [0.0, 0.0],
      [L, 0.0],
    ];
  } else {
    // Rotate and translate to local horizontal ESP coordinates (align with X axis)
    const p0 = pts[0];
    const pEnd = pts[pts.length - 1];
    const dx = pEnd[0] - p0[0];
    const dy = pEnd[1] - p0[1];
    const angle = Math.atan2(dy, dx);
    const cosA = Math.cos(-angle);
    const sinA = Math.sin(-angle);

    pts = pts.map((p) => {
      const rx = p[0] - p0[0];
      const ry = p[1] - p0[1];
      return [
        rx * cosA - ry * sinA,
        rx * sinA + ry * cosA,
      ];
    });
  }

  const cumDists = [0.0];
  for (let i = 1; i < pts.length; i++) {
    const d = dist2d(pts[i - 1], pts[i]);
    cumDists.push(cumDists[i - 1] + Math.max(d, 1e-6));
  }
  const totalLength = cumDists[cumDists.length - 1];

  function getAt(s) {
    const chainage = Math.max(0.0, Math.min(totalLength, parseNum(s, 0.0)));
    let low = 0;
    let high = cumDists.length - 1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (cumDists[mid] <= chainage) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    const idx = Math.max(0, Math.min(pts.length - 2, high));
    const s0 = cumDists[idx];
    const s1 = cumDists[idx + 1];
    const segLen = Math.max(s1 - s0, 1e-6);
    const t = Math.max(0.0, Math.min(1.0, (chainage - s0) / segLen));

    const pA = pts[idx];
    const pB = pts[idx + 1];
    const px = pA[0] + t * (pB[0] - pA[0]);
    const py = pA[1] + t * (pB[1] - pA[1]);

    const tx = (pB[0] - pA[0]) / segLen;
    const ty = (pB[1] - pA[1]) / segLen;
    const nx = -ty;
    const ny = tx;

    return { point: [px, py], tangent: [tx, ty], normal: [nx, ny], chainage };
  }

  function offsetAt(s, lateralOffset) {
    const at = getAt(s);
    return [
      at.point[0] + at.normal[0] * lateralOffset,
      at.point[1] + at.normal[1] * lateralOffset,
    ];
  }

  function samplePolyline(sStart, sEnd, lateralOffset, step = SAMPLE_STEP_M) {
    const start = Math.max(0.0, Math.min(totalLength, parseNum(sStart, 0.0)));
    const end = Math.max(0.0, Math.min(totalLength, parseNum(sEnd, totalLength)));
    if (start >= end) return [];

    const out = [];
    let cur = start;
    while (cur < end) {
      out.push(offsetAt(cur, lateralOffset));
      cur += step;
    }
    out.push(offsetAt(end, lateralOffset));
    return out;
  }

  return {
    totalLength,
    getAt,
    offsetAt,
    samplePolyline,
  };
}

/**
 * Generate complete dynamic preview SVG from form state.
 */
export function generateDynamicPreview(form, options = {}) {
  const f = form || {};
  const alignPts = f.alignmentPoints || options.alignmentPoints || null;
  const mainLen = parseNum(f.mainLength, 1600.0);
  const align = buildAlignmentHelper(alignPts, mainLen);
  const totalLength = align.totalLength;
  const stationMarkers = f.stationMarkers || [];
  const stationDistance = (marker) => {
    if (!marker || [marker.km, marker.m, marker.chainage].every(isBlank)) return null;
    const kmM = isBlank(marker.km) && isBlank(marker.m) ? parseKmM(marker.chainage) : marker;
    return getStationTrackDistance(kmM, f.startKm, f.startM);
  };
  let baseCenter = parseNum(f.mainCenter, totalLength / 2.0);
  const firstStationDistance = stationDistance(stationMarkers[0]);
  if (firstStationDistance != null && firstStationDistance <= totalLength) {
    baseCenter = firstStationDistance;
  }
  const mainCenter = baseCenter;

  // Track position solver: trackName -> lateralOffset from MAIN_LINE
  const trackOffsets = { MAIN_LINE: 0.0 };

  (f.mainLines || []).forEach((ml, idx) => {
    const name = `MAIN_LINE_${idx + 1}`;
    const ref = ml.referenceTrack || 'MAIN_LINE';
    const baseOff = trackOffsets[ref] ?? 0.0;
    const sp = parseNum(ml.spacing, 5.3);
    const sgn = String(ml.side || 'LEFT').toUpperCase() === 'RIGHT' ? -1 : 1;
    trackOffsets[name] = baseOff + sgn * sp;
  });

  (f.loops || []).forEach((lp, idx) => {
    const name = (lp.name || `LOOP_${idx + 1}`).trim();
    const ref = lp.referenceTrack || 'MAIN_LINE';
    const baseOff = trackOffsets[ref] ?? 0.0;
    const sp = parseNum(lp.spacing, 5.3);
    const sgn = String(lp.side || 'LEFT').toUpperCase() === 'RIGHT' ? -1 : 1;
    trackOffsets[name] = baseOff + sgn * sp;
  });

  // Layer containers
  const layerGroups = new Map();
  const labels = [];
  const crossoverTags = [];
  const bounds = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  const featureBounds = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };

  const isFeatureLayer = (layerName) => {
    const s = String(layerName || '').toUpperCase();
    return (
      s.includes('STATION') ||
      s.includes('PLATFORM') ||
      s.includes('LOOP') ||
      s.includes('TURNOUT') ||
      s.includes('CROSSOVER') ||
      s.includes('FOB') ||
      s.includes('BRIDGE') ||
      s.includes('SIGNAL')
    );
  };

  const feed = (x, y, layerName = null) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    if (x < bounds.x0) bounds.x0 = x;
    if (y < bounds.y0) bounds.y0 = y;
    if (x > bounds.x1) bounds.x1 = x;
    if (y > bounds.y1) bounds.y1 = y;
    if (layerName && isFeatureLayer(layerName)) {
      if (x < featureBounds.x0) featureBounds.x0 = x;
      if (y < featureBounds.y0) featureBounds.y0 = y;
      if (x > featureBounds.x1) featureBounds.x1 = x;
      if (y > featureBounds.y1) featureBounds.y1 = y;
    }
  };

  const getGroup = (layerName) => {
    const key = String(layerName || '0');
    if (!layerGroups.has(key)) {
      layerGroups.set(key, { name: key, items: [], style: getLayerStyle(key) });
    }
    return layerGroups.get(key);
  };

  const addLine = (p1, p2, layerName, extraDash = '') => {
    feed(p1[0], p1[1], layerName);
    feed(p2[0], p2[1], layerName);
    const grp = getGroup(layerName);
    const color = grp.style.color;
    const w = grp.style.width || '1.5';
    const dash = extraDash || grp.style.dash || '';
    const dashAttr = dash ? `stroke-dasharray="${dash}" ` : '';
    grp.items.push(
      `<line x1="${r3(p1[0])}" y1="${r3(p1[1])}" x2="${r3(p2[0])}" y2="${r3(p2[1])}" stroke="${color}" stroke-width="${w}" ${dashAttr}vector-effect="non-scaling-stroke"/>`,
    );
  };

  const addPolyline = (pts, layerName, closed = false, filled = false) => {
    if (!pts || pts.length < 2) return;
    pts.forEach((p) => feed(p[0], p[1], layerName));
    const grp = getGroup(layerName);
    const color = grp.style.color;
    const w = grp.style.width || '1.5';
    const dash = grp.style.dash || '';
    const dashAttr = dash ? `stroke-dasharray="${dash}" ` : '';
    const fillAttr = filled ? `fill="${color}" ` : 'fill="none" ';
    const d = polylinePathD(pts, closed);
    grp.items.push(
      `<path d="${esc(d)}" ${fillAttr}stroke="${color}" stroke-width="${w}" ${dashAttr}vector-effect="non-scaling-stroke"/>`,
    );
  };

  const addPath = (d, layerName, extraColor = null, extraWidth = null) => {
    const grp = getGroup(layerName);
    const color = extraColor || grp.style.color;
    const w = extraWidth || grp.style.width || '1.5';
    grp.items.push(
      `<path d="${esc(d)}" fill="none" stroke="${color}" stroke-width="${w}" vector-effect="non-scaling-stroke"/>`,
    );
  };

  const addText = (str, x, y, layerName, height = 1.0, angle = 0, halign = 1, valign = 2) => {
    feed(x, y, layerName);
    const grp = getGroup(layerName);
    labels.push({
      str: String(str),
      x: Number(x),
      y: Number(y),
      layer: layerName,
      color: grp.style.color,
      height: Number(height) || 1.0,
      angle: Number(angle) || 0,
      halign,
      valign,
    });
  };

  // ---------------------------------------------------------------------------
  // 1. Compute Base Loops & Pre-resolve Crossovers (with 64m Collision Push)
  // ---------------------------------------------------------------------------
  const resolveTrackOffset = (name, fallback) => {
    if (!name) return fallback;
    if (trackOffsets[name] != null) return trackOffsets[name];
    const key = Object.keys(trackOffsets).find((k) => k.toUpperCase() === String(name).toUpperCase());
    return key ? trackOffsets[key] : fallback;
  };

  const baseLoops = {};
  (f.loops || []).forEach((lp, idx) => {
    const name = (lp.name || `LOOP_${idx + 1}`).trim();
    const crossDist = parseNum(lp.crossoverDistance, 750.0);
    const defaultHalf = crossDist / 2.0;
    const autoC1 = Math.max(0.0, baseCenter - defaultHalf);
    const autoC2 = autoC1 + crossDist;
    const c1 = parseNum(lp.c1, autoC1);
    const c2 = parseNum(lp.c2, autoC2);
    baseLoops[name] = { c1, c2 };
  });

  const placedCrossovers = [];

  (f.crossovers || []).forEach((x, idx) => {
    const xId = (x.id || `C${idx + 1}`).trim();
    const fromTrack = (x.from || x.fromTrack || x.track1 || 'MAIN_LINE').trim();
    const otherTracks = Object.keys(trackOffsets).filter((k) => k !== fromTrack);
    const defaultTo = otherTracks.length > 0 ? otherTracks[0] : 'LOOP_1';
    const toTrack = (x.to || x.toTrack || x.track2 || defaultTo).trim();

    const fromOff = resolveTrackOffset(fromTrack, 0.0);
    let toOff = resolveTrackOffset(toTrack, fromOff !== 0.0 ? 0.0 : 5.3);
    if (Math.abs(toOff - fromOff) < 1e-4) {
      toOff = fromOff + 5.3;
    }

    const tc_m = Math.abs(toOff - fromOff);
    const is85 = String(x.turnout || '').includes('8.5');
    const n = is85 ? 8.5 : 12.0;
    const a_m = is85 ? 12.025 : 16.989;

    let ol_m;
    if (tc_m <= 6.0) {
      ol_m = tc_m * n + 2.0 * a_m;
    } else {
      const b_m = is85 ? 16.486 : 22.912;
      const r_m = is85 ? 232.26 : 441.36;
      const fAngle = Math.atan(1.0 / n);
      const cosF = Math.cos(fAngle);
      const sinF = Math.sin(fAngle);
      const tc_mm = tc_m * 1000.0;
      const r_mm = r_m * 1000.0;
      const b_mm = b_m * 1000.0;
      const arg = (r_mm * cosF + b_mm * sinF - tc_mm / 2.0) / r_mm;
      if (arg >= -1.0 && arg <= 1.0) {
        const theta = Math.acos(arg);
        const tanVal = r_mm * Math.tan((theta - fAngle) / 2.0);
        const x_mm = 2.0 * ((b_mm + tanVal) * cosF + tanVal * Math.cos(theta));
        ol_m = (x_mm + 2.0 * a_m * 1000.0) / 1000.0;
      } else {
        ol_m = tc_m * n + 2.0 * a_m;
      }
    }

    const dirStr = String(x.direction || 'FORWARD').toUpperCase();
    const isReverse = dirStr === 'REVERSE';
    const sgnDir = isReverse ? -1.0 : 1.0;

    let c1;
    const rawCh = String(x.chainage ?? x.c1 ?? x.fromChainage ?? '').trim();
    if (rawCh && rawCh.toUpperCase() !== 'AUTO') {
      c1 = parseNum(rawCh, mainCenter - ol_m / 2.0);
    } else {
      // AUTO placement
      const targetLoopName = [toTrack, fromTrack].find((t) => baseLoops[t]);
      const targetLoop = targetLoopName ? baseLoops[targetLoopName] : null;

      // Check if user selected an anchor crossover (e.g. 'C1', 'C2', 'C3')
      let anchorCrossover = null;
      if (x.autoAnchor) {
        anchorCrossover = placedCrossovers.find((c) => c.id === String(x.autoAnchor).trim());
      }

      if (anchorCrossover) {
        // Match the backend spacing datum: compare SRJ positions on a shared
        // track, then solve this crossover's START chainage from that endpoint.
        // Using min/max footprint chainages here incorrectly includes OL and
        // makes opposite-direction AUTO spacing vary with turnout length.
        const sameDir = anchorCrossover.direction === dirStr;
        const sep = sameDir ? 13.0 : 54.0;
        const anchorSrjs = {
          [anchorCrossover.fromTrack]: anchorCrossover.c1,
          [anchorCrossover.toTrack]: anchorCrossover.c2,
        };
        const sharedTrack = [fromTrack, toTrack].find((track) =>
          Object.prototype.hasOwnProperty.call(anchorSrjs, track),
        );
        if (sharedTrack) {
          const targetSrj = anchorSrjs[sharedTrack] + (isReverse ? -sep : sep);
          const candidateEndpointOffset = sharedTrack === fromTrack ? 0.0 : sgnDir * ol_m;
          c1 = targetSrj - candidateEndpointOffset;
        } else {
          c1 = dirStr === 'FORWARD' ? anchorCrossover.c2 + sep : anchorCrossover.c1 - sep;
        }
      } else if (targetLoop) {
        c1 = dirStr === 'FORWARD' ? targetLoop.c1 : targetLoop.c2;
      } else if (placedCrossovers.length > 0) {
        const prev = placedCrossovers[placedCrossovers.length - 1];
        const sameDir = prev.direction === dirStr;
        const sep = sameDir ? 13.0 : 54.0;
        const prevSrjs = { [prev.fromTrack]: prev.c1, [prev.toTrack]: prev.c2 };
        const sharedTrack = [fromTrack, toTrack].find((track) =>
          Object.prototype.hasOwnProperty.call(prevSrjs, track),
        );
        if (sharedTrack) {
          const targetSrj = prevSrjs[sharedTrack] + (isReverse ? -sep : sep);
          const candidateEndpointOffset = sharedTrack === fromTrack ? 0.0 : sgnDir * ol_m;
          c1 = targetSrj - candidateEndpointOffset;
        } else {
          c1 = dirStr === 'FORWARD' ? prev.c2 + sep : prev.c1 - sep;
        }
      } else {
        c1 = dirStr === 'FORWARD' ? Math.max(0.0, mainCenter - 300.0) : Math.min(totalLength, mainCenter + 300.0);
      }
    }

    // --- Collision check and 64m shift ---
    let collision = true;
    let iter = 0;
    while (collision && iter < 10) {
      collision = false;
      iter++;
      const curC2 = c1 + sgnDir * ol_m;

      for (const prev of placedCrossovers) {
        const sharesTrack =
          fromTrack === prev.fromTrack ||
          fromTrack === prev.toTrack ||
          toTrack === prev.fromTrack ||
          toTrack === prev.toTrack;
        if (!sharesTrack) continue;

        let collides = false;
        if (Math.abs(c1 - prev.c1) < 1.0) {
          collides = true;
        } else {
          if (fromTrack === prev.fromTrack && Math.abs(c1 - prev.c1) < 1.0) collides = true;
          if (fromTrack === prev.toTrack && Math.abs(c1 - prev.c2) < 1.0) collides = true;
          if (toTrack === prev.fromTrack && Math.abs(curC2 - prev.c1) < 1.0) collides = true;
          if (toTrack === prev.toTrack && Math.abs(curC2 - prev.c2) < 1.0) collides = true;
        }

        if (collides) {
          collision = true;
          const shift = isReverse ? -64.0 : 64.0;
          c1 += shift;
          break;
        }
      }
    }

    const c2 = c1 + sgnDir * ol_m;

    placedCrossovers.push({
      id: xId,
      c1,
      c2,
      startCh: Math.min(c1, c2),
      endCh: Math.max(c1, c2),
      direction: dirStr,
      fromTrack,
      toTrack,
      fromOff,
      toOff,
      ol_m,
      rawTurnout: x.turnout,
    });
  });

  // ---------------------------------------------------------------------------
  // 2. Compute Loop Extents & Alignment Trimming (overrun 120m from outermost SRJ)
  // ---------------------------------------------------------------------------
  const loopExtents = {};

  (f.loops || []).forEach((lp, idx) => {
    const name = (lp.name || `LOOP_${idx + 1}`).trim();
    const ref = lp.referenceTrack || 'MAIN_LINE';
    const baseOff = trackOffsets[ref] ?? 0.0;
    const sp = parseNum(lp.spacing, 5.3);
    const sgn = String(lp.side || 'LEFT').toUpperCase() === 'RIGHT' ? -1 : 1;
    const loopOff = baseOff + sgn * sp;

    // Base crossover chainages C1 and C2 (default 750m centered on station/track)
    const crossDist = parseNum(lp.crossoverDistance, 750.0);
    const defaultHalf = crossDist / 2.0;
    const autoC1 = Math.max(0.0, baseCenter - defaultHalf);
    const autoC2 = autoC1 + crossDist;
    const baseC1 = parseNum(lp.c1, autoC1);
    const baseC2 = parseNum(lp.c2, autoC2);

    let runS = baseC1;
    let runE = baseC2;

    // Check all SRJs on this loop from placedCrossovers to extend running line
    placedCrossovers.forEach((xo) => {
      if (xo.fromTrack === name || xo.toTrack === name) {
        const srj = xo.fromTrack === name ? xo.c1 : xo.c2;
        const mid = (baseC1 + baseC2) / 2.0;
        if (srj <= mid && srj < runS) runS = srj;
        if (srj > mid && srj > runE) runE = srj;
      }
    });

    // Overruns (default 120m per Indian Railways standards, exactly 120m from outermost SRJ)
    const overrunBefore = parseNum(lp.overrunBeforeC1 ?? lp.extStart, 120.0);
    const overrunAfter = parseNum(lp.overrunAfterC2 ?? lp.extEnd, 120.0);

    // Multi-loop ladder extension (matching backend count_outer_loops * 150m)
    let numOuter = 0;
    const mySide = String(lp.side || 'LEFT').toUpperCase();
    const mySpacing = Math.abs(loopOff);
    (f.loops || []).forEach((otherLp, oIdx) => {
      if (oIdx === idx) return;
      const otherName = (otherLp.name || `LOOP_${oIdx + 1}`).trim();
      const otherSide = String(otherLp.side || 'LEFT').toUpperCase();
      const otherSpacing = Math.abs(trackOffsets[otherName] ?? 5.3);
      if (otherSide === mySide && otherSpacing > mySpacing + 1e-3) {
        numOuter++;
      }
    });
    const ladderLead = numOuter * 150.0;

    const sStart = Math.max(0.0, runS - overrunBefore - ladderLead);
    const sEnd = Math.min(totalLength, runE + overrunAfter + ladderLead);

    loopExtents[name] = { c1: runS, c2: runE, baseC1, baseC2, overrunBefore, overrunAfter, ladderLead, sStart, sEnd, loopOff, ref, sp, sgn };
  });

  const isTrimmed = Boolean(f.enableMainLineTrim || options.isTrimmed || f.isTrimmed);
  let mainStart = 0.0;
  let mainEnd = totalLength;

  if (isTrimmed) {
    let minExtent = Infinity;
    let maxExtent = -Infinity;

    Object.values(loopExtents).forEach((l) => {
      if (l.sStart < minExtent) minExtent = l.sStart;
      if (l.sEnd > maxExtent) maxExtent = l.sEnd;
    });

    (f.platforms || []).forEach((p) => {
      const ch = parseNum(p.chainage, mainCenter);
      const len = parseNum(p.length, 550.0);
      if (ch - len / 2.0 < minExtent) minExtent = ch - len / 2.0;
      if (ch + len / 2.0 > maxExtent) maxExtent = ch + len / 2.0;
    });

    if (Number.isFinite(minExtent) && Number.isFinite(maxExtent) && minExtent < maxExtent) {
      // 50m margin past outermost entities, matching backend _trim_main_lines_to_srj
      mainStart = Math.max(0.0, minExtent - 50.0);
      mainEnd = Math.min(totalLength, maxExtent + 50.0);
    }
  }

  // ---------------------------------------------------------------------------
  // 1. Draw MAIN_LINE & Additional Main Lines
  // ---------------------------------------------------------------------------
  const mainPts = align.samplePolyline(mainStart, mainEnd, 0.0);
  addPolyline(mainPts, 'MAIN_LINE');

  // Direction mark: only draw when additional main lines are configured (matching backend tracks.py line 187)
  const dirAt = align.getAt(mainCenter);
  const dirAng = (Math.atan2(dirAt.tangent[1], dirAt.tangent[0]) * 180) / Math.PI;
  const hasMultipleMains = Array.isArray(f.mainLines) && f.mainLines.length > 0;
  if (hasMultipleMains) {
    const dirName = String(f.mainLineDirection || 'UP').toUpperCase();
    const arrowSgn = dirName === 'UP' ? 1 : -1;
    const arrowX = dirAt.point[0];
    const arrowY = dirAt.point[1] + (dirAt.normal[1] * 2.5 || 2.5);
    addLine(
      [arrowX - 8 * arrowSgn * dirAt.tangent[0], arrowY - 8 * arrowSgn * dirAt.tangent[1]],
      [arrowX + 8 * arrowSgn * dirAt.tangent[0], arrowY + 8 * arrowSgn * dirAt.tangent[1]],
      'DIRECTION',
    );
    addText(dirName, arrowX, arrowY + (dirAt.normal[1] * 1.5 || 1.5), 'DIRECTION', 1.0, dirAng, 1, 2);
  }

  // Additional Main Lines
  (f.mainLines || []).forEach((ml, idx) => {
    const name = `MAIN_LINE_${idx + 1}`;
    const off = trackOffsets[name] ?? 5.3;
    const pts = align.samplePolyline(mainStart, mainEnd, off);
    addPolyline(pts, name);
    const mlDir = String(ml.direction || 'DN').toUpperCase();
    const mlAt = align.getAt(mainCenter);
    const mlY = mlAt.point[1] + off + (mlDir === 'UP' ? 3.0 : -3.0);
    addText(name, mlAt.point[0], mlY, 'TRACK_LABELS', 0.9, dirAng, 1, 2);
  });

  // ---------------------------------------------------------------------------
  // 2. Draw Loop Lines (Mathematical mirror of backend generator.py)
  // ---------------------------------------------------------------------------
  (f.loops || []).forEach((lp, idx) => {
    const name = (lp.name || `LOOP_${idx + 1}`).trim();
    const ext = loopExtents[name];
    if (!ext) return;
    const { c1, c2, sStart, sEnd, loopOff } = ext;

    // Parallel loop track polyline
    const runningPts = align.samplePolyline(sStart, sEnd, loopOff);
    addPolyline(runningPts, name);

    // Buffer stop / snick marks at overrun line ends
    if (runningPts.length >= 2) {
      const startAt = align.getAt(sStart);
      const endAt = align.getAt(sEnd);
      const pS0 = [runningPts[0][0] - startAt.normal[0] * 1.2, runningPts[0][1] - startAt.normal[1] * 1.2];
      const pS1 = [runningPts[0][0] + startAt.normal[0] * 1.2, runningPts[0][1] + startAt.normal[1] * 1.2];
      addLine(pS0, pS1, name);

      const lastPt = runningPts[runningPts.length - 1];
      const pE0 = [lastPt[0] - endAt.normal[0] * 1.2, lastPt[1] - endAt.normal[1] * 1.2];
      const pE1 = [lastPt[0] + endAt.normal[0] * 1.2, lastPt[1] + endAt.normal[1] * 1.2];
      addLine(pE0, pE1, name);
    }

    // Track Label (CAL = Clear Available Length)
    const loopMid = (sStart + sEnd) / 2.0;
    const lPos = align.offsetAt(loopMid, loopOff);
    const lAt = align.getAt(loopMid);
    const ang = (Math.atan2(lAt.tangent[1], lAt.tangent[0]) * 180) / Math.PI;
    const calDist = Math.abs(c2 - c1);
    addText(
      `${name} (CAL ${calDist.toFixed(0)}m)`,
      lPos[0],
      lPos[1] + (loopOff > 0 ? 1.8 : -2.5),
      'TRACK_LABELS',
      0.9,
      ang,
      1,
      2,
    );
  });

  // ---------------------------------------------------------------------------
  // 3. Draw Crossovers (Mathematical mirror of backend crossover/core.py & geometry.py)
  // ---------------------------------------------------------------------------
  placedCrossovers.forEach((px) => {
    const { id: xId, c1, c2, fromOff, toOff, rawTurnout } = px;

    // Sample the crossover reverse-curve trajectory
    const numSamples = 24;
    const xPts = [];
    for (let k = 0; k <= numSamples; k++) {
      const t = k / numSamples;
      // Tangent-continuous smoothstep (zero first derivative at endpoints for exact track alignment)
      const sCurve = t * t * (3.0 - 2.0 * t);
      const ch = c1 + t * (c2 - c1);
      const lat = fromOff + sCurve * (toOff - fromOff);
      xPts.push(align.offsetAt(ch, lat));
    }

    addPolyline(xPts, 'CROSSOVERS');

    // SRJ indicator tick marks at start and end
    const at1 = align.getAt(c1);
    const at2 = align.getAt(c2);
    const p1 = align.offsetAt(c1, fromOff);
    const p2 = align.offsetAt(c2, toOff);
    const sgnLat = toOff > fromOff ? 1 : -1;
    const srjLen = 1.2;

    addLine(
      [p1[0], p1[1]],
      [p1[0] + at1.normal[0] * sgnLat * srjLen, p1[1] + at1.normal[1] * sgnLat * srjLen],
      'SRJ',
    );
    addLine(
      [p2[0], p2[1]],
      [p2[0] - at2.normal[0] * sgnLat * srjLen, p2[1] - at2.normal[1] * sgnLat * srjLen],
      'SRJ',
    );

    // Crossover Tag Badge at midpoint - strictly normalize angle to [-90, 90] so text is NEVER upside down or reversed
    const midIdx = Math.floor(xPts.length / 2);
    const midPt = xPts[midIdx] || align.offsetAt((c1 + c2) / 2.0, (fromOff + toOff) / 2.0);
    const dx = p2[0] - p1[0];
    const dy = p2[1] - p1[1];
    let ang = (Math.atan2(dy, dx) * 180.0) / Math.PI;
    while (ang > 90) ang -= 180;
    while (ang < -90) ang += 180;

    crossoverTags.push({
      id: xId,
      x: midPt[0],
      y: midPt[1],
      ang,
    });

    // Turnout type annotation text
    const tDes = (rawTurnout || '1:12').replace(':', ' in ');
    addText(tDes, midPt[0], midPt[1] + sgnLat * 1.5, 'CROSSOVERS', 0.8, ang, 1, 2);
  });

  // ---------------------------------------------------------------------------
  // 4. Draw Platforms & Station Buildings (Mathematical mirror of backend platform/station)
  // ---------------------------------------------------------------------------
  const platformBoundsMap = {};

  (f.platforms || []).forEach((p, idx) => {
    // References from the form and backend use IDs, independent of display names.
    const layerName = `PLATFORM_${idx + 1}`;
    const pType = String(p.type || 'SIDE').toUpperCase();
    const pLen = parseNum(p.length, 550.0);
    const pWidth = parseNum(p.width, 7.0);
    const pClr = parseNum(p.clearance, 1.68);
    const stationIndex = p.stationIndex ?? p.station_index ?? (stationMarkers.length === 1 ? 0 : null);
    const referenceDistance = stationIndex == null ? null : stationDistance(stationMarkers[stationIndex]);
    const centerCh = p.centerOnTrack === false
      ? parseNum(p.startChainage, 0.0) + pLen / 2.0
      : referenceDistance ?? parseNum(p.chainage, mainCenter);

    let nearOff, farOff, isRight, trackOff;
    if (pType === 'ISLAND') {
      const trk1 = p.track || 'MAIN_LINE';
      const trk2 = p.track2 || Object.keys(trackOffsets).find((k) => k !== trk1) || 'LOOP_1';
      const off1 = trackOffsets[trk1] ?? 0.0;
      const off2 = trackOffsets[trk2] ?? 5.3;
      const lowOff = Math.min(off1, off2);
      const highOff = Math.max(off1, off2);
      trackOff = lowOff;
      nearOff = lowOff + pClr;
      farOff = highOff - pClr;
      isRight = false;
    } else {
      const track = p.track || 'MAIN_LINE';
      isRight = String(p.side || 'LEFT').toUpperCase() === 'RIGHT';
      trackOff = trackOffsets[track] ?? 0.0;
      const sgn = isRight ? -1 : 1;
      nearOff = trackOff + sgn * pClr;
      farOff = nearOff + sgn * pWidth;
    }

    const s0 = Math.max(0.0, centerCh - pLen / 2.0);
    const s1 = Math.min(totalLength, centerCh + pLen / 2.0);

    // Check if any FOB arm widens this platform (backend platform fob_widenings)
    let fobWidenZone = null;
    let widenedFarOff = farOff;
    const sgn = isRight ? -1 : 1;
    (f.fobs || []).forEach((fb) => {
      const conn = fb.platforms || [];
      if (conn.includes(layerName)) {
        const width = parseNum(fb.width, 3.0);
        const halfFobW = width / 2.0;
        const arm = (fb.arms || []).find((a) => a.platform === layerName);
        const armSide = String(arm?.side || 'LEFT').toUpperCase();
        const armLen = parseNum(arm?.length, 17.0);

        let fbCh = mainCenter;
        if (fb.placementMode === 'fixed' && fb.chainage) {
          fbCh = parseNum(fb.chainage, mainCenter);
        } else {
          const off = parseNum(fb.offset, 40.0);
          const dir = fb.direction || 'INCREASING';
          const validStn = (f.stations || []).find((s) => s?.platform && platformBoundsMap[String(s.platform).trim()]);
          const stnLen = parseNum(validStn?.length, 40.0);
          const edge = mainCenter + (dir === 'INCREASING' ? stnLen / 2.0 : -stnLen / 2.0);
          // Backend: arm_towards_station is non-zero ONLY when arm points toward the station
          const towardsStation = (dir === 'INCREASING' && armSide === 'LEFT') || (dir === 'DECREASING' && armSide === 'RIGHT');
          const armTowardsStation = towardsStation ? armLen : 0.0;
          const extra = halfFobW + armTowardsStation;
          fbCh = dir === 'INCREASING' ? edge + off + extra : edge - (off + extra);
        }

        if (fbCh >= s0 && fbCh <= s1 && armLen > 0) {
          // IRS SOD clearance: FOB arm outer edge = 5.33 + arm_w, required widening = 5.33 + arm_w + 1.0
          const armW = Math.max(3.0, width);
          const armOuterDist = 5.33 + armW;
          const curFarDist = Math.abs(farOff - trackOff);
          if (curFarDist < armOuterDist) {
            const widenedDist = armOuterDist + 1.0;
            widenedFarOff = trackOff + sgn * widenedDist;

            let fobMinCh, fobMaxCh;
            // RIGHT = toward higher chainage (+X), LEFT = toward lower chainage (-X)
            if (armSide === 'RIGHT') {
              fobMinCh = fbCh - halfFobW;
              fobMaxCh = fbCh + halfFobW + armLen;
            } else {
              fobMinCh = fbCh - halfFobW - armLen;
              fobMaxCh = fbCh + halfFobW;
            }
            fobWidenZone = {
              sStart: Math.max(s0, fobMinCh - 1.0),
              sEnd: Math.min(s1, fobMaxCh + 1.0),
            };
          }
        }
      }
    });

    const pA = align.offsetAt(s0, nearOff);
    const pB = align.offsetAt(s1, nearOff);
    const pC = align.offsetAt(s1, farOff);
    const pD = align.offsetAt(s0, farOff);

    if (fobWidenZone) {
      const w0 = Math.min(fobWidenZone.sStart, fobWidenZone.sEnd);
      const w1 = Math.max(fobWidenZone.sStart, fobWidenZone.sEnd);
      const pW0 = align.offsetAt(w0, farOff);
      const pW1 = align.offsetAt(w0, widenedFarOff);
      const pW2 = align.offsetAt(w1, widenedFarOff);
      const pW3 = align.offsetAt(w1, farOff);
      addPolyline([pA, pB, pC, pW3, pW2, pW1, pW0, pD], layerName, true);
    } else {
      addPolyline([pA, pB, pC, pD], layerName, true);
    }

    // Platform end stairs / ramps with ladder tread lines (matching backend platform_gen/stairs.py)
    const stairLen = 17.0;
    const sStart0 = Math.max(0.0, s0 - stairLen);
    const pStairStartA = align.offsetAt(sStart0, nearOff);
    const pStairStartB = align.offsetAt(s0, nearOff);
    const pStairStartC = align.offsetAt(s0, farOff);
    const pStairStartD = align.offsetAt(sStart0, farOff);
    addPolyline([pStairStartA, pStairStartB, pStairStartC, pStairStartD], layerName, true);
    for (let tch = sStart0 + 1.5; tch < s0 - 0.2; tch += 1.5) {
      addLine(align.offsetAt(tch, nearOff), align.offsetAt(tch, farOff), layerName);
    }

    const sEnd1 = Math.min(totalLength, s1 + stairLen);
    const pStairEndA = align.offsetAt(s1, nearOff);
    const pStairEndB = align.offsetAt(sEnd1, nearOff);
    const pStairEndC = align.offsetAt(sEnd1, farOff);
    const pStairEndD = align.offsetAt(s1, farOff);
    addPolyline([pStairEndA, pStairEndB, pStairEndC, pStairEndD], layerName, true);
    for (let tch = s1 + 1.5; tch < sEnd1 - 0.2; tch += 1.5) {
      addLine(align.offsetAt(tch, nearOff), align.offsetAt(tch, farOff), layerName);
    }

    platformBoundsMap[layerName] = {
      s0,
      s1,
      nearOff,
      farOff,
      trackOff,
      centerCh,
      isRight,
    };

    // Platform text label
    const pMid = align.offsetAt(centerCh, (nearOff + farOff) / 2.0);
    const pAt = align.getAt(centerCh);
    const pAng = (Math.atan2(pAt.tangent[1], pAt.tangent[0]) * 180) / Math.PI;
    addText(
      `HIGH LEVEL PASSENGER PLATFORM (${pLen.toFixed(0)}X${Math.abs(farOff - nearOff).toFixed(1)}m)`,
      pMid[0],
      pMid[1],
      layerName,
      1.1,
      pAng,
      1,
      2,
    );
  });

  const stationBuildingBounds = new Map();

  // Station Buildings (Mathematical mirror of backend station building flush to platform)
  (f.stations || []).forEach((stn, idx) => {
    const platName = String(stn?.platform || '').trim();
    if (!platName || !platformBoundsMap[platName]) {
      return;
    }
    const platBound = platformBoundsMap[platName];
    const sLen = parseNum(stn.length, 40.0);
    const sWidth = parseNum(stn.width, 10.0);
    const sName = stn.name || 'STATION BUILDING';

    // Respect the user's "Side of platform" selection ('LEFT' or 'RIGHT')
    const isLeftSide = String(stn?.side || 'RIGHT').toUpperCase() === 'LEFT';
    const sgn = isLeftSide ? 1 : -1;
    const topEdge = Math.max(platBound.nearOff, platBound.farOff);
    const bottomEdge = Math.min(platBound.nearOff, platBound.farOff);
    const bNear = isLeftSide ? topEdge : bottomEdge;
    const bFar = bNear + sgn * sWidth;

    // The backend centres the footprint on the selected platform. Station
    // chainage is a kilometre annotation, not a local placement in metres.
    const centerCh = (platBound.s0 + platBound.s1) / 2.0;
    const s0 = Math.max(0.0, centerCh - sLen / 2.0);
    const s1 = Math.min(totalLength, centerCh + sLen / 2.0);

    stationBuildingBounds.set(idx, { start: s0, end: s1 });
    const bA = align.offsetAt(s0, bNear);
    const bB = align.offsetAt(s1, bNear);
    const bC = align.offsetAt(s1, bFar);
    const bD = align.offsetAt(s0, bFar);
    addPolyline([bA, bB, bC, bD], 'STATION-BUILDING', true);

    const bMid = align.offsetAt(centerCh, (bNear + bFar) / 2.0);
    const bAt = align.getAt(centerCh);
    const bAng = (Math.atan2(bAt.tangent[1], bAt.tangent[0]) * 180) / Math.PI;
    addText(sName, bMid[0], bMid[1], 'STATION-BUILDING', 1.2, bAng, 1, 2);

    // Station Building dimensions matching backend station.py
    const dimY = bFar + sgn * 2.2;
    const dimLeft = align.offsetAt(s0, dimY);
    const dimRight = align.offsetAt(s1, dimY);
    addLine(dimLeft, dimRight, 'STATION-BUILDING');
    addLine(dimLeft, [dimLeft[0] + 1.2, dimLeft[1] + 0.4], 'STATION-BUILDING');
    addLine(dimLeft, [dimLeft[0] + 1.2, dimLeft[1] - 0.4], 'STATION-BUILDING');
    addLine(dimRight, [dimRight[0] - 1.2, dimRight[1] + 0.4], 'STATION-BUILDING');
    addLine(dimRight, [dimRight[0] - 1.2, dimRight[1] - 0.4], 'STATION-BUILDING');
    addText(`${sLen.toFixed(2)}`, (dimLeft[0] + dimRight[0]) / 2, dimY + sgn * 0.8, 'STATION-BUILDING', 0.8, bAng, 1, 2);

    // Station Centerline perpendicular to track (matching backend station.py)
    const clStart = align.offsetAt(centerCh, bNear - sgn * 5.0);
    const clEnd = align.offsetAt(centerCh, bFar + sgn * 15.0);
    addLine(clStart, clEnd, 'STATION-CENTER', '6 3');
    const clTextPt = align.offsetAt(centerCh, bFar + sgn * 18.0);
    addText(`C/L OF ${sName} CH:0.00 KM`, clTextPt[0], clTextPt[1], 'STATION-CENTER', 0.9, bAng, 1, 2);
    const stationIndex = stn.stationIndex ?? stn.station_index;
    const marker = stationIndex == null ? null : stationMarkers[stationIndex];
    let stationChainage = isBlank(stn.chainage) ? stn.station_chainage : stn.chainage;
    if (isBlank(stationChainage) && marker) {
      stationChainage = isBlank(marker.km) && isBlank(marker.m)
        ? marker.chainage
        : formatStartChainage(marker.km, marker.m);
    }
    if (!isBlank(stationChainage)) {
      const rawKm = String(stationChainage).trim();
      const kmLabel = Number.isFinite(Number(rawKm)) ? Number(rawKm).toFixed(3) : rawKm;
      const kmTextPt = align.offsetAt(centerCh, bFar + sgn * 20.0);
      addText(`KM: ${kmLabel}`, kmTextPt[0], kmTextPt[1], 'STATION-CENTER', 0.9, bAng, 1, 2);
    }

    // Station Flag with double-headed arrow
    const fBase = align.offsetAt(centerCh, bFar);
    const fTop = [fBase[0] + bAt.normal[0] * (sgn * 8.0), fBase[1] + bAt.normal[1] * (sgn * 8.0)];
    addLine(fBase, fTop, 'STATION-FLAG');
    addPolyline([
      fTop,
      [fTop[0] + 8.0, fTop[1] + sgn * 2.5],
      [fTop[0], fTop[1] + sgn * 5.0],
    ], 'STATION-FLAG', true, true);

    const arrowY = bFar + sgn * 4.0;
    const aL = align.offsetAt(centerCh - 5.0, arrowY);
    const aR = align.offsetAt(centerCh + 5.0, arrowY);
    addLine(aL, aR, 'STATION-FLAG');
    addLine(aL, [aL[0] + 1.0, aL[1] + 0.4], 'STATION-FLAG');
    addLine(aL, [aL[0] + 1.0, aL[1] - 0.4], 'STATION-FLAG');
    addLine(aR, [aR[0] - 1.0, aR[1] + 0.4], 'STATION-FLAG');
    addLine(aR, [aR[0] - 1.0, aR[1] - 0.4], 'STATION-FLAG');
  });

  // ---------------------------------------------------------------------------
  // 5. Draw FOBs (Foot Over Bridges)
  // ---------------------------------------------------------------------------
  (f.fobs || []).forEach((fb, idx) => {
    const width = parseNum(fb.width, 3.0);
    const halfW = width / 2.0;
    const connPlats = fb.platforms || Object.keys(platformBoundsMap);
    if (connPlats.length < 2) return;

    let fbCh = mainCenter;
    if (fb.placementMode === 'fixed') {
      fbCh = resolveBridgeDistance(f, { placementMode: 'fixed', chainage: fb.chainage });
      if (!Number.isFinite(fbCh) || fbCh < 0 || fbCh > totalLength) return;
    } else {
      const off = parseNum(fb.offset, 40.0);
      const dir = fb.direction || 'INCREASING';
      const validStn = (f.stations || []).find((s) => s?.platform && platformBoundsMap[String(s.platform).trim()]);
      const stnLen = parseNum(validStn?.length, 40.0);
      const edge = mainCenter + (dir === 'INCREASING' ? stnLen / 2.0 : -stnLen / 2.0);

      // Check if any arm goes towards station (backend resolve_fob_chainage)
      let armTowardsStation = 0.0;
      (fb.arms || []).forEach((arm) => {
        const armSide = String(arm.side || 'LEFT').toUpperCase();
        const armLen = parseNum(arm.length, 17.0);
        const towards = (dir === 'INCREASING' && armSide === 'LEFT') || (dir === 'DECREASING' && armSide === 'RIGHT');
        if (towards) {
          armTowardsStation = Math.max(armTowardsStation, armLen);
        }
      });
      const extra = halfW + armTowardsStation;
      fbCh = dir === 'INCREASING' ? edge + off + extra : edge - (off + extra);
    }

    const offs = connPlats.map((p) => {
      const b = platformBoundsMap[p];
      return b ? [b.nearOff, b.farOff] : [0, 5.3];
    }).flat();

    const minOff = Math.min(...offs);
    const maxOff = Math.max(...offs);

    const fA = align.offsetAt(fbCh - halfW, minOff);
    const fB = align.offsetAt(fbCh + halfW, minOff);
    const fC = align.offsetAt(fbCh + halfW, maxOff);
    const fD = align.offsetAt(fbCh - halfW, maxOff);
    addPolyline([fA, fB, fC, fD], 'FOB', true);

    // Landing arms (RIGHT = toward higher chainage +X, LEFT = toward lower chainage -X)
    (fb.arms || []).forEach((arm) => {
      const pName = arm.platform;
      const b = platformBoundsMap[pName];
      if (!b) return;
      const aLen = parseNum(arm.length, 17.0);
      if (aLen <= 0) return;
      const aSide = String(arm.side || 'LEFT').toUpperCase();
      const stride = aSide === 'RIGHT' ? 1.0 : -1.0;

      const sIn = stride > 0 ? fbCh + halfW : fbCh - halfW;
      const sOut = sIn + stride * aLen;
      const armStart = Math.min(sIn, sOut);
      const armEnd = Math.max(sIn, sOut);

      // IRS SOD clearance: near edge of FOB arm is at 5.33m from track centerline!
      const armW = Math.max(3.0, width);
      const trkOff = b.trackOff ?? 0.0;
      const sgn = b.isRight ? -1 : 1;
      const armNear = trkOff + sgn * 5.33;
      const armFar = armNear + sgn * armW;

      const aA = align.offsetAt(armStart, armNear);
      const aB = align.offsetAt(armEnd, armNear);
      const aC = align.offsetAt(armEnd, armFar);
      const aD = align.offsetAt(armStart, armFar);
      addPolyline([aA, aB, aC, aD], 'FOB', true);
    });

    const midPt = align.offsetAt(fbCh, (minOff + maxOff) / 2.0);
    const fbAt = align.getAt(fbCh);
    const fbAng = (Math.atan2(fbAt.normal[1], fbAt.normal[0]) * 180) / Math.PI;
    addText('FOOT OVER BRIDGE', midPt[0], midPt[1], 'FOB', 1.0, fbAng, 1, 2);
  });

  // ---------------------------------------------------------------------------
  // 6. Draw bridges (Bridges)
  // ---------------------------------------------------------------------------
  (f.bridges || []).forEach((bridge, idx) => {
    const width = parseNum(bridge.width, 10);
    const distance = resolveBridgeDistance(f, bridge,
      stationBuildingBounds.get(Number(bridge.stationBuildingIndex)));
    if ((bridge.placementMode !== 'fixed' && (bridge.stationBuildingIndex == null || bridge.stationBuildingIndex === '')) ||
        !Number.isFinite(distance) || distance < 0 || distance > totalLength || width <= 0) return;
    const included = Object.entries(trackOffsets).filter(([name]) =>
      !bridge.tracks?.length || bridge.tracks.includes(name)).map(([, offset]) => offset);
    if (!included.length) return;
    const lo = Math.min(...included) - 3.5, hi = Math.max(...included) + 3.5;
    const at = align.getAt(distance), half = width / 2, diag = 8 * Math.SQRT1_2;
    const pt = (u, v) => [at.point[0] + at.tangent[0] * u + at.normal[0] * v,
      at.point[1] + at.tangent[1] * u + at.normal[1] * v];
    const layer = `BRIDGE_${idx + 1}`;
    for (const side of [-1, 1]) {
      addLine(pt(side * half, lo), pt(side * half, hi), layer);
      addLine(pt(side * half, hi), pt(side * (half + diag), hi + diag), layer);
      addLine(pt(side * half, lo), pt(side * (half + diag), lo - diag), layer);
    }
    const label = pt(0, hi + diag + 2.5);
    addText(`${bridgeTypeLabel(bridge)} BRIDGE`, label[0], label[1], layer, 1.2,
      Math.atan2(at.tangent[1], at.tangent[0]) * 180 / Math.PI, 1, 2);
  });

  // ---------------------------------------------------------------------------
  // 7. Draw Sidings
  // ---------------------------------------------------------------------------
  (f.sidings || []).forEach((sd, idx) => {
    const srcTrack = sd.sourceTrack || 'MAIN_LINE';
    const srcOff = trackOffsets[srcTrack] ?? 0.0;
    const toCh = parseNum(sd.takeOffChainage, mainCenter);
    const len = parseNum(sd.length, 200.0);
    const sp = parseNum(sd.spacing, 5.3);
    const sgn = String(sd.side || 'LEFT').toUpperCase() === 'RIGHT' ? -1 : 1;
    const sidingOff = srcOff + sgn * sp;

    const lead = Math.min(50.0, len * 0.4);
    const pStart = align.offsetAt(toCh, srcOff);
    const pRunningStart = align.offsetAt(toCh + lead, sidingOff);
    const pEnd = align.offsetAt(toCh + len, sidingOff);

    // Turnout lead
    addLine(pStart, pRunningStart, 'TURNOUT');
    // Siding track
    addLine(pRunningStart, pEnd, 'MAIN_TRACK');

    // Buffer stop at end
    const endAt = align.getAt(toCh + len);
    const bA = [pEnd[0] - endAt.normal[0] * 1.5, pEnd[1] - endAt.normal[1] * 1.5];
    const bB = [pEnd[0] + endAt.normal[0] * 1.5, pEnd[1] + endAt.normal[1] * 1.5];
    addLine(bA, bB, 'MAIN_TRACK');

    // Siding text
    const sMid = align.offsetAt(toCh + len / 2.0, sidingOff + sgn * 1.5);
    addText(sd.name || `SIDING_${idx + 1}`, sMid[0], sMid[1], 'TRACK_LABELS', 0.9, 0, 1, 2);
  });

  // ---------------------------------------------------------------------------
  // 8. Final SVG Assembly
  // ---------------------------------------------------------------------------
  if (!Number.isFinite(bounds.x0) || bounds.x0 >= bounds.x1) {
    bounds.x0 = 0.0;
    bounds.y0 = -20.0;
    bounds.x1 = totalLength;
    bounds.y1 = 20.0;
  }

  const padX = Math.max((bounds.x1 - bounds.x0) * 0.05, 15.0);
  const padY = Math.max((bounds.y1 - bounds.y0) * 0.35, 20.0);
  const x0 = bounds.x0 - padX;
  const y0 = bounds.y0 - padY;
  const w = Math.max(bounds.x1 - bounds.x0 + padX * 2, 20.0);
  const h = Math.max(bounds.y1 - bounds.y0 + padY * 2, 20.0);
  const flip = y0 + (y0 + h);

  const sortedLayers = Array.from(layerGroups.values()).sort((a, b) => {
    const order = { fencing: 1, reference: 2, platform: 3, station: 4, fob: 5, bridge: 6, signal: 7, track: 8, crossover: 9 };
    return (order[a.style.category] || 5) - (order[b.style.category] || 5);
  });

  const geomMarkup = sortedLayers
    .filter((g) => g.items.length > 0)
    .map(
      (g) =>
        `<g data-layer="${esc(g.name)}" class="cad-layer layer-${esc(g.name.replace(/[^a-zA-Z0-9_-]/g, '_'))}">\n${g.items.join('\n')}\n</g>`,
    )
    .join('\n');

  const textMarkup = labels
    .map((t) => {
      const anchor = t.halign === 2 ? 'end' : t.halign === 1 ? 'middle' : 'start';
      const baseline = t.valign === 2 ? 'central' : 'central';
      return `<text data-layer="${esc(t.layer)}" x="${r3(t.x)}" y="${r3(flip - t.y)}" font-size="${r3(t.height)}" fill="${t.color}" font-weight="600" text-anchor="${anchor}" dominant-baseline="${baseline}" paint-order="stroke fill" stroke="#0a0e17" stroke-width="${r3(Math.max(t.height * 0.16, 0.08))}" stroke-linejoin="round" transform="rotate(${r3(-t.angle)} ${r3(t.x)} ${r3(flip - t.y)})">${esc(t.str)}</text>`;
    })
    .join('\n');

  const crossoverBadges = crossoverTags.map((tag) => {
    const labelStr = tag.id;
    const badgeH = 2.2;
    const badgeW = Math.max(badgeH * 1.8, labelStr.length * badgeH * 0.75 + badgeH * 0.8);
    const svgX = tag.x;
    const svgY = flip - tag.y;
    const rx = badgeH * 0.35;
    return (
      `<g data-layer="CROSSOVERS" class="cad-crossover-tag" transform="rotate(${r3(-tag.ang)} ${r3(svgX)} ${r3(svgY)})">` +
      `<rect x="${r3(svgX - badgeW / 2)}" y="${r3(svgY - badgeH / 2)}" width="${r3(badgeW)}" height="${r3(badgeH)}" rx="${r3(rx)}" class="crossover-badge-bg"/>` +
      `<text x="${r3(svgX)}" y="${r3(svgY)}" font-size="${r3(badgeH * 0.65)}" class="crossover-badge-text">${esc(labelStr)}</text>` +
      `</g>`
    );
  });

  const svgParts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${r3(w)}" height="${r3(h)}" viewBox="${r3(x0)} ${r3(y0)} ${r3(w)} ${r3(h)}" preserveAspectRatio="xMidYMid meet">`,
    `<style>`,
    `  .cad-geom line, .cad-geom path, .cad-geom circle { vector-effect: non-scaling-stroke; stroke-linecap: round; stroke-linejoin: round; }`,
    `  .cad-text text { font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }`,
    `  .crossover-badge-bg { fill: #0f172a; stroke: #38bdf8; stroke-width: 0.35px; vector-effect: non-scaling-stroke; }`,
    `  .crossover-badge-text { fill: #ffffff !important; stroke: none !important; font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 700 !important; text-anchor: middle !important; dominant-baseline: central !important; }`,
    `</style>`,
    `<rect x="${r3(x0)}" y="${r3(y0)}" width="${r3(w)}" height="${r3(h)}" fill="${BG_DARK}" class="cad-bg"/>`,
    `<g transform="translate(0 ${r3(flip)}) scale(1 -1)" fill="none" class="cad-geom">`,
    geomMarkup,
    `</g>`,
    `<g class="cad-text">`,
    textMarkup,
    `</g>`,
    `<g class="cad-crossovers-overlay">`,
    crossoverBadges.join('\n'),
    `</g>`,
    `</svg>`,
  ];

  let totalEntities = 0;
  layerGroups.forEach((g) => (totalEntities += g.items.length));
  totalEntities += labels.length;

  const hasFeatures = Number.isFinite(featureBounds.x0) && featureBounds.x0 < featureBounds.x1;
  const fx0 = hasFeatures ? featureBounds.x0 : bounds.x0;
  const fx1 = hasFeatures ? featureBounds.x1 : bounds.x1;
  const fy0 = hasFeatures ? featureBounds.y0 : bounds.y0;
  const fy1 = hasFeatures ? featureBounds.y1 : bounds.y1;

  const featureFocus = {
    hasFeatures,
    x: (fx0 + fx1) / 2,
    y: flip - (fy0 + fy1) / 2,
    spanX: Math.max(fx1 - fx0, 10),
    spanY: Math.max(fy1 - fy0, 10),
  };

  const midPt = align.getAt(mainCenter).point;
  const trackMidpoint = {
    x: midPt[0],
    y: flip - midPt[1],
  };

  const trackWaypoints = [
    { name: 'Start', x: align.getAt(0).point[0], y: flip - align.getAt(0).point[1] },
    { name: 'Midpoint', x: midPt[0], y: flip - midPt[1] },
    { name: 'End', x: align.getAt(totalLength).point[0], y: flip - align.getAt(totalLength).point[1] },
  ];

  return {
    svg: svgParts.join('\n'),
    w,
    h,
    x0,
    y0,
    entities: totalEntities,
    layers: Array.from(layerGroups.keys()),
    featureFocus,
    trackMidpoint,
    trackWaypoints,
    crossoverTags,
    crossoverCount: crossoverTags.length,
    placedCrossovers,
    isDynamic: true,
  };
}
