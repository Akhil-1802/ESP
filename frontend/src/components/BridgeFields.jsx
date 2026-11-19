import { ChainageRangeReference } from './ChainageRangeReference.jsx';
import { Field, Grid, Num, Sel, Text } from './fields.jsx';
import { BRIDGE_TYPE_OPTIONS } from '../lib/bridgePlacement.js';

export function BridgeFields({ form, bridge, onChange, buildingOptions = [] }) {
  const fixed = bridge.placementMode === 'fixed';
  return (
    <div className="space-y-3">
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
        <Field label="Placement method">
          <Sel value={bridge.placementMode || 'offset'} options={[
            { value: 'offset', label: 'Offset from station edge' },
            { value: 'fixed', label: 'Absolute chainage' },
          ]} onChange={(e) => onChange({ placementMode: e.target.value })} />
        </Field>
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
