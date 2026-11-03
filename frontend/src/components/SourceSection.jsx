import { useState } from 'react';
import { fetchMainCenter } from '../lib/api.js';
import { calculateEndChainageFromKmM, fillCentredChainages, fillFobCentres, formatStartChainage } from '../lib/config.js';
import { isBlank } from '../lib/formUtils.js';
import { Field, Grid, Section, Text } from './fields.jsx';
import { useFormSetter } from '../lib/useFormSetter.js';

export function SourceSection({ form, set, onPreviewKml }) {
  const setTop = useFormSetter(set);
  const [centreBusy, setCentreBusy] = useState(false);
  const [centreMsg, setCentreMsg] = useState('');
  const file = form.kmlFile;

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
                    min="0"
                    step="any"
                    value={form.startKm ?? ''}
                    placeholder="e.g. 2 or 4"
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
