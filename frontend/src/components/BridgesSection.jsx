import { Section, Empty, ItemCard } from './fields.jsx';
import { blankBridge } from '../lib/formDefaults.js';
import { patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { BridgeFields } from './BridgeFields.jsx';

export function BridgesSection({ form, set }) {
  const setTop = useFormSetter(set);
  const bridges = form.bridges || [];
  const buildingOptions = (form.stations || []).map((s, i) => ({
    value: i, label: s.name || `Station building ${i + 1}`,
  }));
  return (
    <Section id="bridges" title="Bridges" count={bridges.length}
      onAdd={() => setTop({ bridges: [...bridges, blankBridge()] })} addLabel="+ Add Bridge">
      {bridges.length === 0 && <Empty>No bridges configured.</Empty>}
      {bridges.map((bridge, i) => (
        <ItemCard key={i} title={`Bridge ${i + 1}`}
          onRemove={() => setTop({ bridges: bridges.filter((_, k) => k !== i) })}>
          <BridgeFields form={form} bridge={bridge} buildingOptions={buildingOptions}
            onChange={(patch) => setTop({ bridges: patchAt(bridges, i, patch) })} />
        </ItemCard>
      ))}
    </Section>
  );
}
