/** Shared bridge placement semantics for validation and live preview. */
export const BRIDGE_TYPE_OPTIONS = [
  { value: 'PSC_SLAB', label: 'PSC Slab' },
  { value: 'RCC_BOX', label: 'RCC Box' },
  { value: 'OTHER', label: 'Other' },
];

export function bridgeTypeLabel(bridge) {
  return bridge.bridgeType === 'OTHER'
    ? String(bridge.customType || '').trim().replace(/\s+/g, ' ')
    : ({ PSC_SLAB: 'PSC SLAB', RCC_BOX: 'RCC BOX' }[bridge.bridgeType || 'PSC_SLAB'] || '');
}

export function parseAbsoluteChainage(value) {
  const raw = String(value ?? '').trim().toUpperCase();
  const plus = raw.match(/^(-?\d+)\s*\+\s*(\d+(?:\.\d+)?)$/);
  let result;
  if (plus) {
    if (Number(plus[2]) >= 1000) return NaN;
    result = (plus[1].startsWith('-') ? -1 : 1) * (Math.abs(Number(plus[1])) * 1000 + Number(plus[2]));
  } else {
    const number = raw.match(/^([+-]?\d+(?:\.\d+)?)\s*(KM|M)?$/);
    if (!number) return NaN;
    result = Number(number[1]) * (number[2] === 'KM' ? 1000 : 1);
  }
  return Number.isFinite(result) ? result : NaN;
}

export function alignmentStartMetres(form) {
  if ((form.startKm != null && String(form.startKm).trim() !== '') ||
      (form.startM != null && String(form.startM).trim() !== '')) {
    return (String(form.startKm ?? 0).trim().startsWith('-') ? -1 : 1) *
      (Math.abs(Number(form.startKm || 0)) * 1000 + Math.abs(Number(form.startM || 0)));
  }
  const raw = String(form.startChainage || '0').trim();
  const value = parseAbsoluteChainage(raw);
  return /^[+-]?\d+$/.test(raw) && Math.abs(value) <= 50 ? value * 1000 : value;
}

export function resolveBridgeDistance(form, bridge, stationBounds = null) {
  if ((bridge.placementMode || 'offset') === 'fixed') {
    return parseAbsoluteChainage(bridge.chainage) - alignmentStartMetres(form);
  }
  if (!stationBounds) return NaN;
  const offset = Number(bridge.offset ?? 50);
  return bridge.direction === 'DECREASING'
    ? stationBounds.start - offset : stationBounds.end + offset;
}
