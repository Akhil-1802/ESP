import { patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankLine, blankMainLine } from '../lib/formDefaults.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function MainTracksSection({ form, set }) {
  const setTop = useFormSetter(set);

  const mainLineReferenceTracks = (index) => [
    'MAIN_LINE',
    ...(form.mainLines || []).slice(0, index).map((_, i) => `MAIN_LINE_${i + 1}`),
  ];

  const addMainLine = () => {
    const prevRef = form.mainLines && form.mainLines.length > 0
      ? `MAIN_LINE_${form.mainLines.length}`
      : 'MAIN_LINE';
    setTop({ mainLines: [...(form.mainLines || []), blankMainLine(prevRef)] });
  };

  const addAdditionalLine = () => {
    setTop({ additionalLines: [...(form.additionalLines || []), blankLine()] });
  };

  return (
    <Section
      id="main-tracks"
      title="2 · Continuous Main Track Alignments"
      hint="Continuous lines running across the entire track corridor. Station loops are configured per station below."
      count={(form.mainLines || []).length}
    >
      <div className="space-y-3">
        {/* Primary MAIN_LINE Direction */}
        <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-slate-700 block">Primary MAIN_LINE</span>
              <span className="text-[11px] text-slate-500 block">
                The uploaded KML provides the centreline geometry for MAIN_LINE
              </span>
            </div>
            <div className="w-28">
              <span className="mb-0.5 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                Direction
              </span>
              <Sel
                value={form.mainLineDirection || 'UP'}
                onChange={(e) => setTop({ mainLineDirection: e.target.value })}
                options={['UP', 'DN']}
              />
            </div>
          </div>
        </div>

        {/* Multi-tracking: Additional Continuous Main Lines */}
        <div className="space-y-2">
          <div className="flex items-center justify-between pt-1">
            <div>
              <h3 className="text-xs font-bold text-slate-700">Additional Main Lines (Multi-Tracking)</h3>
              <p className="text-[11px] text-slate-500">Continuous full-corridor tracks (e.g. 2nd / 3rd main line)</p>
            </div>
            <button
              type="button"
              onClick={addMainLine}
              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer shadow-sm"
            >
              + Add MAIN line
            </button>
          </div>

          {(form.mainLines || []).length === 0 ? (
            <Empty>Single MAIN_LINE layout (add a MAIN line above for double-track corridors).</Empty>
          ) : (
            (form.mainLines || []).map((line, i) => {
              const name = `MAIN_LINE_${i + 1}`;
              const availableRefs = mainLineReferenceTracks(i);
              const refBadge = `${line.referenceTrack || 'MAIN_LINE'} · ${line.spacing || 5.3}m`;
              const dirSub = line.direction || 'UP/DN';
              return (
                <ItemCard
                  key={i}
                  title={`${name} (Continuous)`}
                  badge={refBadge}
                  subtitle={dirSub}
                  onRemove={() => setTop({ mainLines: form.mainLines.filter((_, k) => k !== i) })}
                >
                  <Grid>
                    <Field label="Reference track">
                      <Sel
                        value={line.referenceTrack || 'MAIN_LINE'}
                        onChange={(e) => setTop({ mainLines: patchAt(form.mainLines, i, { referenceTrack: e.target.value }) })}
                        options={availableRefs}
                      />
                    </Field>
                    <Field label="Spacing (m)" hint="Centre-to-centre, ≥ 5.3">
                      <Num
                        value={line.spacing}
                        placeholder="5.3"
                        min="5.3"
                        onChange={(e) => setTop({ mainLines: patchAt(form.mainLines, i, { spacing: e.target.value }) })}
                      />
                    </Field>
                    <Field label="Side of reference track">
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
              );
            })
          )}
        </div>
      </div>
    </Section>
  );
}

