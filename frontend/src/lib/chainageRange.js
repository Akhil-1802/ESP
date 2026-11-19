import { alignmentStartMetres } from './bridgePlacement.js';

/** Current survey extent, before yard trimming; unknown alignments have no range. */
export function getAlignmentChainageRange(form = {}) {
  if (form.mainLength == null || String(form.mainLength).trim() === '') return null;
  const length = Number(form.mainLength);
  const start = alignmentStartMetres(form);
  if (!Number.isFinite(length) || length <= 0 || !Number.isFinite(start)) return null;
  const end = start + length;
  return Number.isFinite(end) ? { start, end } : null;
}

export function formatRailwayChainage(metres) {
  if (!Number.isFinite(metres)) return '';
  // Round before splitting so 999.9996 m correctly becomes 1+000.
  const millimetres = Math.round(Math.abs(metres) * 1000);
  const km = Math.floor(millimetres / 1_000_000);
  const remainder = String((millimetres % 1_000_000) / 1000).split('.');
  const suffix = remainder[1] ? `.${remainder[1]}` : '';
  return `${metres < 0 && millimetres !== 0 ? '-' : ''}${km}+${remainder[0].padStart(3, '0')}${suffix}`;
}

export function chainageRangeReference(form = {}, units = 'metres') {
  const range = getAlignmentChainageRange(form);
  if (!range) {
    const length = Number(form.mainLength);
    return Number.isFinite(length) && length > 0
      ? 'Enter a valid alignment start chainage to see the range.'
      : 'Upload and select a KML alignment to see the chainage range.';
  }
  const { start, end } = range;
  const numericRange = units === 'kilometres'
    ? `${Number((start / 1000).toFixed(6))} – ${Number((end / 1000).toFixed(6))} km`
    : `${Number(start.toFixed(3))} – ${Number(end.toFixed(3))} m`;
  return `Alignment chainage range: ${formatRailwayChainage(start)} – ${formatRailwayChainage(end)} (${numericRange}).`;
}

/** Convert a local MAIN distance to an absolute value for centre-fill controls. */
export function absoluteChainageAtDistance(form, distance) {
  if (distance == null || String(distance).trim() === '') return '';
  const start = alignmentStartMetres(form);
  const local = Number(distance);
  return Number.isFinite(start) && Number.isFinite(local) ? formatRailwayChainage(start + local) : '';
}
