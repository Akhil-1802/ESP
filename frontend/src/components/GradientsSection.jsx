import { useFormSetter } from '../lib/useFormSetter.js';
import { patchAt } from '../lib/formUtils.js';
import { blankGradient } from '../lib/formDefaults.js';
import { formatStartChainage, parseKmM } from '../lib/config.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function GradientsSection({ form, set }) {
  const setTop = useFormSetter(set);
  const gradients = form.gradients || [];

  // Station chainage from Station section if available
  const stationCenterCh = form.stations?.[0]?.chainage || form.stations?.[0]?.station_chainage || '125';

  return (
    <Section
      id="gradients"
      title="10 · Gradient Annotations"
      hint="Draws straight horizontal gradient annotation symbols on the railway alignment, using station center chainage as reference."
      count={gradients.length}
      onAdd={() => setTop({ gradients: [...gradients, blankGradient()] })}
      addLabel="+ Add Gradient"
    >
      {gradients.length === 0 && <Empty>No gradient annotations configured.</Empty>}

      {gradients.map((g, i) => {
        const parsed = parseKmM(g.chainage);
        const kmVal = g.km !== undefined && g.km !== null ? String(g.km) : parsed.km;
        const mVal = g.m !== undefined && g.m !== null ? String(g.m) : parsed.m;
        const displayCh = formatStartChainage(kmVal, mVal);
        const gradCh = g.chainage ?? (kmVal ? displayCh : '');
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
        } else if (g.chainage || kmVal) {
          cardTitle = `Gradient at ${g.chainage || displayCh}`;
        }

        return (
          <ItemCard
            key={i}
            title={cardTitle}
            onRemove={() => setTop({ gradients: gradients.filter((_, k) => k !== i) })}
          >
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
              {/* KM and M Option */}
              <div className="sm:col-span-5 grid grid-cols-2 gap-2">
                <div>
                  <span className="mb-1 block text-xs font-medium text-slate-700">
                    Gradient KM *
                  </span>
                  <Text
                    type="number"
                    min="0"
                    step="any"
                    value={kmVal}
                    placeholder="e.g. 70"
                    onChange={(e) => {
                      const newKm = e.target.value;
                      const newCh = formatStartChainage(newKm, mVal);
                      setTop({ gradients: patchAt(gradients, i, { km: newKm, m: mVal, chainage: newCh }) });
                    }}
                  />
                </div>
                <div>
                  <span className="mb-1 block text-xs font-medium text-slate-700">
                    M (optional)
                  </span>
                  <Text
                    type="number"
                    min="0"
                    step="any"
                    value={mVal}
                    placeholder="e.g. 400"
                    onChange={(e) => {
                      const newM = e.target.value;
                      const newCh = formatStartChainage(kmVal, newM);
                      setTop({ gradients: patchAt(gradients, i, { km: kmVal, m: newM, chainage: newCh }) });
                    }}
                  />
                </div>
              </div>

              <div className="sm:col-span-3">
                <Field label="Direction">
                  <Sel
                    value={g.direction || 'UP'}
                    onChange={(e) => setTop({ gradients: patchAt(gradients, i, { direction: e.target.value }) })}
                    options={['UP', 'DN']}
                  />
                </Field>
              </div>

              <div className="sm:col-span-4">
                <Field label="RL (Reduced Level)" hint="e.g. 102.45">
                  <Text
                    value={g.rl ?? ''}
                    placeholder="102.45"
                    onChange={(e) => setTop({ gradients: patchAt(gradients, i, { rl: e.target.value }) })}
                  />
                </Field>
              </div>
            </div>

            <div className="mt-1 flex flex-wrap items-center justify-between text-[11px] text-slate-500">
              <span>
                Chainage:{' '}
                <strong className="text-slate-700 font-semibold">
                  {displayCh !== '0.000' || kmVal ? `CH-${displayCh}` : 'e.g. 70 or 125+400'}
                </strong>
              </span>
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
