import { patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankStation } from '../lib/formDefaults.js';
import { Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function StationsSection({ form, set, layers }) {
  const setTop = useFormSetter(set);
  const layerOpts = [{ value: '', label: 'Select platform…' }, ...layers];
  return (
    <Section
      id="stations"
      title="5 · Station buildings"
      hint="Rectangular footprints placed against a platform edge. Blank length/width = 40 × 10 m."
      count={form.stations.length}
      onAdd={() => setTop({ stations: [...form.stations, blankStation()] })}
      addLabel="+ Add station"
    >
      {form.stations.length === 0 && <Empty>No station buildings.</Empty>}
      {form.stations.map((s, i) => (
        <ItemCard
          key={i}
          title={s.name.trim() || `Station ${i + 1}`}
          onRemove={() => setTop({ stations: form.stations.filter((_, k) => k !== i) })}
        >
          <Grid>
            <Field label="Platform *">
              <Sel
                value={s.platform}
                onChange={(e) => setTop({ stations: patchAt(form.stations, i, { platform: e.target.value }) })}
                options={layerOpts}
              />
            </Field>
            <Field label="Length (m)" hint="Blank = 40">
              <Num
                value={s.length}
                placeholder="40.0"
                min="0"
                onChange={(e) => setTop({ stations: patchAt(form.stations, i, { length: e.target.value }) })}
              />
            </Field>
            <Field label="Width (m)" hint="Blank = 10">
              <Num
                value={s.width}
                placeholder="10.0"
                min="0"
                onChange={(e) => setTop({ stations: patchAt(form.stations, i, { width: e.target.value }) })}
              />
            </Field>
            <Field label="Side of platform">
              <Sel
                value={s.side}
                onChange={(e) => setTop({ stations: patchAt(form.stations, i, { side: e.target.value }) })}
                options={['LEFT', 'RIGHT']}
              />
            </Field>
            <Field label="Building name">
              <Text
                value={s.name}
                placeholder={i === 0 ? 'STATION BUILDING' : `STATION ${i + 1}`}
                onChange={(e) => setTop({ stations: patchAt(form.stations, i, { name: e.target.value }) })}
              />
            </Field>
            <Field label="Station chainage (KM)" hint="e.g. 125 (shown as KM: 125.000 below CH:0.00 KM)">
              <Text
                value={s.chainage ?? ''}
                placeholder="125"
                onChange={(e) => setTop({ stations: patchAt(form.stations, i, { chainage: e.target.value }) })}
              />
            </Field>
          </Grid>
        </ItemCard>
      ))}
    </Section>
  );
}
