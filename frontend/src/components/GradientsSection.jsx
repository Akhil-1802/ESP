import { ChainageRangeReference } from './ChainageRangeReference.jsx';
import { useFormSetter } from '../lib/useFormSetter.js';
import { patchAt } from '../lib/formUtils.js';
import { blankGradient } from '../lib/formDefaults.js';
import { formatStartChainage, parseKmM } from '../lib/config.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function GradientsSection({ form, set }) {
  const setTop = useFormSetter(set);
  const gradients = form.gradients || [];

  // Derive station center reference chainage dynamically from stationMarkers, stations, or mainCenter
  const firstMarker = form.stationMarkers?.[0];
  const firstStn = form.stations?.[0];
  const activeStation = firstMarker || firstStn;
  const parsedStn = parseKmM(activeStation?.chainage || activeStation?.station_chainage);
  const hasKmStn = activeStation?.km != null && String(activeStation.km).trim() !== '';
  const hasMStn = activeStation?.m != null && String(activeStation.m).trim() !== '';
  const stnKmVal = hasKmStn ? String(activeStation.km) : (hasMStn ? '' : (parsedStn.km || ''));
  const stnMVal = hasMStn ? String(activeStation.m) : (parsedStn.m || '');
  const stationCenterCh = (hasKmStn || hasMStn)
    ? formatStartChainage(stnKmVal, stnMVal)
    : (activeStation?.chainage || activeStation?.station_chainage || (form.mainCenter != null && form.mainCenter !== '' ? String(form.mainCenter) : '0.000'));

  const parseChToMeters = (chStr) => {
    if (chStr == null || String(chStr).trim() === '') return null;
    const s = String(chStr).trim();
    if (s.includes('+')) {
      const parts = s.split('+');
      const k = parseFloat(parts[0]) || 0;
      const m = parseFloat(parts[1]) || 0;
      const sign = (k < 0 || parts[0].trim().startsWith('-')) ? -1 : 1;
      return sign * (Math.abs(k) * 1000 + Math.abs(m));
    }
    const clean = s.toUpperCase().replace(/^[A-Z\s:]+/, '').trim();
    if (clean.endsWith('KM')) {
      const num = parseFloat(clean.replace('KM', '').trim());
      return isNaN(num) ? null : num * 1000;
    }
    if (clean.endsWith('M')) {
      const num = parseFloat(clean.replace('M', '').trim());
      return isNaN(num) ? null : num;
    }
    const num = parseFloat(clean);
    if (!isNaN(num)) {
      if (clean.includes('.') && Math.abs(num) < 500) {
        return num * 1000;
      }
      return num;
    }
    return null;
  };

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
        const hasKm = kmVal !== undefined && kmVal !== null && String(kmVal).trim() !== '';
        const hasM = mVal !== undefined && mVal !== null && String(mVal).trim() !== '';
        const displayCh = (hasKm || hasM) ? formatStartChainage(kmVal, mVal) : '';
        const gradCh = (g.chainage !== undefined && g.chainage !== null && String(g.chainage).trim() !== '')
          ? String(g.chainage).trim()
          : displayCh;

        let offsetDisplay = null;
        if (gradCh !== '') {
          const gMeters = parseChToMeters(gradCh);
          const sMeters = parseChToMeters(stationCenterCh);
          if (gMeters !== null && sMeters !== null) {
            let diffM = gMeters - sMeters;
            if (gMeters < 10000 && sMeters >= 10000) {
              const sKmInM = Math.floor(sMeters / 1000) * 1000;
              diffM = (gMeters + sKmInM) - sMeters;
            } else if (sMeters < 10000 && gMeters >= 10000) {
              const gKmInM = Math.floor(gMeters / 1000) * 1000;
              diffM = gMeters - (sMeters + gKmInM);
            }
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
        } else if (gradCh || displayCh) {
          cardTitle = `Gradient at ${displayCh || gradCh}`;
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
                    KM (optional)
                  </span>
                  <Text
                    type="number"
                    min="0"
                    step="any"
                    value={kmVal}
                    placeholder={stnKmVal || 'e.g. 70'}
                    onChange={(e) => {
                      const newKm = e.target.value;
                      const newCh = formatStartChainage(newKm, mVal);
                      setTop({ gradients: patchAt(gradients, i, { km: newKm, m: mVal, chainage: newCh }) });
                    }}
                  />
                </div>
                <div>
                  <span className="mb-1 block text-xs font-medium text-slate-700">
                    Meters (M)
                  </span>
                  <Text
                    type="number"
                    min="0"
                    step="any"
                    value={mVal}
                    placeholder={stnMVal || 'e.g. 831'}
                    onChange={(e) => {
                      const newM = e.target.value;
                      const newCh = formatStartChainage(kmVal, newM);
                      setTop({ gradients: patchAt(gradients, i, { km: kmVal, m: newM, chainage: newCh }) });
                    }}
                  />
                </div>
                <ChainageRangeReference form={form} units="kilometres" className="col-span-2" />
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
                  {displayCh || gradCh ? `CH-${displayCh || gradCh}` : (stationCenterCh !== '0.000' ? `e.g. ${stationCenterCh}` : 'e.g. 831 M or 70+831')}
                </strong>
              </span>
              {stationCenterCh !== '0.000' && (
                <button
                  type="button"
                  onClick={() => {
                    setTop({ gradients: patchAt(gradients, i, { km: stnKmVal, m: stnMVal, chainage: stationCenterCh }) });
                  }}
                  className="text-[11px] font-medium text-emerald-700 hover:text-emerald-900 border border-emerald-300 bg-emerald-50 rounded px-2 py-0.5 cursor-pointer transition-colors"
                >
                  Fill with station center ({stationCenterCh})
                </button>
              )}
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
