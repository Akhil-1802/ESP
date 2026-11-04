/**
 * High-accuracy DXF plan-view renderer for engineering schematics and previews.
 */

import DxfParser from 'dxf-parser';
import {
  arcPathD,
  esc,
  finite,
  mtextPlain,
  parseLeaders,
  polylinePathD,
  r3,
  splinePathD,
  vertsOf,
} from './dxfPathUtils.js';

export const BG_DARK = '#0a0e17';
export const BG_LIGHT = '#f8fafc';

export const LAYER_CONFIG = {
  // Main Running Tracks
  MAIN_TRACK: { color: '#38bdf8', width: '2.4', category: 'track', label: 'Main Track' },
  MAIN_LINE: { color: '#38bdf8', width: '2.4', category: 'track', label: 'Main Line' },
  LOOP_1: { color: '#fbbf24', width: '2.2', category: 'track', label: 'Loop 1' },
  LOOP_2: { color: '#f59e0b', width: '2.2', category: 'track', label: 'Loop 2' },
  LOOP_3: { color: '#d97706', width: '2.2', category: 'track', label: 'Loop 3' },
  TURNOUT: { color: '#fb923c', width: '2.2', category: 'crossover', label: 'Turnouts' },
  TURNOUT_SWITCH: { color: '#f97316', width: '2.2', category: 'crossover', label: 'Switches' },
  TURNOUT_CROSSING: { color: '#ea580c', width: '2.2', category: 'crossover', label: 'Crossings' },
  LOOP_CROSSOVER: { color: '#fb923c', width: '2.2', category: 'crossover', label: 'Loop Crossovers' },
  CROSSOVERS: { color: '#fb923c', width: '2.2', category: 'crossover', label: 'Crossovers' },
  OVER_RUN: { color: '#f87171', width: '1.8', category: 'track', label: 'Over-run Lines' },

  // Reference & Centerlines
  TRACK_CENTERS: { color: '#94a3b8', width: '1.0', dash: '8 4', category: 'reference', label: 'Track Centers' },
  DIRECTION: { color: '#facc15', width: '1.6', category: 'reference', label: 'Direction' },

  // Platforms & Structures
  PLATFORM_1: { color: '#c084fc', width: '2.0', category: 'platform', label: 'High Level Passenger Platform' },
  PLATFORM_2: { color: '#a855f7', width: '2.0', category: 'platform', label: 'High Level Passenger Platform' },
  'PLATFORM-STAIRS': { color: '#d8b4fe', width: '1.0', category: 'platform', label: 'Platform Stairs' },
  'PLATFORM-DIM': { color: '#64748b', width: '0.9', category: 'reference', label: 'Platform Dimensions' },
  'FOB-DIM': { color: '#64748b', width: '0.9', category: 'reference', label: 'FOB Dimensions' },
  'STATION-BUILDING': { color: '#818cf8', width: '2.0', category: 'station', label: 'Station Building' },
  'STATION-CENTER': { color: '#6366f1', width: '1.0', dash: '6 3', category: 'station', label: 'Station Center' },
  'STATION-FLAG': { color: '#ef4444', width: '1.4', category: 'station', label: 'Station Flag' },
  FOB_1: { color: '#2dd4bf', width: '2.0', category: 'fob', label: 'Foot Over Bridge' },
  ROB: { color: '#ef4444', width: '2.5', category: 'rob', label: 'Road Over Bridge (SGFD)' },
  SGFD: { color: '#ef4444', width: '2.5', category: 'rob', label: 'Road Over Bridge (SGFD)' },
  'ROB-DIM': { color: '#64748b', width: '0.9', category: 'reference', label: 'ROB Dimensions' },
  'SGFD-DIM': { color: '#64748b', width: '0.9', category: 'reference', label: 'SGFD Dimensions' },
  'ROB-CENTER': { color: '#94a3b8', width: '1.0', dash: '6 3', category: 'reference', label: 'ROB Centerline' },
  'SGFD-CENTER': { color: '#94a3b8', width: '1.0', dash: '6 3', category: 'reference', label: 'SGFD Centerline' },

  // Signals
  SRJ: { color: '#ef4444', width: '2.0', category: 'signal', label: 'SRJ Points' },
  FM: { color: '#f43f5e', width: '4.0', category: 'signal', label: 'Fouling Marks' },
  CHAINAGE: { color: '#ef4444', width: '1.2', dash: '4 3', category: 'reference', label: 'Station Chainage' },
  GRADIENT: { color: '#ef4444', width: '1.6', category: 'reference', label: 'Gradient Annotation' },

  // Boundary / Fencing
  FENCING: { color: '#475569', width: '0.9', opacity: '0.6', category: 'fencing', label: 'Fencing' },
};

const PALETTE = ['#38bdf8', '#fbbf24', '#34d399', '#f43f5e', '#a78bfa', '#22d3ee', '#fb923c'];
export const FORCE_STROKE_COLOR = '#ff0000';

export function getLayerStyle(layer) {
  const name = String(layer ?? '').trim();
  const red = (style) =>
    FORCE_STROKE_COLOR ? { ...style, color: FORCE_STROKE_COLOR } : style;
  if (LAYER_CONFIG[name]) {
    return red(LAYER_CONFIG[name]);
  }

  const u = name.toUpperCase();
  if (u.includes('MAIN') || (u.includes('TRACK') && !u.includes('CENTER'))) {
    return red({ color: '#38bdf8', width: '2.4', category: 'track', label: name });
  }
  if (u.includes('LOOP')) {
    return red({ color: '#fbbf24', width: '2.2', category: 'track', label: name });
  }
  if (u.includes('SIDING')) {
    return red({ color: '#fb923c', width: '2.2', category: 'track', label: name });
  }
  if (u.includes('CROSS') || u.includes('TURNOUT')) {
    return red({ color: '#fb923c', width: '2.2', category: 'crossover', label: name });
  }
  if (u.includes('DIM')) {
    return red({ color: '#64748b', width: '0.9', category: 'reference', label: name });
  }
  if (u.includes('PLATFORM')) {
    return red({ color: '#c084fc', width: '2.0', category: 'platform', label: name });
  }
  if (u.includes('STATION')) {
    return red({ color: '#818cf8', width: '2.0', category: 'station', label: name });
  }
  if (u.includes('FOB')) {
    return red({ color: '#2dd4bf', width: '2.0', category: 'fob', label: name });
  }
  if (u.includes('ROB') || u.includes('SGFD')) {
    return red({ color: '#ef4444', width: '2.5', category: 'rob', label: name });
  }
  if (u.includes('FENCE')) {
    return red({ color: '#475569', width: '0.9', opacity: '0.6', category: 'fencing', label: name });
  }
  if (u.includes('FM')) {
    return red({ color: '#f43f5e', width: '4.0', category: 'signal', label: name });
  }
  if (u.includes('SRJ') || u.includes('SIGNAL')) {
    return red({ color: '#ef4444', width: '2.0', category: 'signal', label: name });
  }
  if (u.includes('CHAINAGE') || u.includes('F/CSB')) {
    return red({ color: '#ef4444', width: '1.2', category: 'reference', label: name });
  }

  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return { color: PALETTE[h % PALETTE.length], width: '1.5', category: 'other', label: name };
}

/** Render a DXF to SVG structure and layer metadata. */
export function dxfToSvg(input) {
  const text =
    typeof input === 'string'
      ? input
      : new TextDecoder('utf-8', { fatal: false }).decode(input);
  const dxf = new DxfParser().parseSync(text);
  const entities = (dxf && dxf.entities) || [];
  const extraLeaders = parseLeaders(text);
  if (extraLeaders.length > 0) {
    entities.push(...extraLeaders);
  }

  const layerGroups = new Map();
  const labels = [];
  const bounds = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  const featureBounds = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  let longestPoints = [];
  let maxPointsCount = 0;
  const allTrackCoords = [];

  const isFeatureLayer = (layerName) => {
    const s = String(layerName || '').toUpperCase();
    return (
      s.includes('STATION') ||
      s.includes('PLATFORM') ||
      s.includes('LOOP') ||
      s.includes('TURNOUT') ||
      s.includes('CROSSOVER') ||
      s.includes('FOB') ||
      s.includes('ROB') ||
      s.includes('GRADIENT') ||
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

  for (const e of entities) {
    const layer = e.layer || '0';
    const group = getGroup(layer);
    const style = group.style;
    const color = style.color;
    const strokeWidth = style.width || '1.5';
    const entityDash = e.lineType && (String(e.lineType).toUpperCase().includes('DOT') || String(e.lineType).toUpperCase().includes('DASH'))
      ? (String(e.lineType).toUpperCase().includes('DOT') ? '1 2' : '4 3')
      : (style.dash || '');
    const dashAttr = entityDash ? `stroke-dasharray="${entityDash}" ` : '';
    const opacityAttr = style.opacity ? `opacity="${style.opacity}" ` : '';

    switch (e.type) {
      case 'LINE': {
        const pts = vertsOf(e.vertices);
        if (pts.length < 2) break;
        pts.forEach((p) => {
          feed(p[0], p[1], layer);
          allTrackCoords.push(p);
        });
        if (pts.length > maxPointsCount) {
          maxPointsCount = pts.length;
          longestPoints = pts;
        }
        group.items.push(
          `<line x1="${r3(pts[0][0])}" y1="${r3(pts[0][1])}" x2="${r3(pts[1][0])}" y2="${r3(pts[1][1])}" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
        );
        break;
      }
      case 'LWPOLYLINE':
      case 'POLYLINE': {
        const pts = vertsOf(e.vertices);
        if (pts.length < 2) break;
        pts.forEach((p) => {
          feed(p[0], p[1], layer);
          allTrackCoords.push(p);
        });
        if (pts.length > maxPointsCount) {
          maxPointsCount = pts.length;
          longestPoints = pts;
        }
        const d = polylinePathD(pts, !!e.shape);
        if (d) {
          const u = String(layer || '').toUpperCase();
          const filled = !!e.shape && (u.includes('FM') || u.includes('SRJ'));
          const fillAttr = filled ? `fill="${color}" fill-opacity="1" ` : `fill="none" `;
          group.items.push(
            `<path d="${esc(d)}" ${fillAttr}stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
          );
        }
        break;
      }
      case 'SPLINE': {
        const pts = vertsOf(e.fitPoints && e.fitPoints.length ? e.fitPoints : e.controlPoints);
        if (pts.length < 2) break;
        pts.forEach((p) => {
          feed(p[0], p[1], layer);
          allTrackCoords.push(p);
        });
        if (pts.length > maxPointsCount) {
          maxPointsCount = pts.length;
          longestPoints = pts;
        }
        const d = splinePathD(pts, false);
        if (d) {
          group.items.push(
            `<path d="${esc(d)}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
          );
        }
        break;
      }
      case 'ARC': {
        const c = e.center || {};
        const rad = Number(e.radius);
        if (!Number.isFinite(c.x) || !Number.isFinite(c.y) || !finite(rad) || rad <= 0) break;
        feed(c.x - rad, c.y - rad, layer);
        feed(c.x + rad, c.y + rad, layer);
        const d = arcPathD(c.x, c.y, rad, e.startAngle, e.endAngle);
        group.items.push(
          `<path d="${esc(d)}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
        );
        break;
      }
      case 'CIRCLE': {
        const c = e.center || {};
        const rad = Number(e.radius);
        if (!Number.isFinite(c.x) || !Number.isFinite(c.y) || !finite(rad) || rad <= 0) break;
        feed(c.x - rad, c.y - rad, layer);
        feed(c.x + rad, c.y + rad, layer);
        group.items.push(
          `<circle cx="${r3(c.x)}" cy="${r3(c.y)}" r="${r3(rad)}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}vector-effect="non-scaling-stroke"/>`,
        );
        break;
      }
      case 'POINT': {
        const p = e.position || {};
        if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) break;
        feed(p.x, p.y, layer);
        group.items.push(
          `<circle cx="${r3(p.x)}" cy="${r3(p.y)}" r="1.2" fill="${color}" stroke="none" vector-effect="non-scaling-stroke"/>`,
        );
        break;
      }
      case 'TEXT':
      case 'MTEXT': {
        const hasAlign = (e.halign !== undefined && e.halign !== 0) || (e.valign !== undefined && e.valign !== 0);
        const at = hasAlign && e.endPoint ? e.endPoint : (e.startPoint || e.position || e.insertionPoint || {});
        if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) break;
        const raw = e.type === 'TEXT' ? String(e.text ?? '') : mtextPlain(e.text);
        if (!raw) break;
        const height = Number(e.textHeight ?? e.height ?? e.nominalTextHeight ?? 1) || 1;
        const lines = raw.split(/\r?\n|\\P/gi);
        lines.forEach((line, idx) => {
          const str = line.trim();
          if (!str) return;
          const ly = at.y - idx * height * 1.4;
          feed(at.x, ly, layer);
          feed(at.x + str.length * height * 0.7, ly + height, layer);
          feed(at.x - str.length * height * 0.7, ly - height, layer);
          labels.push({
            x: Number(at.x),
            y: Number(ly),
            str,
            height,
            angle: Number(e.rotation ?? 0) || 0,
            color,
            layer,
            halign: Number(e.halign ?? 0),
            valign: Number(e.valign ?? 0),
          });
        });
        break;
      }
      case 'INSERT': {
        const blk = e.name && dxf.blocks && dxf.blocks[e.name];
        if (blk && Array.isArray(blk.entities)) {
          const insX = Number(e.position?.x ?? e.insertionPoint?.x ?? 0);
          const insY = Number(e.position?.y ?? e.insertionPoint?.y ?? 0);
          const sx = Number(e.xScale ?? 1), sy = Number(e.yScale ?? 1);
          const rotRad = ((Number(e.rotation ?? 0)) * Math.PI) / 180;
          const cosR = Math.cos(rotRad), sinR = Math.sin(rotRad);
          const tf = (p) => [insX + p[0] * sx * cosR - p[1] * sy * sinR, insY + p[0] * sx * sinR + p[1] * sy * cosR];
          for (const sub of blk.entities) {
            if (sub.type === 'LINE') {
              const pts = vertsOf(sub.vertices);
              if (pts.length >= 2) {
                const p0 = tf(pts[0]), p1 = tf(pts[1]);
                feed(p0[0], p0[1]); feed(p1[0], p1[1]);
                group.items.push(`<line x1="${r3(p0[0])}" y1="${r3(p0[1])}" x2="${r3(p1[0])}" y2="${r3(p1[1])}" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`);
              }
            } else if (sub.type === 'MTEXT' || sub.type === 'TEXT') {
              const at = sub.position || sub.insertionPoint || sub.startPoint || {};
              if (Number.isFinite(at.x) && Number.isFinite(at.y)) {
                const str = sub.type === 'TEXT' ? String(sub.text ?? '') : mtextPlain(sub.text);
                if (str) {
                  const p = tf([at.x, at.y]);
                  const h = (Number(sub.textHeight ?? sub.charHeight ?? sub.height ?? 0.8) || 0.8) * Math.abs(sy);
                  const rot = (Number(sub.rotation ?? 0) + Number(e.rotation ?? 0));
                  feed(p[0], p[1]);
                  labels.push({
                    x: Number(p[0]),
                    y: Number(p[1]),
                    str,
                    height: h,
                    angle: rot,
                    color,
                    layer,
                    halign: Number(sub.halign ?? 0),
                    valign: Number(sub.valign ?? 0),
                  });
                }
              }
            }
          }
        }
        break;
      }
      case 'DIMENSION': {
        const blockName = e.block;
        const block = blockName && dxf.blocks && dxf.blocks[blockName];
        if (block && Array.isArray(block.entities)) {
          for (const sub of block.entities) {
            if (sub.type === 'LINE') {
              const pts = vertsOf(sub.vertices);
              if (pts.length >= 2) {
                pts.forEach((p) => feed(p[0], p[1]));
                group.items.push(
                  `<line x1="${r3(pts[0][0])}" y1="${r3(pts[0][1])}" x2="${r3(pts[1][0])}" y2="${r3(pts[1][1])}" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
                );
              }
            } else if (sub.type === 'INSERT') {
              const blk = sub.name && dxf.blocks && dxf.blocks[sub.name];
              if (blk && Array.isArray(blk.entities)) {
                const insX = Number(sub.position?.x ?? 0), insY = Number(sub.position?.y ?? 0);
                const sx = Number(sub.xScale ?? 1), sy = Number(sub.yScale ?? 1);
                const rotRad = ((Number(sub.rotation ?? 0)) * Math.PI) / 180;
                const cosR = Math.cos(rotRad), sinR = Math.sin(rotRad);
                const tf = (p) => [insX + (p[0] * sx) * cosR - (p[1] * sy) * sinR, insY + (p[0] * sx) * sinR + (p[1] * sy) * cosR];
                for (const bEnt of blk.entities) {
                  if (bEnt.type === 'LINE') {
                    const bPts = vertsOf(bEnt.vertices);
                    if (bPts.length >= 2) {
                      const p0 = tf(bPts[0]), p1 = tf(bPts[1]);
                      feed(p0[0], p0[1]); feed(p1[0], p1[1]);
                      group.items.push(`<line x1="${r3(p0[0])}" y1="${r3(p0[1])}" x2="${r3(p1[0])}" y2="${r3(p1[1])}" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`);
                    }
                  } else if (bEnt.type === 'SOLID' || bEnt.type === 'LWPOLYLINE') {
                    const bPts = vertsOf(bEnt.points || bEnt.vertices);
                    if (bPts.length >= 2) {
                      const tfPts = bPts.map(tf);
                      tfPts.forEach((p) => feed(p[0], p[1]));
                      const d = polylinePathD(tfPts, true);
                      if (d) group.items.push(`<path d="${esc(d)}" fill="${color}" stroke="${color}" stroke-width="${strokeWidth}" ${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`);
                    }
                  }
                }
              }
            } else if (sub.type === 'MTEXT' || sub.type === 'TEXT') {
              const at = sub.position || sub.insertionPoint || {};
              if (Number.isFinite(at.x) && Number.isFinite(at.y)) {
                const str = sub.type === 'TEXT' ? String(sub.text ?? '') : mtextPlain(sub.text);
                if (str) {
                  const h = Number(sub.textHeight ?? sub.charHeight ?? sub.height ?? 0.8) || 0.8;
                  feed(at.x, at.y);
                  feed(at.x + str.length * h * 0.7, at.y + h);
                  feed(at.x - str.length * h * 0.7, at.y - h);
                  labels.push({
                    x: Number(at.x),
                    y: Number(at.y),
                    str,
                    height: h,
                    angle: Number(sub.rotation ?? 0) || 0,
                    color,
                    layer,
                    halign: 1,
                    valign: 2,
                  });
                }
              }
            }
          }
        }
        break;
      }
      case 'LEADER': {
        const pts = vertsOf(e.vertices);
        if (pts.length < 2) break;
        pts.forEach((p) => feed(p[0], p[1], layer));
        for (let i = 0; i < pts.length - 1; i++) {
          group.items.push(
            `<line x1="${r3(pts[i][0])}" y1="${r3(pts[i][1])}" x2="${r3(pts[i + 1][0])}" y2="${r3(pts[i + 1][1])}" stroke="${color}" stroke-width="${strokeWidth}" ${dashAttr}${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
          );
        }
        const p0 = pts[0];
        const p1 = pts[1];
        const dx = p0[0] - p1[0];
        const dy = p0[1] - p1[1];
        const dn = Math.hypot(dx, dy) || 1.0;
        const ux = dx / dn;
        const uy = dy / dn;
        const al = 2.0;
        const aw = 0.7;
        const bx = p0[0] - ux * al;
        const by = p0[1] - uy * al;
        const tri = [
          [p0[0], p0[1]],
          [bx - uy * aw, by + ux * aw],
          [bx + uy * aw, by - ux * aw],
        ];
        tri.forEach((p) => feed(p[0], p[1], layer));
        const triD = `M ${r3(tri[0][0])},${r3(tri[0][1])} L ${r3(tri[1][0])},${r3(tri[1][1])} L ${r3(tri[2][0])},${r3(tri[2][1])} Z`;
        group.items.push(
          `<path d="${triD}" fill="${color}" stroke="${color}" stroke-width="${strokeWidth}" ${opacityAttr}stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
        );
        break;
      }
      default:
        break;
    }
  }

  if (!Number.isFinite(bounds.x0)) {
    throw new Error('No drawable entities found in this DXF.');
  }

  const padX = Math.max((bounds.x1 - bounds.x0) * 0.05, 5.0);
  const padY = Math.max((bounds.y1 - bounds.y0) * 0.05, 5.0);
  const x0 = bounds.x0 - padX;
  const y0 = bounds.y0 - padY;
  const w = Math.max(bounds.x1 - bounds.x0 + padX * 2, 1e-6);
  const h = Math.max(bounds.y1 - bounds.y0 + padY * 2, 1e-6);
  const flip = y0 + (y0 + h);

  const sortedLayers = Array.from(layerGroups.values()).sort((a, b) => {
    const order = { fencing: 1, reference: 2, platform: 3, station: 4, fob: 5, rob: 6, signal: 7, track: 8, crossover: 9 };
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
      const baseline = t.halign === 2 && (t.valign === 0 || !t.valign) ? 'alphabetic' : (t.valign === 2 ? 'central' : 'central');
      return `<text data-layer="${esc(t.layer)}" x="${r3(t.x)}" y="${r3(flip - t.y)}" font-size="${r3(t.height)}" fill="${t.color}" font-weight="600" text-anchor="${anchor}" dominant-baseline="${baseline}" paint-order="stroke fill" stroke="#0a0e17" stroke-width="${r3(Math.max(t.height * 0.16, 0.08))}" stroke-linejoin="round" transform="rotate(${r3(-t.angle)} ${r3(t.x)} ${r3(flip - t.y)})">${esc(t.str)}</text>`;
    })
    .join('\n');

  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${r3(w)}" height="${r3(h)}" viewBox="${r3(x0)} ${r3(y0)} ${r3(w)} ${r3(h)}" preserveAspectRatio="xMidYMid meet">`,
    `<style>`,
    `  .cad-geom line, .cad-geom path, .cad-geom circle { vector-effect: non-scaling-stroke; stroke-linecap: round; stroke-linejoin: round; }`,
    `  .cad-text text { font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }`,
    `</style>`,
    `<rect x="${r3(x0)}" y="${r3(y0)}" width="${r3(w)}" height="${r3(h)}" fill="${BG_DARK}" class="cad-bg"/>`,
    `<g transform="translate(0 ${r3(flip)}) scale(1 -1)" fill="none" class="cad-geom">`,
    geomMarkup,
    `</g>`,
    `<g class="cad-text">`,
    textMarkup,
    `</g>`,
    `</svg>`,
  ];

  let totalEntities = 0;
  layerGroups.forEach((g) => (totalEntities += g.items.length));
  totalEntities += labels.length;

  const hasFeatures = Number.isFinite(featureBounds.x0);
  const fx0 = hasFeatures ? featureBounds.x0 : bounds.x0;
  const fx1 = hasFeatures ? featureBounds.x1 : bounds.x1;
  const fy0 = hasFeatures ? featureBounds.y0 : bounds.y0;
  const fy1 = hasFeatures ? featureBounds.y1 : bounds.y1;

  // In SVG viewBox coordinates, Y is flipped: svgY = flip - worldY
  const featureFocus = {
    hasFeatures,
    x: (fx0 + fx1) / 2,
    y: flip - (fy0 + fy1) / 2,
    spanX: Math.max(fx1 - fx0, 10),
    spanY: Math.max(fy1 - fy0, 10),
  };

  const samplePts = longestPoints.length >= 2 ? longestPoints : allTrackCoords;
  let trackMidpoint = null;
  const trackWaypoints = [];

  if (samplePts.length > 0) {
    const fractions = [
      { name: 'Start', f: 0 },
      { name: '25%', f: 0.25 },
      { name: 'Center', f: 0.5 },
      { name: '75%', f: 0.75 },
      { name: 'End', f: 1.0 },
    ];
    for (const fr of fractions) {
      const idx = Math.min(Math.floor(samplePts.length * fr.f), samplePts.length - 1);
      const pt = samplePts[idx];
      if (pt && Number.isFinite(pt[0]) && Number.isFinite(pt[1])) {
        trackWaypoints.push({
          name: fr.name,
          x: pt[0],
          y: flip - pt[1],
        });
      }
    }
    const centerWp = trackWaypoints.find((w) => w.name === 'Center') || trackWaypoints[0];
    if (centerWp) {
      trackMidpoint = { x: centerWp.x, y: centerWp.y };
    }
  }

  return {
    svg: parts.join('\n'),
    w,
    h,
    x0,
    y0,
    featureFocus,
    trackMidpoint,
    trackWaypoints,
    entities: totalEntities,
    layers: Array.from(layerGroups.values()).map((g) => ({
      name: g.name,
      color: g.style.color,
      count: g.items.length,
      category: g.style.category,
      label: g.style.label || g.name,
    })),
  };
}

/** Rasterise preview SVG string to a PNG Blob. */
export function svgToPngBlob(svgText, w, h) {
  return new Promise((resolve, reject) => {
    const scale = Math.min(4, 3200 / Math.max(w, 1), 1600 / Math.max(h, 1));
    const W = Math.max(1, Math.round(w * scale));
    const H = Math.max(1, Math.round(h * scale));
    const url = URL.createObjectURL(
      new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' }),
    );
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = BG_DARK;
        ctx.fillRect(0, 0, W, H);
        ctx.drawImage(img, 0, 0, W, H);
        URL.revokeObjectURL(url);
        canvas.toBlob(
          (b) => (b ? resolve(b) : reject(new Error('PNG rasterisation failed.'))),
          'image/png',
        );
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('PNG rasterisation failed.'));
    };
    img.src = url;
  });
}
