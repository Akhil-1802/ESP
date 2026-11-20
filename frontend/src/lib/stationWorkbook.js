import { blankStationMarker } from './formDefaults.js';

const normalize = (value) => String(value ?? '').trim().replace(/\s+/g, ' ').toLowerCase();

export function stationsFromRows(rows) {
  const headerIndex = rows.findIndex((row) => {
    const headers = row.map(normalize);
    return headers.includes('name of station') && headers.includes('location (km)');
  });
  if (headerIndex < 0) throw new Error('The first worksheet needs Name of station and Location (km) columns.');
  const headers = rows[headerIndex].map(normalize);
  const stations = [];
  rows.slice(headerIndex + 1).forEach((row, index) => {
    if (row.every((value) => !normalize(value))) return;
    const name = row[headers.indexOf('name of station')];
    const location = row[headers.indexOf('location (km)')];
    const km = Number(location);
    if (typeof name !== 'string' || !name.trim() || !/^\d+(\.\d+)?$/.test(String(location).trim()) || !Number.isSafeInteger(Math.round(km * 1e6))) {
      throw new Error(`Row ${headerIndex + index + 2} needs a station name and a non-negative location in kilometres.`);
    }
    const millimetres = Math.round(km * 1e6);
    stations.push({ ...blankStationMarker(), name: name.trim(), km: String(Math.floor(millimetres / 1e6)), m: String((millimetres % 1e6) / 1000) });
  });
  if (!stations.length) throw new Error('The worksheet has no station rows.');
  return stations;
}

export function mergeImportedStations(current, imported) {
  const stations = [...current];
  for (const station of imported) {
    const duplicate = stations.some((entry) =>
      normalize(entry.name) === normalize(station.name) &&
      (normalize(entry.km) || normalize(entry.m)) &&
      Math.round((Number(entry.km || 0) * 1000 + Number(entry.m || 0)) * 1000) === Number(station.km) * 1e6 + Math.round(Number(station.m) * 1000));
    if (duplicate) continue;
    const empty = stations.findIndex((entry, idx) => entry.name === blankStationMarker(idx + 1).name &&
      !normalize(entry.km) && !normalize(entry.m) && !normalize(entry.chainage) && entry.showFlag !== false);
    if (empty < 0) stations.push(station);
    else stations[empty] = station;
  }
  return stations;
}
