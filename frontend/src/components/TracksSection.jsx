import { useState } from 'react';
import { fetchMainCenter } from '../lib/api.js';
import { patchAt, fmt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankLoop, blankLine, blankMainLine } from '../lib/formDefaults.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function TracksSection({ form, set }) {
  const setTop = useFormSetter(set);
  const [autoBusy, setAutoBusy] = useState(false);
  const [autoMsg, setAutoMsg] = useState('');

  const autoCentre = async (i) => {
    if (!form.kmlFile) {
      setAutoMsg('Upload the KML file first — the centre is read from your alignment.');
      return;
    }
    setAutoBusy(true);
    setAutoMsg('');
    try {
      const c = await fetchMainCenter({ kmlFile: form.kmlFile });
      setTop({
        mainLength: c.main_length_m,
        mainCenter: c.main_center_m,
        loops: patchAt(form.loops, i, { c1: fmt(c.default_c1_m), c2: fmt(c.default_c2_m) }),
      });
      const name = (form.loops[i].name || '').trim() || `LOOP_${i + 1}`;
      setAutoMsg(`Auto-centred ${name}: C1 ${c.default_c1_m} m, C2 ${c.default_c2_m} m (MAIN centre ${c.main_center_m} m).`);
    } catch (err) {
      setAutoMsg(err.message);
    } finally {
      setAutoBusy(false);
    }
  };

  const loopReferenceTracks = (index) => [
    'MAIN_LINE',
    ...(form.mainLines || []).map((_, i) => `MAIN_LINE_${i + 1}`),
    ...(form.loops || []).slice(0, index).map((loop, i) => loop.name.trim() || `LOOP_${i + 1}`),
  ];

  return (
    <Section
      id="tracks"
      title="2 · MAIN lines, loops & additional lines"
      hint="Loops are bounded parallel lines (C1 → C2). Blank spacing = 5.3 m, blank turnout = 1:12, blank distance = 750 m. Leave C1+C2 blank (or Auto-centre) for a 750 m loop centred on MAIN — the centre is read from your KML."
      count={form.mainLines.length + form.loops.length}
      onAdd={() => setTop({ loops: [...form.loops, blankLoop()] })}
      addLabel="+ Add loop"
    >
      {autoMsg && (
        <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800">{autoMsg}</p>
      )}
      <div className="flex items-center gap-2 pt-1">
        <h3 className="text-sm font-semibold text-slate-700">MAIN lines</h3>
        <button
          type="button"
          onClick={() => setTop({ mainLines: [...(form.mainLines || []), blankMainLine()] })}
          className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          + Add MAIN line
        </button>
      </div>
      {form.mainLines.length === 0 ? (
        <Empty>One MAIN_LINE is used by default and is marked UP/DN.</Empty>
      ) : (
        <>
          <p className="text-[11px] leading-snug text-slate-500">
            With additional MAIN lines, choose the running direction for every MAIN line. Defaults are MAIN_LINE = UP and added lines = DN.
          </p>
          <ItemCard title="MAIN_LINE">
            <Grid>
              <Field label="Direction">
                <Sel
                  value={form.mainLineDirection || 'UP'}
                  onChange={(e) => setTop({ mainLineDirection: e.target.value })}
                  options={['UP', 'DN']}
                />
              </Field>
            </Grid>
          </ItemCard>
          {form.mainLines.map((line, i) => (
            <ItemCard
              key={i}
              title={`MAIN_LINE_${i + 1}`}
              onRemove={() => setTop({ mainLines: form.mainLines.filter((_, k) => k !== i) })}
            >
              <Grid>
                <Field label="Spacing from MAIN_LINE (m)" hint="Blank = 5.3">
                  <Num
                    value={line.spacing}
                    placeholder="5.3"
                    min="5.3"
                    onChange={(e) => setTop({ mainLines: patchAt(form.mainLines, i, { spacing: e.target.value }) })}
                  />
                </Field>
                <Field label="Side of MAIN_LINE">
                  <Sel
                    value={line.side}
                    onChange={(e) => setTop({ mainLines: patchAt(form.mainLines, i, { side: e.target.value }) })}
                    options={['LEFT', 'RIGHT']}
                  />
                </Field>
                <Field label="Direction">
                  <Sel
                    value={line.direction || 'DN'}
                    onChange={(e) => setTop({ mainLines: patchAt(form.mainLines, i, { direction: e.target.value }) })}
                    options={['UP', 'DN']}
                  />
                </Field>
              </Grid>
            </ItemCard>
          ))}
        </>
      )}

      <h3 className="pt-1 text-sm font-semibold text-slate-700">Loops</h3>
      {form.loops.length === 0 && <Empty>No loops — add one, or skip for a MAIN-only layout.</Empty>}
      {form.loops.map((l, i) => (
        <ItemCard
          key={i}
          title={l.name.trim() || `LOOP_${i + 1}`}
          onRemove={() => setTop({ loops: form.loops.filter((_, k) => k !== i) })}
        >
          <Grid>
            <Field label="Name" hint="Unique track name">
              <Text
                value={l.name}
                placeholder={`LOOP_${i + 1}`}
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { name: e.target.value }) })}
              />
            </Field>
            <Field label="Side of Referenced Track">
              <Sel
                value={l.side}
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { side: e.target.value }) })}
                options={['LEFT', 'RIGHT']}
              />
            </Field>
            <Field label="Reference track" hint="This loop offsets from the selected track">
              <Sel
                value={l.referenceTrack || 'MAIN_LINE'}
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { referenceTrack: e.target.value }) })}
                options={loopReferenceTracks(i)}
              />
            </Field>
            <Field label="Spacing from Referenced Track (m) *" hint="Centre-to-centre, ≥ 5.3 (blank = 5.3)">
              <Num
                value={l.spacing}
                placeholder="5.3"
                min="5.3"
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { spacing: e.target.value }) })}
              />
            </Field>
            <Field label="C1 chainage (MAIN m) *" hint="First crossover point (blank C1+C2 = auto-centre)">
              <Num
                value={l.c1}
                placeholder="auto"
                min="0"
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { c1: e.target.value }) })}
              />
            </Field>
            <Field label="C2 chainage (MAIN m)" hint="Second point (blank = C1 + distance)">
              <Num
                value={l.c2}
                placeholder="auto"
                min="0"
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { c2: e.target.value }) })}
              />
            </Field>
            <Field label="Crossover distance (m)" hint="Used when C2 is blank (default 750)">
              <Num
                value={l.crossoverDistance}
                placeholder="750.0"
                min="0"
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { crossoverDistance: e.target.value }) })}
              />
            </Field>
            <Field label="Overrun before C1 (m)" hint="OVER RUN LINE past the turnout (blank = 120)">
              <Num
                value={l.extStart}
                placeholder="120.0"
                min="0"
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { extStart: e.target.value }) })}
              />
            </Field>
            <Field label="Overrun past C2 (m)" hint="OVER RUN LINE past the turnout (blank = 120)">
              <Num
                value={l.extEnd}
                placeholder="120.0"
                min="0"
                onChange={(e) => setTop({ loops: patchAt(form.loops, i, { extEnd: e.target.value }) })}
              />
            </Field>
          </Grid>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => autoCentre(i)}
              disabled={autoBusy}
              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
            >
              {autoBusy ? 'Locating…' : 'Auto-centre 750 m on MAIN'}
            </button>
            <span className="text-[11px] text-slate-400">Fills C1/C2 from your KML (centre ± 375 m).</span>
          </div>
        </ItemCard>
      ))}

      <div className="flex items-center gap-2 pt-1">
        <h3 className="text-sm font-semibold text-slate-700">Additional full-length lines</h3>
        <button
          type="button"
          onClick={() => setTop({ additionalLines: [...form.additionalLines, blankLine()] })}
          className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          + Add line
        </button>
      </div>
      {form.additionalLines.length === 0 && <Empty>None — proposed full-length parallels go here.</Empty>}
      {form.additionalLines.map((l, i) => (
        <ItemCard
          key={i}
          title={l.name.trim() || `PROPOSED_LINE_${i + 1}`}
          onRemove={() => setTop({ additionalLines: form.additionalLines.filter((_, k) => k !== i) })}
        >
          <Grid>
            <Field label="Name *">
              <Text
                value={l.name}
                placeholder={`PROPOSED_LINE_${i + 1}`}
                onChange={(e) => setTop({ additionalLines: patchAt(form.additionalLines, i, { name: e.target.value }) })}
              />
            </Field>
            <Field label="Spacing from Referenced Track(m)" hint="Blank = 5.3">
              <Num
                value={l.spacing}
                placeholder="5.3"
                min="5.3"
                onChange={(e) => setTop({ additionalLines: patchAt(form.additionalLines, i, { spacing: e.target.value }) })}
              />
            </Field>
            <Field label="Side of Referenced Track">
              <Sel
                value={l.side}
                onChange={(e) => setTop({ additionalLines: patchAt(form.additionalLines, i, { side: e.target.value }) })}
                options={['LEFT', 'RIGHT']}
              />
            </Field>
          </Grid>
        </ItemCard>
      ))}
    </Section>
  );
}
