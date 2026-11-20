import { patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankCrossover } from '../lib/formDefaults.js';
import { getExtendedLoopEnds } from '../lib/config.js';
import { Empty, Field, Grid, ItemCard, Section, Sel, Text } from './fields.jsx';

export function CrossoversSection({ form, set, tracks, hasGenerated }) {
  const setTop = useFormSetter(set);
  const trackOpts = [{ value: '', label: 'Select…' }, ...tracks];

  const loopEnds = getExtendedLoopEnds(form);

  return (
    <Section
      id="crossovers"
      title="5 · Crossovers"
      hint="Only the START chainage is input — the second SRJ is derived (OL = TC·N + 2·A). Type AUTO to let the engine place it."
      count={form.crossovers.length}
      onAdd={() => setTop({ crossovers: [...form.crossovers, blankCrossover()] })}
      addLabel="+ Add crossover"
    >
      {!hasGenerated && (
        <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50/80 p-2.5 text-xs text-blue-900 shadow-2xs">
          <div className="flex items-start gap-2">
            <span className="text-sm select-none" aria-hidden="true">ℹ️</span>
            <div className="leading-snug">
              <span className="font-semibold">Crossover chainages:</span> Crossover chainages will be shown after you generate DXF once (chainages require backend calculation).
            </div>
          </div>
        </div>
      )}
      {form.crossovers.length === 0 && <Empty>No crossovers.</Empty>}
      {form.crossovers.map((x, i) => {
          const targetTrack = loopEnds[x.from] ? x.from : x.to;
          const ends = loopEnds[targetTrack];
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
                      ? `Defined ends of ${targetTrack} in metres.`
                      : 'First SRJ, or AUTO'
                  }
                >
                  <Text
                    value={x.chainage}
                    placeholder={ends ? `${ends.baseC1} or ${ends.baseC2} or AUTO` : 'chainage or AUTO'}
                    onChange={(e) => setChainage(e.target.value)}
                  />
                  {ends && (
                    <span className="mt-1 flex flex-wrap gap-1.5">
                      <button type="button" className={chipCls} onClick={() => setChainage(String(ends.baseC1))}>
                        Loop start {ends.baseC1}
                      </button>
                      <button type="button" className={chipCls} onClick={() => setChainage(String(ends.baseC2))}>
                        Loop end {ends.baseC2}
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
