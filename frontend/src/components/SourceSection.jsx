import { useState } from 'react';
import { fetchMainCenter } from '../lib/api.js';
import { calculateEndChainageFromKmM, fillCentredChainages, fillFobCentres, formatStartChainage } from '../lib/config.js';
import { blankStationMarker } from '../lib/formDefaults.js';
import { isBlank } from '../lib/formUtils.js';
import { Field, Grid, Section, Text } from './fields.jsx';
import { useFormSetter } from '../lib/useFormSetter.js';

export function SourceSection({ form, set, onPreviewKml }) {
  const setTop = useFormSetter(set);
  const [centreBusy, setCentreBusy] = useState(false);
  const [centreMsg, setCentreMsg] = useState('');
  const file = form.kmlFile;
  const stationMarkers = form.stationMarkers || [];

  const onStationCountChange = (val) => {
    const targetCount = Math.max(0, parseInt(val, 10) || 0);
    const current = [...(form.stationMarkers || [])];
    if (targetCount === current.length) return;
    if (targetCount < current.length) {
      setTop({ stationMarkers: current.slice(0, targetCount) });
    } else {
      const added = [];
      for (let i = current.length; i < targetCount; i++) {
        added.push(blankStationMarker(i + 1));
      }
      setTop({ stationMarkers: [...current, ...added] });
    }
  };

  const addStationMarker = () => {
    const current = form.stationMarkers || [];
    setTop({ stationMarkers: [...current, blankStationMarker(current.length + 1)] });
  };

  const updateStationMarker = (idx, patch) => {
    const current = [...(form.stationMarkers || [])];
    current[idx] = { ...current[idx], ...patch };
    setTop({ stationMarkers: current });
  };

  const removeStationMarker = (idx) => {
    const current = (form.stationMarkers || []).filter((_, i) => i !== idx);
    setTop({ stationMarkers: current });
  };

  const onFile = async (chosen) => {
    setTop({ kmlFile: chosen });
    setCentreMsg('');
    if (!chosen) {
      set((f) => ({ ...f, kmlFile: null, mainLength: null, mainCenter: null }));
      return;
    }
    setCentreBusy(true);
    try {
      const c = await fetchMainCenter({ kmlFile: chosen });
      set((f) => ({
        ...fillFobCentres(fillCentredChainages(f, c), c),
        mainLength: c.main_length_m,
        mainCenter: c.main_center_m,
      }));
      setCentreMsg(
        `KML track length: ${c.main_length_m.toFixed(2)} m (MAIN centre: ${c.main_center_m.toFixed(2)} m)`,
      );
    } catch (err) {
      setCentreMsg(err.message);
    } finally {
      setCentreBusy(false);
    }
  };

  const calculatedEnd = calculateEndChainageFromKmM(form.startKm, form.startM, form.mainLength);
  const startDisplay = formatStartChainage(form.startKm, form.startM);

  return (
    <Section
      id="source"
      title="1 · Source & output"
      hint="The uploaded KML is always the alignment source. The output name is used for the downloaded DXF."
    >
      <Grid>
        <Field span2 label="KML alignment file *" hint={file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'Required, e.g. ESP.kml'}>
          <input
            type="file"
            accept=".kml"
            onChange={(e) => onFile(e.target.files[0] || null)}
            className="w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700"
          />
          {(centreBusy || centreMsg) && (
            <span className="mt-0.5 block text-[11px] leading-snug text-sky-700">
              {centreBusy ? 'Reading track geometry from KML…' : centreMsg}
            </span>
          )}
          {file && onPreviewKml && (
            <div className="mt-2.5">
              <button
                type="button"
                onClick={onPreviewKml}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors cursor-pointer"
              >
                <span>👁️ View KML Track with Chainages</span>
              </button>
            </div>
          )}
        </Field>
        {/* Alignment Reference Chainages Card */}
        <div className="col-span-full rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-1">
            <span className="text-xs font-semibold text-slate-700">Track Reference Chainages</span>
            {form.mainLength != null && (
              <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200/60 rounded px-2 py-0.5">
                KML Track Length: {form.mainLength.toFixed(2)} m
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
            {/* Start Reference Chainage */}
            <div>
              <span className="mb-1 block text-xs font-medium text-slate-700">
                Start reference chainage *
              </span>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                    KM
                  </span>
                  <Text
                    type="number"
                    step="any"
                    value={form.startKm ?? ''}
                    placeholder="e.g. -4 or 4"
                    onChange={(e) => setTop({ startKm: e.target.value })}
                  />
                </div>
                <div>
                  <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                    M (optional)
                  </span>
                  <Text
                    type="number"
                    min="0"
                    step="any"
                    value={form.startM ?? ''}
                    placeholder="e.g. 900 or empty"
                    onChange={(e) => setTop({ startM: e.target.value })}
                  />
                </div>
              </div>
              <span className="mt-1 block text-[11px] text-slate-500">
                Starts at:{' '}
                <strong className="text-slate-700 font-semibold">
                  {startDisplay || '0.000'}
                </strong>
              </span>
            </div>

            {/* End Chainage (Calculated) */}
            <div>
              <span className="mb-1 block text-xs font-medium text-slate-700">
                End chainage (calculated)
              </span>
              <div>
                <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                  Derived Target
                </span>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={
                    calculatedEnd ??
                    (form.mainLength != null ? 'Invalid start chainage' : '— (Upload KML to calculate)')
                  }
                  className="w-full rounded-lg border border-slate-300 bg-slate-100 px-2.5 py-1.5 text-xs font-semibold text-slate-800 cursor-not-allowed select-all"
                />
              </div>
              <span className="mt-1 block text-[11px] text-slate-500">
                {form.mainLength != null
                  ? `Formula: ${startDisplay || '0'} + ${form.mainLength.toFixed(2)} m`
                  : 'Awaiting KML alignment file'}
              </span>
            </div>
          </div>
        </div>

        {/* Stations along Alignment Card */}
        <div className="col-span-full rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs font-semibold text-slate-700 block">Stations along Alignment</span>
              <span className="text-[10px] text-slate-500 block">
                Mark station reference chainages along track alignment
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <label htmlFor="station-count-input" className="text-[11px] font-medium text-slate-600">
                  No. of stations:
                </label>
                <input
                  id="station-count-input"
                  type="number"
                  min="0"
                  value={stationMarkers.length}
                  onChange={(e) => onStationCountChange(e.target.value)}
                  className="w-14 rounded-md border border-slate-300 bg-white px-2 py-1 text-center text-xs font-semibold text-slate-800 shadow-2xs focus:border-emerald-500 focus:outline-hidden"
                />
              </div>
              <button
                type="button"
                onClick={addStationMarker}
                className="inline-flex items-center gap-1 rounded-md bg-emerald-600 hover:bg-emerald-500 px-2 py-1 text-[11px] font-semibold text-white shadow-2xs transition-colors cursor-pointer"
              >
                <span>+ Add</span>
              </button>
            </div>
          </div>

          {stationMarkers.length === 0 ? (
            <div className="rounded-md border border-dashed border-slate-300 bg-white/50 p-2.5 text-center text-[11px] text-slate-500">
              No alignment stations specified. Enter number of stations or click <strong>+ Add</strong> to place station marker lines along the track.
            </div>
          ) : (
            <div className="space-y-2.5">
              {stationMarkers.map((stn, idx) => {
                const hasKm = !isBlank(stn.km);
                const hasM = !isBlank(stn.m);
                const chDisplay = hasKm || hasM ? formatStartChainage(stn.km, stn.m) : null;

                return (
                  <div
                    key={idx}
                    className="rounded-lg border border-slate-200 bg-white p-2.5 space-y-2 shadow-2xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold text-slate-700">
                          Station #{idx + 1}
                        </span>
                        <label className="inline-flex items-center gap-1 cursor-pointer select-none text-[10px] text-slate-600 bg-slate-100 hover:bg-slate-200/80 px-1.5 py-0.5 rounded transition-colors">
                          <input
                            type="checkbox"
                            checked={stn.showFlag !== false}
                            onChange={(e) => updateStationMarker(idx, { showFlag: e.target.checked })}
                            className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 h-3 w-3"
                          />
                          <span>🚩 Station Flag</span>
                        </label>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeStationMarker(idx)}
                        className="text-[11px] font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded px-1.5 py-0.5 transition-colors cursor-pointer"
                        title="Remove this station"
                      >
                        ✕ Remove
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-start">
                      {/* Station Name */}
                      <div>
                        <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          Station Name *
                        </span>
                        <Text
                          value={stn.name ?? ''}
                          placeholder={`STATION ${idx + 1}`}
                          onChange={(e) => updateStationMarker(idx, { name: e.target.value })}
                        />
                      </div>

                      {/* Station Chainage KM */}
                      <div>
                        <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          KM *
                        </span>
                        <Text
                          type="number"
                          min="0"
                          step="any"
                          value={stn.km ?? ''}
                          placeholder="e.g. 2"
                          onChange={(e) => updateStationMarker(idx, { km: e.target.value })}
                        />
                      </div>

                      {/* Station Chainage M (optional) */}
                      <div>
                        <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          M (optional)
                        </span>
                        <Text
                          type="number"
                          min="0"
                          step="any"
                          value={stn.m ?? ''}
                          placeholder="e.g. 400 or empty"
                          onChange={(e) => updateStationMarker(idx, { m: e.target.value })}
                        />
                      </div>
                    </div>

                    {/* Station Summary / Placement Badge */}
                    <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-500 pt-0.5">
                      <span>
                        Placement:{' '}
                        <strong className="text-slate-700 font-semibold">
                          {chDisplay ? `CH-${chDisplay}` : 'Awaiting chainage'}
                        </strong>
                        {stn.showFlag !== false && (
                          <span className="ml-1.5 text-rose-600 font-medium text-[10px]">🚩 Flag enabled</span>
                        )}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        Visible in KML alignment view until loops are added
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <Field label="Output DXF name" hint="Used for the download (default ESP_frontend.dxf)">
          <Text
            value={form.outputDxf}
            placeholder="ESP_frontend.dxf"
            onChange={(e) => setTop({ outputDxf: e.target.value })}
          />
        </Field>
        <Field label="Track source layer" hint="Layer of MAIN in the source (KML converts to MAIN_TRACK)">
          <Text
            value={form.trackSourceLayer}
            placeholder="MAIN_TRACK"
            onChange={(e) => setTop({ trackSourceLayer: e.target.value })}
          />
        </Field>
      </Grid>
    </Section>
  );
}
