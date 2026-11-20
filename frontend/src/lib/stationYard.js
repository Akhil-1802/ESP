const collections = ['loops', 'platforms', 'stations', 'crossovers', 'fobs', 'bridges', 'sidings', 'gradients'];
export const yardOwner = (row) => Number(row.stationIndex ?? row.station_index ?? 0);

// Resolve positional IDs from older forms before filtering or removing rows.
export function identifyCrossovers(rows) {
  const keys = rows.map((row, i) => row.crossoverKey || `legacy-xo-${i + 1}`);
  return rows.map((row, i) => {
    const legacy = /^C(\d+)$/i.exec(row.autoAnchor || '');
    const named = legacy ? rows.findIndex(other => other.id === row.autoAnchor) : -1;
    return { ...row, crossoverKey: keys[i], autoAnchor: legacy
      ? keys[named >= 0 ? named : Number(legacy[1]) - 1] ?? 'missing-anchor' : row.autoAnchor || '' };
  });
}

export function anchorIndex(rows, index) {
  const row = rows[index];
  if (!row.autoAnchor) return -1;
  const target = rows.findIndex((other, i) =>
    ((other.crossoverKey || `legacy-xo-${i + 1}`) === row.autoAnchor || (other.id || `C${i + 1}`) === row.autoAnchor) &&
    i < index && yardOwner(other) === yardOwner(row));
  return target;
}

// Platforms and buildings are referenced by their position in the full form.
// Translate those references whenever a subset becomes a standalone drawing.
function selectYards(form, keep, owner, preserveDisplayIds = false) {
  const result = { ...form };
  const platforms = new Map();
  const buildings = new Map();
  for (const key of collections) {
    result[key] = [];
    const rows = key === 'crossovers' ? identifyCrossovers(form[key] || []) : form[key] || [];
    rows.forEach((row, index) => {
      if (!keep(yardOwner(row))) return;
      const local = result[key].length;
      if (key === 'platforms') platforms.set(`PLATFORM_${index + 1}`, `PLATFORM_${local + 1}`);
      if (key === 'stations') buildings.set(index, local);
      const item = { ...row, stationIndex: owner(yardOwner(row)) };
      if (preserveDisplayIds && key === 'crossovers') item.displayId = row.id || `C${index + 1}`;
      if (key === 'loops' && !item.name?.trim()) item.name = `LOOP_${index + 1}`;
      result[key].push(item);
    });
  }
  const layer = (value) => platforms.get(value) ?? '';
  for (const building of result.stations) building.platform = layer(building.platform);
  for (const fob of result.fobs) {
    fob.platforms = (fob.platforms || []).map(layer);
    fob.arms = (fob.arms || []).map((arm) => ({ ...arm, platform: layer(arm.platform) }));
  }
  for (const bridge of result.bridges) {
    const index = bridge.stationBuildingIndex;
    bridge.stationBuildingIndex = index == null || index === '' ? null : buildings.get(Number(index)) ?? null;
  }
  return result;
}

export function stationYardForm(form, index) {
  const station = form.stationMarkers[index];
  const name = (station.name?.trim() || 'Station').replace(/[^\p{L}\p{N}_-]+/gu, '_');
  const base = (form.outputDxf?.trim() || 'ESP').replace(/\.dxf$/i, '').replace(/[\\/:*?"<>|]/g, '_');
  return {
    ...selectYards(form, (i) => i === index, () => 0, true),
    stationMarkers: [station], directKml: false, enableMainLineTrim: false,
    outputDxf: `${base}_${index + 1}_${name}.dxf`,
  };
}

export function removeYard(form, index) {
  return {
    ...selectYards(form, (i) => i !== index, (i) => i > index ? i - 1 : i),
    stationMarkers: form.stationMarkers.filter((_, i) => i !== index),
  };
}
