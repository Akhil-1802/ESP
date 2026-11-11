import { patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { Check, Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function PlatformsSection({ form, set, tracks }) {
  const setTop = useFormSetter(set);
  const blank = () => ({
    track: '',
    track2: '',
    type: 'SIDE',
    side: 'LEFT',
    centerOnTrack: true,
    clearance: '',
    width: '',
    length: '',
    height: '',
    name: '',
    stairLength: '',
  });
  const trackOpts = [{ value: '', label: 'Select track…' }, ...tracks];
  return (
    <Section
      id="platforms"
      title="4 · Platforms"
      hint="SIDE sits next to one track; ISLAND sits between two. Blank width/length/clearance/height = 7.0 m / 550 m / 1.68 m / 0.84 m."
      count={form.platforms.length}
      onAdd={() => setTop({ platforms: [...form.platforms, blank()] })}
      addLabel="+ Add platform"
    >
      {form.platforms.length === 0 && <Empty>No platforms.</Empty>}
      {form.platforms.map((p, i) => {
        const pBadge = `${p.type || 'SIDE'} · ${p.track || 'Track'}`;
        const pSub = `${p.length || 550}m × ${p.width || 7}m`;
        return (
          <ItemCard
            key={i}
            title={`PLATFORM_${i + 1}${p.name.trim() ? ` · ${p.name.trim()}` : ''}`}
            badge={pBadge}
            subtitle={pSub}
            onRemove={() => setTop({ platforms: form.platforms.filter((_, k) => k !== i) })}
          >
          <Grid>
            <Field label="Track *">
              <Sel
                value={p.track}
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { track: e.target.value }) })}
                options={trackOpts}
              />
            </Field>
            <Field label="Type">
              <Sel
                value={p.type}
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { type: e.target.value }) })}
                options={['SIDE', 'ISLAND']}
              />
            </Field>
            {p.type === 'ISLAND' ? (
              <Field label="Second track *" hint="The other track it serves">
                <Sel
                  value={p.track2}
                  onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { track2: e.target.value }) })}
                  options={trackOpts}
                />
              </Field>
            ) : (
              <Field label="Side of track">
                <Sel
                  value={p.side}
                  onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { side: e.target.value }) })}
                  options={['LEFT', 'RIGHT']}
                />
              </Field>
            )}
            <Field label="Clearance (m)" hint="Track centre → near edge (blank = 1.68)">
              <Num
                value={p.clearance}
                placeholder="1.68"
                min="0"
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { clearance: e.target.value }) })}
              />
            </Field>
            <Field label="Width (m)" hint="Blank = 7.0">
              <Num
                value={p.width}
                placeholder="7.0"
                min="0"
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { width: e.target.value }) })}
              />
            </Field>
            <Field label="Length (m)" hint="Blank = 550">
              <Num
                value={p.length}
                placeholder="550.0"
                min="0"
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { length: e.target.value }) })}
              />
            </Field>
            <Field label="Height (m)" hint="Text label only (blank = 0.84)">
              <Num
                value={p.height}
                placeholder="0.84"
                min="0"
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { height: e.target.value }) })}
              />
            </Field>
            <Field label="Platform name">
              <Text
                value={p.name}
                placeholder="HIGH LEVEL PASSENGER PLATFORM"
                onChange={(e) => setTop({ platforms: patchAt(form.platforms, i, { name: e.target.value }) })}
              />
            </Field>
          </Grid>
          <div className="mt-3">
            <Check
              checked={p.centerOnTrack}
              onChange={(v) => setTop({ platforms: patchAt(form.platforms, i, { centerOnTrack: v }) })}
              label="Centre on track midpoint"
            />
          </div>
        </ItemCard>
      );
    })}
    </Section>
  );
}
