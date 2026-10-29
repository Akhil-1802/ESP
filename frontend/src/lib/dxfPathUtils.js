/**
 * SVG vector path generation and DXF entity geometry utilities.
 */

export const esc = (s) =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

export const r3 = (n) => Math.round(Number(n) * 1000) / 1000;

export const finite = (n) => Number.isFinite(Number(n));

export function vertsOf(list) {
  return (list || [])
    .map((v) => [Number(v.x), Number(v.y), Number(v.bulge || 0)])
    .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
}

export function polylinePathD(vertices, closed) {
  if (!vertices || vertices.length === 0) return '';
  let d = '';
  for (let i = 0; i < vertices.length; i++) {
    const v1 = vertices[i];
    const x1 = Number(v1.x ?? v1[0]);
    const y1 = Number(v1.y ?? v1[1]);
    if (!Number.isFinite(x1) || !Number.isFinite(y1)) continue;

    if (d === '') {
      d += `M ${r3(x1)},${r3(y1)}`;
    }

    const isLast = i === vertices.length - 1;
    if (isLast && !closed) break;

    const nextIdx = isLast ? 0 : i + 1;
    const v2 = vertices[nextIdx];
    const x2 = Number(v2.x ?? v2[0]);
    const y2 = Number(v2.y ?? v2[1]);
    if (!Number.isFinite(x2) || !Number.isFinite(y2)) continue;

    const bulge = Number(v1.bulge ?? v1[2] ?? 0);
    if (bulge !== 0 && Number.isFinite(bulge)) {
      const dx = x2 - x1;
      const dy = y2 - y1;
      const chord = Math.sqrt(dx * dx + dy * dy);
      if (chord > 1e-6) {
        const radius = Math.abs((chord * (1 + bulge * bulge)) / (4 * bulge));
        const sweep = bulge > 0 ? 1 : 0;
        const large = Math.abs(bulge) > 1 ? 1 : 0;
        d += ` A ${r3(radius)},${r3(radius)} 0 ${large} ${sweep} ${r3(x2)},${r3(y2)}`;
        continue;
      }
    }
    d += ` L ${r3(x2)},${r3(y2)}`;
  }
  if (closed && vertices.length > 2) d += ' Z';
  return d;
}

export function splinePathD(points, closed) {
  if (!points || points.length < 2) return '';
  if (points.length === 2) {
    return `M ${r3(points[0][0])},${r3(points[0][1])} L ${r3(points[1][0])},${r3(points[1][1])}`;
  }
  let d = `M ${r3(points[0][0])},${r3(points[0][1])}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2 < points.length ? i + 2 : i + 1];

    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;

    d += ` C ${r3(cp1x)},${r3(cp1y)} ${r3(cp2x)},${r3(cp2y)} ${r3(p2[0])},${r3(p2[1])}`;
  }
  if (closed) d += ' Z';
  return d;
}

export function arcPathD(cx, cy, radius, a0deg, a1deg) {
  let a0 = (Number(a0deg) * Math.PI) / 180;
  let a1 = (Number(a1deg) * Math.PI) / 180;
  while (a1 < a0) a1 += Math.PI * 2;
  if (a1 - a0 < 1e-9) a1 = a0 + Math.PI * 2;

  const x0 = cx + radius * Math.cos(a0);
  const y0 = cy + radius * Math.sin(a0);
  const x1 = cx + radius * Math.cos(a1);
  const y1 = cy + radius * Math.sin(a1);
  const largeArc = a1 - a0 > Math.PI ? 1 : 0;

  return `M ${r3(x0)},${r3(y0)} A ${r3(radius)},${r3(radius)} 0 ${largeArc} 1 ${r3(x1)},${r3(y1)}`;
}

export function mtextPlain(raw) {
  return String(raw ?? '')
    .replace(/\\P/gi, '\n')
    .replace(/\\[^;]*;/g, '')
    .replace(/[{}]/g, '')
    .trim();
}

export function parseLeaders(raw) {
  const lines = String(raw || '').split(/\r?\n/);
  const leaders = [];
  let inLeader = false, layer = '0', color = 256;
  let verts = [], curX = null, curY = null;
  for (let i = 0; i < lines.length - 1; i += 2) {
    const code = lines[i].trim();
    const val = lines[i + 1].trim();
    if (code === '0') {
      if (inLeader && verts.length >= 2) {
        leaders.push({ type: 'LEADER', layer, color, vertices: verts });
      }
      inLeader = (val === 'LEADER');
      layer = '0';
      color = 256;
      verts = [];
      curX = null;
      curY = null;
      continue;
    }
    if (!inLeader) continue;
    if (code === '8') layer = val;
    if (code === '62') color = parseInt(val, 10);
    if (code === '10') curX = parseFloat(val);
    if (code === '20') curY = parseFloat(val);
    if (code === '30' && curX !== null && curY !== null) {
      verts.push({ x: curX, y: curY });
      curX = null;
      curY = null;
    }
  }
  if (inLeader && verts.length >= 2) {
    leaders.push({ type: 'LEADER', layer, color, vertices: verts });
  }
  return leaders;
}
