import { useFormSetter } from '../lib/useFormSetter.js';
import { patchAt } from '../lib/formUtils.js';
import { blankGradient } from '../lib/formDefaults.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function GradientsSection({ form, set }) {
  const setTop = useFormSetter(set);
  const gradients = form.gradients || [];

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
            const hasKm = String(gradCh).toUpperCase().includes('KM') || String(stationCenterCh).toUpperCase().includes('KM');
            const diff = gVal - sVal;
            const isRouteKmDiff = !hasKm && Math.abs(diff) <= 4.0 && gVal >= 10 && sVal >= 10 && (String(gradCh).includes('.') || String(stationCenterCh).includes('.'));
            const diffM = hasKm || isRouteKmDiff ? diff * 1000 : diff;
            offsetDisplay = `${diffM >= 0 ? '+' : ''}${diffM.toFixed(1)} m`;
          }
        }

        const leftVal = g.leftValue ?? g.left_gradient_value ?? '';
        const rightVal = g.rightValue ?? g.right_gradient_value ?? g.gradientValue ?? '';
        const leftDir = g.leftDirection || g.left_direction || 'STRAIGHT';
        const rightDir = g.rightDirection || g.right_direction || g.direction || 'RISE';

        let cardTitle = `Gradient ${i + 1}`;
        if (leftVal || rightVal) {
          const lPart = leftVal ? `Left: ${leftVal} (${leftDir})` : null;
          const rPart = rightVal ? `Right: ${rightVal} (${rightDir})` : null;
          cardTitle = [lPart, rPart].filter(Boolean).join(' | ');
        } else if (g.chainage) {
          cardTitle = `Gradient at ${g.chainage}`;
        }

        return (
          <ItemCard
            key={i}
            title={cardTitle}
            onRemove={() => setTop({ gradients: gradients.filter((_, k) => k !== i) })}
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Field label="Gradient chainage *" hint="e.g. 400.000 or 125.400">
                <Text
                  value={g.chainage ?? ''}
                  placeholder="400.000"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { chainage: e.target.value }) })}
                />
              </Field>

              <Field label="Direction">
                <Sel
                  value={g.direction || 'UP'}
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { direction: e.target.value }) })}
                  options={['UP', 'DN']}
                />
              </Field>

              <Field label="RL (Reduced Level)" hint="e.g. 102.45">
                <Text
                  value={g.rl ?? ''}
                  placeholder="102.45"
                  onChange={(e) => setTop({ gradients: patchAt(gradients, i, { rl: e.target.value }) })}
                />
              </Field>
            </div>

            {/* Two inputs: Left of Center and Right of Center */}
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 pt-2.5 border-t border-slate-200/80">
              {/* Left Side */}
              <div className="bg-slate-50/90 rounded border border-slate-200 p-2.5 space-y-2">
                <div className="text-[11px] font-semibold text-slate-800 flex items-center justify-between">
                  <span>◀ Left of Center</span>
                  <span className="text-[10px] text-slate-500 font-mono">5.0 m</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Gradient value" hint="e.g. 525 or 202">
                    <Text
                      value={leftVal}
                      placeholder="e.g. 525"
                      onChange={(e) => setTop({ gradients: patchAt(gradients, i, { leftValue: e.target.value }) })}
                    />
                  </Field>
                  <Field label="Profile">
                    <Sel
                      value={leftDir}
                      onChange={(e) => setTop({ gradients: patchAt(gradients, i, { leftDirection: e.target.value }) })}
                      options={['STRAIGHT', 'RISE', 'DOWN']}
                    />
                  </Field>
                </div>
              </div>

              {/* Right Side */}
              <div className="bg-slate-50/90 rounded border border-slate-200 p-2.5 space-y-2">
                <div className="text-[11px] font-semibold text-slate-800 flex items-center justify-between">
                  <span>▶ Right of Center</span>
                  <span className="text-[10px] text-slate-500 font-mono">5.0 m</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Gradient value" hint="e.g. 260 or 1278">
                    <Text
                      value={rightVal}
                      placeholder="e.g. 260"
                      onChange={(e) => setTop({ gradients: patchAt(gradients, i, { rightValue: e.target.value, gradientValue: e.target.value }) })}
                    />
                  </Field>
                  <Field label="Profile">
                    <Sel
                      value={rightDir}
                      onChange={(e) => setTop({ gradients: patchAt(gradients, i, { rightDirection: e.target.value, direction: e.target.value }) })}
                      options={['RISE', 'DOWN', 'STRAIGHT']}
                    />
                  </Field>
                </div>
              </div>
            </div>

            <div className="mt-2.5 rounded border border-blue-200 bg-blue-50/70 p-2 text-[11px] text-blue-800 space-y-1">
              <div className="font-semibold text-blue-900 flex items-center gap-1.5">
                <span>🚩 Station Flag Transverse Axis</span>
                <span className="font-mono text-blue-700 bg-blue-100/80 px-1 rounded">
                  {offsetDisplay ? `Offset: ${offsetDisplay} from Station C/L (${stationCenterCh})` : 'Aligned with Station Center'}
                </span>
              </div>
              <div className="text-[10px] text-blue-700">
                Positioned automatically along the station flag axis with fixed compact reference standard geometry (10.0 m).
              </div>
            </div>
          </ItemCard>
        );
      })}
    </Section>
  );
}
