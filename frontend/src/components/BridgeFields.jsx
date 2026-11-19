import { useId } from 'react';
import { ChainageRangeReference } from './ChainageRangeReference.jsx';
import { Field, Grid, ItemCard, Num, Sel, Text } from './fields.jsx';
import { BRIDGE_TYPE_OPTIONS } from '../lib/bridgePlacement.js';

export function BridgeFields({ form, bridge, onChange, buildingOptions = [] }) {
  const groupName = useId();
  const fixed = bridge.placementMode === 'fixed';
  return (
    <div className="space-y-3">
      <div role="radiogroup" aria-label="Placement mode" className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs font-medium text-slate-700">
        <span className="text-slate-500">Placement mode:</span>
        {[
          ['offset', 'Offset from station edge (Recommended)'],
          ['fixed', 'Absolute chainage'],
        ].map(([mode, label]) => (
          <label key={mode} className="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" name={groupName} value={mode}
              checked={(bridge.placementMode || 'offset') === mode}
              onChange={() => onChange({ placementMode: mode })}
              className="accent-[var(--accent)]" />
            {label}
          </label>
        ))}
      </div>
      <Grid>
        <Field label="Bridge type *">
          <Sel value={bridge.bridgeType || 'PSC_SLAB'} options={BRIDGE_TYPE_OPTIONS}
            onChange={(e) => onChange({ bridgeType: e.target.value })} />
        </Field>
        {bridge.bridgeType === 'OTHER' && (
          <Field label="Bridge type/name *" hint="Up to 80 characters">
            <Text value={bridge.customType || ''} maxLength={80}
              onChange={(e) => onChange({ customType: e.target.value })} />
          </Field>
        )}
        {fixed ? (
          <Field label="Absolute chainage *" hint="MAIN datum: km+metres (12+850), or absolute metres (12850)">
            <Text value={bridge.chainage ?? ''} placeholder="12+850"
              onChange={(e) => onChange({ chainage: e.target.value })} />
            <ChainageRangeReference form={form} />
          </Field>
        ) : (
          <>
            <Field label="Reference station building *" hint="Uses the actual building edge along MAIN">
              <Sel value={bridge.stationBuildingIndex ?? ''} options={[
                { value: '', label: 'Select station building…' }, ...buildingOptions,
              ]} onChange={(e) => onChange({
                stationBuildingIndex: e.target.value === '' ? null : Number(e.target.value),
              })} />
            </Field>
            <Field label="Offset from station edge (m)" hint="Distance from building edge to bridge centreline">
              <Num value={bridge.offset ?? '50.0'} min="0"
                onChange={(e) => onChange({ offset: e.target.value })} />
            </Field>
            <Field label="Placement direction">
              <Sel value={bridge.direction || 'INCREASING'} options={[
                { value: 'INCREASING', label: 'Increasing chainage' },
                { value: 'DECREASING', label: 'Decreasing chainage' },
              ]} onChange={(e) => onChange({ direction: e.target.value })} />
            </Field>
          </>
        )}
        <Field label="Bridge width (m)" hint="Width along track; the shared symbol spans the yard">
          <Num value={bridge.width ?? '10.0'} min="0.01"
            onChange={(e) => onChange({ width: e.target.value })} />
        </Field>
      </Grid>
      {!fixed && buildingOptions.length === 0 && (
        <p className="text-xs text-amber-700">Add a station building to use an edge offset, or choose absolute chainage.</p>
      )}
    </div>
  );
}

export function BridgeCard({ title, onRemove, bridge, ...fieldProps }) {
  const badge = bridge.placementMode === 'fixed'
    ? (String(bridge.chainage ?? '').trim() ? `CH ${bridge.chainage}` : 'Absolute chainage')
    : `Offset ${bridge.offset || 50}m (${bridge.direction || 'INCREASING'})`;
  return (
    <ItemCard title={title} subtitle={`Width: ${bridge.width || 10}m · MAIN_LINE`} badge={badge} onRemove={onRemove}>
      <BridgeFields bridge={bridge} {...fieldProps} />
    </ItemCard>
  );
}
