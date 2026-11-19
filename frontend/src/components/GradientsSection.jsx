import { absoluteChainageAtDistance, formatRailwayChainage } from '../lib/chainageRange.js';
import { parseKmM } from '../lib/config.js';
import { blankGradient } from '../lib/formDefaults.js';
import { isBlank } from '../lib/formUtils.js';
import { ChainageRangeReference } from './ChainageRangeReference.jsx';
import { Field, Grid, ItemCard, Sel, Text, YardAddButton } from './fields.jsx';

function stationCentre(form, station) {
  if (!station) return absoluteChainageAtDistance(form, form.mainCenter);
  const { km, m } = isBlank(station.km) && isBlank(station.m)
    ? parseKmM(station.chainage) : station;
  if (isBlank(km) && isBlank(m)) return '';
  const sign = String(km ?? '').trim().startsWith('-') ? -1 : 1;
  return formatRailwayChainage(sign * (Math.abs(Number(km || 0)) * 1000 + Math.abs(Number(m || 0))));
}

export function GradientsSection({ form, set, stationIndex }) {
  const gradients = (form.gradients || []).filter(g => (g.stationIndex ?? g.station_index ?? 0) === stationIndex);
  const centre = stationCentre(form, form.stationMarkers?.[stationIndex]);
  const onAdd = () => set(f => ({
    ...f, gradients: [...(f.gradients || []), {
      ...blankGradient(), stationIndex, absoluteChainage: centre,
    }],
  }));
  const onUpdate = (gradient, patch) => set(f => ({
    ...f, gradients: f.gradients.map(g => g === gradient ? { ...g, ...patch } : g),
  }));
  const onRemove = gradient => set(f => ({
    ...f, gradients: f.gradients.filter(g => g !== gradient),
  }));

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-bold text-slate-800">Gradients ({gradients.length})</h3>
        <YardAddButton onClick={onAdd}>gradient</YardAddButton>
      </div>
      {!gradients.length && <p className="text-xs text-slate-500">No gradients configured for this yard.</p>}
      {gradients.map((g, i) => (
        <ItemCard key={i} title={`Gradient ${i + 1}`} onRemove={() => onRemove(g)}>
          <Grid>
            <Field label="Absolute chainage *" hint="Enter km+metres (12+850) or absolute metres (12850).">
              <Text value={g.absoluteChainage ?? ''} placeholder="12+850"
                onChange={e => onUpdate(g, { absoluteChainage: e.target.value })} />
              <ChainageRangeReference form={form} />
              {g.absoluteChainage == null && g.chainage && (
                <small>Current station-relative setting: {g.chainage}</small>
              )}
              {centre && <button type="button"
                className="mt-1 inline-flex w-fit items-center rounded-md border border-[var(--accent)] bg-[var(--surface)] px-2 py-0.5 text-[11px] leading-4 font-medium text-[var(--accent)] hover:bg-[var(--surface-soft)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] cursor-pointer"
                onClick={() => onUpdate(g, { absoluteChainage: centre })}>
                Use station centre ({centre})
              </button>}
            </Field>
            <Field label="Line direction">
              <Sel value={g.direction || 'UP'} options={['UP', 'DN']}
                onChange={e => onUpdate(g, { direction: e.target.value })} />
            </Field>
            <Field label="Reduced level (m)">
              <Text value={g.rl ?? ''} placeholder="102.45" onChange={e => onUpdate(g, { rl: e.target.value })} />
            </Field>
          </Grid>
          {['left', 'right'].map(side => (
            <Grid key={side}>
              <Field label={side === 'left' ? 'Left gradient value' : 'Right gradient value'}>
                <Text value={g[side + 'Value'] ?? g[side + '_gradient_value'] ?? (side === 'right' ? g.gradientValue : '') ?? ''}
                  placeholder="e.g. 525" onChange={e => onUpdate(g, { [side + 'Value']: e.target.value })} />
              </Field>
              <Field label={side === 'left' ? 'Left profile' : 'Right profile'}>
                <Sel value={g[side + 'Direction'] || g[side + '_direction'] || (side === 'left' ? 'STRAIGHT' : 'RISE')}
                  options={['STRAIGHT', 'RISE', 'DOWN']}
                  onChange={e => onUpdate(g, { [side + 'Direction']: e.target.value })} />
              </Field>
            </Grid>
          ))}
        </ItemCard>
      ))}
    </div>
  );
}
