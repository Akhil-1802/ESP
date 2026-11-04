/** Minimal client for the ESP backend (POST /generate -> DXF download). */

export const API_BASE =
  (typeof import.meta !== 'undefined' &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE) ||
  'http://127.0.0.1:8000';

function downloadName(res, fallback) {
  const header = res.headers.get('content-disposition') || '';
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header);
  if (match) {
    try {
      return decodeURIComponent(match[1].replace(/"/g, '').trim());
    } catch {
      return match[1].replace(/"/g, '').trim();
    }
  }
  return fallback;
}

export async function generateDxf({ config, kmlFile, apiBase = API_BASE }) {  const body = new FormData();
  body.append(
    'config',
    new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' }),
    'inputconfig.json',
  );
  body.append('kml', kmlFile, kmlFile.name);

  let res;
  try {
    res = await fetch(`${apiBase}/generate`, { method: 'POST', body });
  } catch (err) {
    throw new Error(
      `Cannot reach the backend at ${apiBase} — is it running (python -m uvicorn backend.app:app --port 8000)? (${err.message})`,
    );
  }
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      detail = await res.text();
    }
    throw new Error(`Backend rejected the request (${res.status}): ${detail}`);
  }
  const blob = await res.blob();
  const fallback = String(config.output_dxf || 'ESP_output.dxf').split(/[\\/]/).pop();
  return { blob, filename: downloadName(res, fallback) };
}

export async function convertKmlDirect({ kmlFile, apiBase = API_BASE }) {
  const body = new FormData();
  body.append('kml', kmlFile, kmlFile.name);

  let res;
  try {
    res = await fetch(`${apiBase}/convert-kml-direct`, { method: 'POST', body });
  } catch (err) {
    throw new Error(
      `Cannot reach the backend at ${apiBase} — is it running (python -m uvicorn backend.app:app --port 8000)? (${err.message})`,
    );
  }
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      detail = await res.text();
    }
    throw new Error(`Direct KML conversion failed (${res.status}): ${detail}`);
  }
  const blob = await res.blob();
  const fallback = kmlFile.name.replace(/\.kml$/i, '') + '_direct.dxf';
  return { blob, filename: downloadName(res, fallback) };
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/**
 * Ask the backend for the MAIN midpoint from a KML file.
 * Returns { main_center_m, main_length_m, default_c1_m, default_c2_m }
 * (default extent = centre ± 375 m, the 750 m loop convention).
 */
export async function fetchMainCenter({ kmlFile, apiBase = API_BASE }) {
  const body = new FormData();
  body.append('kml', kmlFile, kmlFile.name);
  let res;
  try {
    res = await fetch(`${apiBase}/main-center`, { method: 'POST', body });
  } catch (err) {
    throw new Error(
      `Cannot reach the backend at ${apiBase} — is it running (python -m uvicorn backend.app:app --port 8000)? (${err.message})`,
    );
  }
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      detail = await res.text();
    }
    throw new Error(`Could not determine the MAIN centre (${res.status}): ${detail}`);
  }
  return res.json();
}
