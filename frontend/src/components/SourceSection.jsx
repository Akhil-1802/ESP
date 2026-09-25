import { useState } from 'react';
import { fetchMainCenter } from '../lib/api.js';
import { fillCentredChainages, fillFobCentres, fobsNeedingCentre, loopsNeedingCentre } from '../lib/config.js';
import { Field, Grid, Section, Text } from './fields.jsx';
import { useFormSetter } from '../lib/useFormSetter.js';

export function SourceSection({ form, set }) {
  const setTop = useFormSetter(set);
  const [centreBusy, setCentreBusy] = useState(false);
  const [centreMsg, setCentreMsg] = useState('');
  const file = form.kmlFile;

  const onFile = async (chosen) => {
    setTop({ kmlFile: chosen });
    setCentreMsg('');
    if (!chosen || (loopsNeedingCentre(form).length === 0 && fobsNeedingCentre(form).length === 0)) return;
    setCentreBusy(true);
    try {
      const c = await fetchMainCenter({ kmlFile: chosen });
      set((f) => ({
        ...fillFobCentres(fillCentredChainages(f, c), c),
        mainLength: c.main_length_m,
        mainCenter: c.main_center_m,
      }));
      setCentreMsg(
        `MAIN centre ${c.main_center_m} m — blank C1/C2 set to ${c.default_c1_m} / ${c.default_c2_m} m, blank FOB chainages to ${c.main_center_m} m.`,
      );
    } catch (err) {
      setCentreMsg(err.message);
    } finally {
      setCentreBusy(false);
    }
  };

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
              {centreBusy ? 'Reading MAIN centre from KML…' : centreMsg}
            </span>
          )}
        </Field>
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
