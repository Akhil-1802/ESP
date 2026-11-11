import { useState } from 'react';
import { fetchMainCenter } from '../lib/api.js';
import { patchAt, fmt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankLoop } from '../lib/formDefaults.js';
import { getExtendedLoopEnds } from '../lib/config.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function TracksSection({ form, set }) {
  const setTop = useFormSetter(set);
  const [autoBusy, setAutoBusy] = useState(false);
  const [autoMsg, setAutoMsg] = useState('');
  const extendedExtents = getExtendedLoopEnds(form);

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

  const addLoop = () => {
    setTop({ loops: [...form.loops, blankLoop()] });
  };

  return (
    <Section
      id="tracks"
      title="3 · Loop lines"
      hint="Loops are bounded parallel lines (C1 → C2). Blank spacing = 5.3 m, blank turnout = 1:12, blank distance = 750 m. Leave C1+C2 blank for auto-centring."
      count={form.loops.length}
      onAdd={addLoop}
      addLabel="+ Add loop"
    >
      {autoMsg && (
        <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800">{autoMsg}</p>
      )}
      <div className="space-y-2">
        {form.loops.length === 0 && <Empty>No loops — add one, or skip for a MAIN-only layout.</Empty>}
        {form.loops.map((l, i) => {
          const loopName = l.name.trim() || `LOOP_${i + 1}`;
          const ext = extendedExtents[loopName];
          const c1 = l.c1 ?? '';
          const c2 = l.c2 ?? '';
          const hasExtent = c1 !== '' && c2 !== '' && !isNaN(Number(c1)) && !isNaN(Number(c2));
          const baseLen = hasExtent ? `${Math.abs(Number(c2) - Number(c1))}m` : '750m';
          const sideBadge = ext?.isExtended
            ? `${l.side || 'LEFT'} · ${ext.extendedLength}m (Ext)`
            : `${l.side || 'LEFT'} · ${baseLen}`;
          const chSub = ext?.isExtended
            ? `Running: [${ext.c1} → ${ext.c2}] · Spacing: ${l.spacing || 5.3}m`
            : (hasExtent ? `[${c1} → ${c2}] · Spacing: ${l.spacing || 5.3}m` : `Spacing: ${l.spacing || 5.3}m`);
          return (
            <ItemCard
              key={i}
              title={loopName}
              badge={sideBadge}
              subtitle={chSub}
              onRemove={() => setTop({ loops: form.loops.filter((_, k) => k !== i) })}
            >
              {ext?.isExtended && (
                <div className="mb-2.5 rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-xs text-sky-900 flex items-center justify-between">
                  <span>
                    Extended running line: <strong>{ext.c1}</strong> → <strong>{ext.c2}</strong> m
                  </span>
                  <span className="font-semibold text-sky-800 font-mono">
                    {ext.extendedLength} m
                  </span>
                </div>
              )}
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
                  value={l.overrunBeforeC1}
                  placeholder="120"
                  min="0"
                  onChange={(e) => setTop({ loops: patchAt(form.loops, i, { overrunBeforeC1: e.target.value }) })}
                />
              </Field>
              <Field label="Overrun after C2 (m)" hint="OVER RUN LINE past the turnout (blank = 120)">
                <Num
                  value={l.overrunAfterC2}
                  placeholder="120"
                  min="0"
                  onChange={(e) => setTop({ loops: patchAt(form.loops, i, { overrunAfterC2: e.target.value }) })}
                />
              </Field>
              <Field label="Turnout type" hint="Affects lead length and angle (default 1:12)">
                <Sel
                  value={l.turnout}
                  onChange={(e) => setTop({ loops: patchAt(form.loops, i, { turnout: e.target.value }) })}
                  options={['1:8.5', '1:12']}
                />
              </Field>
            </Grid>
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={() => autoCentre(i)}
                disabled={autoBusy}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50 cursor-pointer"
              >
                {autoBusy ? 'Locating…' : 'Auto-centre 750 m on MAIN'}
              </button>
              <span className="text-[11px] text-slate-400">Fills C1/C2 from your KML (centre ± 375 m).</span>
            </div>
          </ItemCard>
        );
      })}
      </div>
    </Section>
  );
}
