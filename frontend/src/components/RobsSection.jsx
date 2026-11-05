import { useFormSetter } from '../lib/useFormSetter.js';
import { patchAt } from '../lib/formUtils.js';
import { blankRob } from '../lib/formDefaults.js';
import { getPlatformBounds } from '../lib/config.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel } from './fields.jsx';

export function RobsSection({ form, set, tracks, layers }) {
  const setTop = useFormSetter(set);
  const robs = form.robs || [];

  return (
    <Section
      id="robs"
      title="8 · Road over bridges (ROB)"
      hint="Road Over Bridge crossing tracks with standard abutments and return wing walls. Position is calculated from selected platform start (- offset) or platform end (+ offset). Deck spans all yard tracks."
      count={robs.length}
      onAdd={() => setTop({ robs: [...robs, blankRob()] })}
      addLabel="+ Add ROB"
    >
      {robs.length === 0 && <Empty>No road over bridges configured.</Empty>}
      {layers.length === 0 && robs.length > 0 && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Define at least one platform above first — an ROB references a platform end.
        </p>
      )}

      {robs.map((rob, i) => {
        const platName = rob.platform || (layers.length ? layers[0] : 'PLATFORM_1');
        const bounds = getPlatformBounds(form, platName);
        const refEnd = (rob.referenceEnd || 'START').toUpperCase();
        const offsetNum = Number(rob.offset || 0);
        const widthNum = Number(rob.width || 10);

        let centerCh = null;
        let formulaText = '';
        let relCh = null;
        let relStr = '';
        if (bounds) {
          if (refEnd === 'START') {
            centerCh = bounds.start - offsetNum;
            formulaText = `${bounds.start.toFixed(2)} m - ${offsetNum.toFixed(2)} m = ${centerCh.toFixed(2)} m`;
          } else {
            centerCh = bounds.end + offsetNum;
            formulaText = `${bounds.end.toFixed(2)} m + ${offsetNum.toFixed(2)} m = ${centerCh.toFixed(2)} m`;
          }
          if (form.stations && form.stations.length > 0) {
            const stCenter = (bounds.start + bounds.end) / 2.0;
            relCh = centerCh - stCenter;
            relStr = relCh > 0 ? `+${relCh.toFixed(2)}` : relCh.toFixed(2);
          }
        }

        const startSpan = centerCh !== null ? centerCh - widthNum / 2 : null;
        const endSpan = centerCh !== null ? centerCh + widthNum / 2 : null;

        return (
          <ItemCard
            key={i}
            title={`ROB ${i + 1}`}
            onRemove={() => setTop({ robs: robs.filter((_, k) => k !== i) })}
          >
            <Grid>
              <Field label="Reference Platform *">
                <Sel
                  value={rob.platform || (layers.length ? layers[0] : 'PLATFORM_1')}
                  onChange={(e) =>
                    setTop({ robs: patchAt(robs, i, { platform: e.target.value }) })
                  }
                  options={layers.length ? layers : ['PLATFORM_1']}
                />
              </Field>

              <Field
                label="Platform End Selection *"
                hint={refEnd === 'START' ? 'Drawn at Start - Offset' : 'Drawn at End + Offset'}
              >
                <Sel
                  value={refEnd}
                  onChange={(e) =>
                    setTop({ robs: patchAt(robs, i, { referenceEnd: e.target.value }) })
                  }
                  options={[
                    { value: 'START', label: 'Platform Start (Start - Offset)' },
                    { value: 'END', label: 'Platform End (End + Offset)' },
                  ]}
                />
              </Field>

              {bounds && (
                <div className="col-span-full rounded-md bg-slate-100 px-3 py-1.5 text-xs text-slate-700 flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <strong>{bounds.platform} Bounds:</strong> Start = <strong>{bounds.start.toFixed(2)} m</strong>, End = <strong>{bounds.end.toFixed(2)} m</strong>
                    {relStr && (
                      <span className="ml-2 text-indigo-700 font-semibold">
                        · Station Rel. CH: {relStr} m
                      </span>
                    )}
                  </span>
                  <span className="text-slate-500">
                    Track: {bounds.track} · Length: {bounds.length.toFixed(1)} m
                  </span>
                </div>
              )}

              <Field
                label="Offset from Platform (m) *"
                hint={refEnd === 'START' ? 'Distance before platform start' : 'Distance after platform end'}
              >
                <Num
                  value={rob.offset ?? '50.0'}
                  onChange={(e) =>
                    setTop({ robs: patchAt(robs, i, { offset: e.target.value }) })
                  }
                  min="0"
                  placeholder="50.0"
                />
              </Field>

              <Field
                label="ROB Width (m) *"
                hint="Width along track (X-axis); spans all tracks"
              >
                <Num
                  value={rob.width ?? '10.0'}
                  onChange={(e) =>
                    setTop({ robs: patchAt(robs, i, { width: e.target.value }) })
                  }
                  min="1"
                  placeholder="10.0"
                />
              </Field>

              <Field label="Reference Track" hint="Track alignment to sample center & angle">
                <Sel
                  value={rob.referenceTrack || 'MAIN_LINE'}
                  onChange={(e) =>
                    setTop({ robs: patchAt(robs, i, { referenceTrack: e.target.value }) })
                  }
                  options={tracks.length ? tracks : ['MAIN_LINE']}
                />
              </Field>

              <Field
                label="Bridge Chainage Label (Optional)"
                hint={
                  centerCh !== null
                    ? `Default: BR.CH- ${relStr ? relStr : centerCh.toFixed(2)}`
                    : 'e.g. 7983.'
                }
              >
                <input
                  type="text"
                  value={rob.chainage ?? ''}
                  onChange={(e) =>
                    setTop({ robs: patchAt(robs, i, { chainage: e.target.value }) })
                  }
                  placeholder={
                    centerCh !== null
                      ? (relStr ? relStr : `${centerCh.toFixed(2)}`)
                      : '7983.'
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none transition-colors"
                />
              </Field>

              <div className="col-span-full">
                <span className="mb-1 block text-xs font-medium text-slate-600">
                  Included Tracks (Span) *
                </span>
                <span className="mb-2 block text-[11px] leading-snug text-slate-400">
                  Select which tracks the ROB spans over. Outer diagonal wings are drawn beyond the outermost selected tracks (+3.5m clearance).
                </span>
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                  <button
                    type="button"
                    onClick={() => setTop({ robs: patchAt(robs, i, { tracks: [] }) })}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      !rob.tracks || rob.tracks.length === 0
                        ? 'bg-slate-900 text-white shadow-xs'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    All Yard Tracks {!rob.tracks || rob.tracks.length === 0 ? '✓' : ''}
                  </button>
                  {tracks.map((t) => {
                    const selected = Array.isArray(rob.tracks) && rob.tracks.includes(t);
                    return (
                      <button
                        key={t}
                        type="button"
                        onClick={() => {
                          const curr = Array.isArray(rob.tracks) ? rob.tracks : [];
                          const next = selected ? curr.filter((x) => x !== t) : [...curr, t];
                          setTop({ robs: patchAt(robs, i, { tracks: next }) });
                        }}
                        className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                          selected
                            ? 'bg-emerald-600 text-white shadow-xs'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {t} {selected ? '✓' : ''}
                      </button>
                    );
                  })}
                </div>
              </div>

              {centerCh !== null && (
                <div className="col-span-full rounded-lg bg-emerald-50/70 border border-emerald-200/80 p-2.5 text-xs text-emerald-950">
                  <div className="font-semibold flex items-center justify-between">
                    <span>📍 Calculated ROB Placement:</span>
                    <span className="font-mono text-emerald-900 font-bold text-sm">
                      {centerCh.toFixed(2)} m
                    </span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-emerald-800">
                    <span>
                      <strong>Formula:</strong> {formulaText}
                    </span>
                    <span>
                      <strong>Deck Span:</strong> {startSpan.toFixed(2)} m – {endSpan.toFixed(2)} m
                    </span>
                    <span>
                      <strong>Deck Width:</strong> {widthNum.toFixed(1)} m
                    </span>
                    <span>
                      <strong>Bridge Chainage:</strong> BR.CH- {rob.chainage || centerCh.toFixed(2)}
                    </span>
                    <span>
                      <strong>Tracks Spanned:</strong> {!rob.tracks || rob.tracks.length === 0 ? 'All Yard Tracks' : rob.tracks.join(', ')}
                    </span>
                  </div>
                </div>
              )}

              {centerCh !== null && centerCh < 0 && (
                <p className="col-span-full rounded-md bg-rose-50 border border-rose-200 px-3 py-1.5 text-xs text-rose-800">
                  ⚠️ Calculated chainage ({centerCh.toFixed(2)} m) is negative! Please reduce the offset.
                </p>
              )}
            </Grid>
          </ItemCard>
        );
      })}
    </Section>
  );
}
