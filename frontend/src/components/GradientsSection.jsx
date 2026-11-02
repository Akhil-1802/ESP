import { useFormSetter } from '../lib/useFormSetter.js';
import { patchAt } from '../lib/formUtils.js';
import { blankGradient } from '../lib/formDefaults.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function GradientsSection({ form, set, tracks }) {
  const setTop = useFormSetter(set);
  const gradients = form.gradients || [];
  const trackOpts = tracks && tracks.length ? tracks : ['MAIN_LINE'];

  // Station chainage from Station section if available
  const stationCenterCh = form.stations?.[0]?.chainage || form.stations?.[0]?.station_chainage || '125';

  return (
    <Section
      id="gradients"
      title="9 · Gradient Annotations"
      hint="Draws straight horizontal gradient annotation symbols on the railway alignment, using station center chainage as reference."
      count={gradients.length}
      onAdd={() => setTop({ gradients: [...gradients, blankGradient()] })}
      addLabel="+ Add Gradient"
    >
      {gradients.length === 0 && <Empty>No gradient annotations configured.</Empty>}

      {gradients.map((g, i) => {
        const gradCh = g.chainage ?? '';
        let offsetDisplay = null;
        if (gradCh !== '') {
          const gVal = parseFloat(String(gradCh).replace(/[^\d.-]/g, ''));
          const sVal = parseFloat(String(stationCenterCh).replace(/[^\d.-]/g, ''));
          if (!isNaN(gVal) && !isNaN(sVal)) {
            const diff = gVal - sVal;
            const diffM = Math.abs(diff) < 50 ? diff * 1000 : diff;
            offsetDisplay = `${diffM >= 0 ? '+' : ''}${diffM.toFixed(1)} m`;
          }
        }

        return (
          <ItemCard
            key={i}
            title={g.gradientValue ? `${g.gradientValue} ${g.direction || 'UP'}` : (g.chainage ? `Gradient at ${g.chainage}` : `Gradient ${i + 1}`)}
            onRemove={() => setTop({ gradients: gradients.filter((_, k) => k !== i) })}
          >
            <Grid>
              <Field label="Track designation">
                <Sel
                  value={g.track || 'MAIN_LINE'}
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { track: e.target.value }) })}
                  options={trackOpts}
                />
              </Field>

              <Field label="Gradient chainage *" hint="e.g. 125.400 or 125+400">
                <Text
                  value={g.chainage ?? ''}
                  placeholder="125.400"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { chainage: e.target.value }) })}
                />
              </Field>

              <Field label="Gradient value" hint="e.g. 1 in 256">
                <Text
                  value={g.gradientValue ?? ''}
                  placeholder="1 in 256"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { gradientValue: e.target.value }) })}
                />
              </Field>

              <Field label="Direction">
                <Sel
                  value={g.direction || 'UP'}
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { direction: e.target.value }) })}
                  options={['UP', 'DOWN']}
                />
              </Field>

              <Field label="RL (Reduced Level)" hint="e.g. 102.45">
                <Text
                  value={g.rl ?? ''}
                  placeholder="102.45"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { rl: e.target.value }) })}
                />
              </Field>

              <Field label="Line length (m)" hint="Blank = 24.0">
                <Num
                  value={g.lineLength ?? '24.0'}
                  placeholder="24.0"
                  min="5"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { lineLength: e.target.value }) })}
                />
              </Field>

              <Field label="Transverse offset (m)" hint="Blank = 12.0">
                <Num
                  value={g.offset ?? '12.0'}
                  placeholder="12.0"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { offset: e.target.value }) })}
                />
              </Field>
            </Grid>

            {offsetDisplay && (
              <div className="mt-2.5 rounded border border-emerald-200 bg-emerald-50/70 p-2 text-[11px] text-emerald-800 space-y-1">
                <div className="font-semibold text-emerald-900 flex items-center gap-1.5">
                  <span>📐 Alignment Placement</span>
                  <span className="font-mono text-emerald-700 bg-emerald-100/80 px-1 rounded">
                    Offset: {offsetDisplay} from Station C/L (KM: {stationCenterCh})
                  </span>
                </div>
                <div className="text-[10px] text-emerald-700 flex flex-wrap gap-x-4">
                  <span><strong>Above Line:</strong> {g.gradientValue ? `${g.gradientValue} ` : ''}{g.direction || 'UP'} ({g.track || 'MAIN_LINE'})</span>
                  <span><strong>Below Line:</strong> CH: {g.chainage || '—'} {g.rl ? `| RL: ${g.rl} M` : ''}</span>
                </div>
              </div>
            )}
          </ItemCard>
        );
      })}
    </Section>
  );
}
