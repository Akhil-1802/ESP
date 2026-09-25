import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';
import { getTrackRange } from '../lib/config.js';
import { blankSiding } from '../lib/formDefaults.js';
import { patchAt } from '../lib/formUtils.js';

export function SidingsSection({ form, set, tracks }) {
  const setTop = (patch) => set((f) => ({ ...f, ...patch }));
  const trackOpts = [{ value: '', label: 'Select…' }, ...tracks];
  const sidings = form.sidings || [];
  const chipCls = 'rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 transition-colors';
  return (
    <Section
      id="sidings"
      title="7 · Sidings"
      hint="Dead-end sidings leaving a source track through a turnout, running out to a parallel spacing, holding the clear standing length (CSL), and terminating in a dead end (DE)."
      count={sidings.length}
      onAdd={() => {
        const defaultTrack = tracks.find((t) => t.startsWith('LOOP')) || tracks[0] || 'MAIN_LINE';
        setTop({ sidings: [...sidings, { ...blankSiding(), sourceTrack: defaultTrack }] });
      }}
      addLabel="+ Add siding"
    >
      {sidings.length === 0 && <Empty>No sidings added.</Empty>}
      {sidings.map((s, i) => {
        const range = getTrackRange(s.sourceTrack, form);
        return (
          <ItemCard
            key={i}
            title={`S${i + 1}${s.sourceTrack ? ` · ${s.sourceTrack}` : ''}${s.csl ? ` (CSL: ${s.csl}m)` : ''}`}
            onRemove={() => setTop({ sidings: sidings.filter((_, k) => k !== i) })}
          >
            <Grid>
              <Field label="Source track *">
                <Sel
                  value={s.sourceTrack}
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { sourceTrack: e.target.value }) })}
                  options={trackOpts}
                />
              </Field>
              <Field
                label={
                  <span className="flex items-center justify-between">
                    <span>Start chainage (m) *</span>
                    {range && (
                      <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-mono font-medium text-slate-600">
                        {range.label} m
                      </span>
                    )}
                  </span>
                }
                hint={range ? `Chainage range on ${s.sourceTrack}: ${range.label} m` : 'Select a track to see valid chainage range'}
              >
                <Text
                  value={s.chainage}
                  placeholder={range ? `e.g. ${range.label}` : 'e.g. 250'}
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { chainage: e.target.value }) })}
                />
                {range && Number.isFinite(range.c1) && (
                  <span className="mt-1 flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      className={chipCls}
                      onClick={() => setTop({ sidings: patchAt(sidings, i, { chainage: String(range.c1) }) })}
                    >
                      Start {range.c1}m
                    </button>
                    {Number.isFinite(range.c2) && (
                      <>
                        <button
                          type="button"
                          className={chipCls}
                          onClick={() =>
                            setTop({
                              sidings: patchAt(sidings, i, {
                                chainage: String(Math.round(((range.c1 + range.c2) / 2) * 10) / 10),
                              }),
                            })
                          }
                        >
                          Mid {Math.round(((range.c1 + range.c2) / 2) * 10) / 10}m
                        </button>
                        <button
                          type="button"
                          className={chipCls}
                          onClick={() => setTop({ sidings: patchAt(sidings, i, { chainage: String(range.c2) }) })}
                        >
                          End {range.c2}m
                        </button>
                      </>
                    )}
                  </span>
                )}
              </Field>
              <Field label="Side">
                <Sel
                  value={s.side || 'LEFT'}
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { side: e.target.value }) })}
                  options={['LEFT', 'RIGHT']}
                />
              </Field>
              <Field label="Direction">
                <Sel
                  value={s.direction || 'FORWARD'}
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { direction: e.target.value }) })}
                  options={['FORWARD', 'REVERSE']}
                />
              </Field>
              <Field label="Turnout (default 1:8.5)">
                <Sel
                  value={s.turnout || '1:8.5'}
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { turnout: e.target.value }) })}
                  options={['1:12', '1:8.5', '1:16']}
                />
              </Field>
              <Field label="CSL (Clear Standing Length, m)">
                <Num
                  value={s.csl ?? '120'}
                  placeholder="120"
                  min="10"
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { csl: e.target.value }) })}
                />
              </Field>
              <Field label="Spacing (m)">
                <Num
                  value={s.spacing ?? '5.3'}
                  placeholder="5.3"
                  min="5.3"
                  step="0.1"
                  onChange={(e) => setTop({ sidings: patchAt(sidings, i, { spacing: e.target.value }) })}
                />
              </Field>
            </Grid>
          </ItemCard>
        );
      })}
    </Section>
  );
}
