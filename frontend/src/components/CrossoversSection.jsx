import { patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankCrossover } from '../lib/formDefaults.js';
import { getExtendedLoopEnds } from '../lib/config.js';
import { Empty, Field, Grid, ItemCard, Section, Sel, Text } from './fields.jsx';

export function CrossoversSection({ form, set, tracks }) {
  const setTop = useFormSetter(set);
  const trackOpts = [{ value: '', label: 'Select…' }, ...tracks];
  const isDefault = form.crossoverMode === 'default';

  const loopEnds = getExtendedLoopEnds(form);

  return (
    <Section
      id="crossovers"
      title="5 · Crossovers"
      hint="Only the START chainage is input — the second SRJ is derived (OL = TC·N + 2·A). Type AUTO to let the engine place it, or use the DEFAULT preset for the standard 4-crossover station layout."
      count={isDefault ? 0 : form.crossovers.length}
      onAdd={isDefault ? null : () => setTop({ crossovers: [...form.crossovers, blankCrossover()] })}
      addLabel="+ Add crossover"
    >
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="radio"
            checked={!isDefault}
            onChange={() => setTop({ crossoverMode: 'manual' })}
            className="h-4 w-4 accent-slate-900"
          />
          Manual list
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="radio"
            checked={isDefault}
            onChange={() => setTop({ crossoverMode: 'default' })}
            className="h-4 w-4 accent-slate-900"
          />
          DEFAULT preset(Only for Class B station)
        </label>
      </div>
      {isDefault && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Requires loops named <b>LOOP_1</b> and <b>LOOP_2</b> on opposite sides of MAIN_LINE. Turnout 1:12.
          Fixed standard layout: C1/C2 sit exactly at your loop chainages with ~98 m footprints —
          any overlap with a platform is rejected. For engine-placed crossovers that dodge
          platforms, use the Manual list with <b>AUTO</b> chainages instead.
        </p>
      )}
      {!isDefault && form.crossovers.length === 0 && <Empty>No crossovers.</Empty>}
      {!isDefault &&
        form.crossovers.map((x, i) => {
          const itemLoopEnds = getExtendedLoopEnds(form, i);
          const targetTrack = itemLoopEnds[x.from] ? x.from : (itemLoopEnds[x.to] ? x.to : null);
          const ends = targetTrack ? itemLoopEnds[targetTrack] : null;
          const setChainage = (v) => setTop({ crossovers: patchAt(form.crossovers, i, { chainage: v }) });
          const chipCls = 'rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 cursor-pointer';
          const chBadge = x.chainage ? `CH ${x.chainage}` : 'AUTO';
          const dirSubtitle = `${x.direction || 'NORMAL'} · ${x.turnout || '1:12'}`;
          return (
            <ItemCard
              key={i}
              title={`C${i + 1}${x.from && x.to ? ` · ${x.from} → ${x.to}` : ''}`}
              badge={chBadge}
              subtitle={dirSubtitle}
              onRemove={() => setTop({ crossovers: form.crossovers.filter((_, k) => k !== i) })}
            >
              <Grid>
                <Field label="From track *">
                  <Sel
                    value={x.from}
                    onChange={(e) => setTop({ crossovers: patchAt(form.crossovers, i, { from: e.target.value }) })}
                    options={trackOpts}
                  />
                </Field>
                <Field label="To track *">
                  <Sel
                    value={x.to}
                    onChange={(e) => setTop({ crossovers: patchAt(form.crossovers, i, { to: e.target.value }) })}
                    options={trackOpts}
                  />
                </Field>
                <Field
                  label="Start chainage (MAIN m) *"
                  hint={
                    ends
                      ? `First SRJ on ${x.from || targetTrack} — range [${ends.c1}, ${ends.c2}], or AUTO${
                          ends.isExtended ? ` (Extended from [${ends.baseC1}, ${ends.baseC2}])` : ''
                        }`
                      : 'First SRJ, or AUTO'
                  }
                >
                  <Text
                    value={x.chainage}
                    placeholder={ends ? `${ends.c1} or ${ends.c2} or AUTO` : 'chainage or AUTO'}
                    onChange={(e) => setChainage(e.target.value)}
                  />
                  {ends && (
                    <span className="mt-1 flex flex-wrap gap-1.5">
                      <button type="button" className={chipCls} onClick={() => setChainage(String(ends.c1))}>
                        Loop start {ends.c1}
                      </button>
                      <button type="button" className={chipCls} onClick={() => setChainage(String(ends.c2))}>
                        Loop end {ends.c2}
                      </button>
                      <button type="button" className={chipCls} onClick={() => setChainage('AUTO')}>
                        AUTO
                      </button>
                    </span>
                  )}
                </Field>
                <Field label="Direction">
                  <Sel
                    value={x.direction}
                    onChange={(e) => setTop({ crossovers: patchAt(form.crossovers, i, { direction: e.target.value }) })}
                    options={['FORWARD', 'REVERSE']}
                  />
                </Field>
                {String(x.chainage || '').trim().toUpperCase() === 'AUTO' && i > 0 && (
                  <Field label="AUTO anchor crossover" hint="13 m same direction; 54 m opposite direction">
                    <Sel
                      value={x.autoAnchor || ''}
                      onChange={(e) => setTop({ crossovers: patchAt(form.crossovers, i, { autoAnchor: e.target.value }) })}
                      options={[{ value: '', label: 'Previous crossover (default)' }, ...form.crossovers.slice(0, i).map((item, k) => ({ value: `C${k + 1}`, label: `C${k + 1} · ${item.from || '?'} → ${item.to || '?'}` }))]}
                    />
                  </Field>
                )}
                <Field label="Turnout" hint="Blank = 1:12">
                  <Sel
                    value={x.turnout}
                    onChange={(e) => setTop({ crossovers: patchAt(form.crossovers, i, { turnout: e.target.value }) })}
                    options={[{ value: '', label: 'Default (1:12)' }, '1:12', '1:8.5']}
                  />
                </Field>
              </Grid>
            </ItemCard>
          );
        })}
    </Section>
  );
}
