import { useState } from 'react';
import { fetchMainCenter } from '../lib/api.js';
import { FOB_MAX_SPAN_M, estimateFobSpan } from '../lib/config.js';
import { fmt, patchAt } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import { blankArm, blankFob } from '../lib/formDefaults.js';
import { Check, Empty, Field, Grid, ItemCard, Num, Section, Sel, Text } from './fields.jsx';

export function FobsSection({ form, set, tracks, layers }) {
  const setTop = useFormSetter(set);
  const [centreBusy, setCentreBusy] = useState(false);
  const [centreMsg, setCentreMsg] = useState('');

  const applyMainCentre = async (i) => {
    if (!form.kmlFile) {
      setCentreMsg('Upload the KML file first — the centre is read from your alignment.');
      return;
    }
    setCentreBusy(true);
    setCentreMsg('');
    try {
      const c = await fetchMainCenter({ kmlFile: form.kmlFile });
      setTop({
        fobs: patchAt(form.fobs, i, {
          chainage: fmt(c.main_center_m),
        }),
      });
      setCentreMsg(`FOB ${i + 1} chainage reset to track centre (${fmt(c.main_center_m)} m).`);
    } catch (err) {
      setCentreMsg(err.message);
    } finally {
      setCentreBusy(false);
    }
  };

  const togglePlatform = (i, layer) => {
    const fb = form.fobs[i];
    const has = fb.platforms.includes(layer);
    const nextPlats = has ? fb.platforms.filter((p) => p !== layer) : [...fb.platforms, layer];
    const nextArms = has
      ? (fb.arms || []).filter((a) => a.platform !== layer)
      : [...(fb.arms || []), { platform: layer, length: '', side: 'LEFT' }];
    setTop({
      fobs: patchAt(form.fobs, i, {
        platforms: nextPlats,
        arms: nextArms,
      }),
    });
  };

  return (
    <Section
      id="fobs"
      title="7 · Foot over bridges"
      hint="Basic deck only: span is auto-derived from the platform boundaries (no coordinates asked). Validated at 6.25 m clearance and 30 m maximum span — keep the connected platforms within it."
      count={form.fobs.length}
      onAdd={() => {
        const plats = layers.slice(0, 2);
        setTop({
          fobs: [
            ...form.fobs,
            {
              ...blankFob(),
              platforms: plats,
              arms: plats.map((p) => ({ platform: p, length: '', side: 'LEFT' })),
            },
          ],
        });
      }}
      addLabel="+ Add FOB"
    >
      {form.fobs.length === 0 && <Empty>No foot over bridges.</Empty>}
      {layers.length < 2 && form.fobs.length > 0 && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Define at least two platforms above first — an FOB must connect ≥ 2.
        </p>
      )}
      {centreMsg && (
        <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800">{centreMsg}</p>
      )}
      {form.fobs.map((fb, i) => {
        const isOffsetMode = fb.placementMode !== 'fixed';
        const fbBadge = isOffsetMode
          ? `Offset ${fb.offset || 40}m (${fb.direction || 'INCREASING'})`
          : (fb.chainage ? `CH ${fb.chainage}m` : 'Track-centre');
        const fbSub = `Width: ${fb.width || 3.0}m · ${fb.refTrack || 'MAIN_LINE'}`;
        return (
          <ItemCard
            key={i}
            title={`FOB ${i + 1}`}
            badge={fbBadge}
            subtitle={fbSub}
            onRemove={() => setTop({ fobs: form.fobs.filter((_, k) => k !== i) })}
          >
          <div className="mb-3 flex items-center gap-4 text-xs font-medium text-slate-700">
            <span className="text-slate-500">Placement mode:</span>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name={`fob-mode-${i}`}
                checked={isOffsetMode}
                onChange={() => setTop({ fobs: patchAt(form.fobs, i, { placementMode: 'offset' }) })}
                className="text-sky-600 focus:ring-sky-500"
              />
              <span>Offset from station edge (Recommended)</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name={`fob-mode-${i}`}
                checked={!isOffsetMode}
                onChange={() => {
                  const defaultCh = fb.chainage || (form.mainCenter ? fmt(form.mainCenter) : '');
                  setTop({ fobs: patchAt(form.fobs, i, { placementMode: 'fixed', chainage: defaultCh }) });
                }}
                className="text-sky-600 focus:ring-sky-500"
              />
              <span>Fixed chainage</span>
            </label>
          </div>

          <Grid>
            <Field label="Reference track *">
              <Sel
                value={fb.refTrack || 'MAIN_LINE'}
                onChange={(e) => setTop({ fobs: patchAt(form.fobs, i, { refTrack: e.target.value }) })}
                options={tracks.length ? tracks : ['MAIN_LINE']}
              />
            </Field>
            {isOffsetMode ? (
              <>
                <Field label="Offset from station edge (m)" hint="40 m to 60 m (blank = 40.0)">
                  <Num
                    value={fb.offset}
                    placeholder="40.0"
                    min="40"
                    max="60"
                    onChange={(e) => setTop({ fobs: patchAt(form.fobs, i, { offset: e.target.value }) })}
                  />
                </Field>
                <Field label="Placement direction">
                  <Sel
                    value={fb.direction || 'INCREASING'}
                    onChange={(e) => setTop({ fobs: patchAt(form.fobs, i, { direction: e.target.value }) })}
                    options={['INCREASING', 'DECREASING']}
                  />
                </Field>
              </>
            ) : (
              <Field label="FOB chainage (MAIN m)" hint="Default = track centre">
                <Text
                  value={fb.chainage}
                  placeholder={form.mainCenter ? fmt(form.mainCenter) : 'MAIN_CENTER'}
                  onChange={(e) => setTop({ fobs: patchAt(form.fobs, i, { chainage: e.target.value }) })}
                />
                <button
                  type="button"
                  onClick={() => applyMainCentre(i)}
                  disabled={centreBusy}
                  className="mt-1 rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50 cursor-pointer"
                >
                  {centreBusy ? 'Locating…' : 'Use track centre'}
                </button>
              </Field>
            )}
            <Field label="Deck width (m)" hint="Blank = 3.0">
              <Num
                value={fb.width}
                placeholder="3.0"
                min="0"
                onChange={(e) => setTop({ fobs: patchAt(form.fobs, i, { width: e.target.value }) })}
              />
            </Field>
          </Grid>
          <div className="mt-3">
            <span className="mb-1 block text-xs font-medium text-slate-600">
              Platforms to connect * (≥ 2)
            </span>
            <div className="flex flex-wrap gap-3">
              {layers.length === 0 && <span className="text-sm text-slate-400">No platforms defined yet.</span>}
              {layers.map((layer) => (
                <Check
                  key={layer}
                  checked={fb.platforms.includes(layer)}
                  onChange={() => togglePlatform(i, layer)}
                  label={layer}
                />
              ))}
            </div>
            {(() => {
              const est = estimateFobSpan(form, i);
              if (est === null) return null;
              return est > FOB_MAX_SPAN_M ? (
                <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                  Estimated span ~{est.toFixed(2)} m — over the {FOB_MAX_SPAN_M} m maximum. Narrow the
                  connected platforms (width/clearance) or the backend will reject this FOB.
                </p>
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  Estimated span ~{est.toFixed(2)} m (within the {FOB_MAX_SPAN_M} m maximum).
                </p>
              );
            })()}
          </div>
          <div className="mt-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Landing arms (optional, parallel to track)</span>
              <button
                type="button"
                onClick={() => {
                  const currentArms = fb.arms || [];
                  const usedPlats = new Set(currentArms.map((a) => a.platform).filter(Boolean));
                  const availablePlat =
                    (fb.platforms || []).find((p) => !usedPlats.has(p)) ||
                    fb.platforms[0] ||
                    layers[0] ||
                    '';
                  setTop({
                    fobs: patchAt(form.fobs, i, {
                      arms: [...currentArms, { platform: availablePlat, length: '', side: 'LEFT' }],
                    }),
                  });
                }}
                className="ml-auto rounded-md border border-slate-300 px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                + Add arm
              </button>
            </div>
            {(fb.arms || []).length === 0 && (
              <p className="text-xs text-slate-400">None — arms run deck-width wide from the deck edge over a platform.</p>
            )}
            {(fb.arms || []).map((arm, k) => (
              <div key={k} className="mb-2 grid grid-cols-1 gap-2 sm:grid-cols-4">
                <Sel
                  value={arm.platform}
                  onChange={(e) => {
                    const arms = (fb.arms || []).map((a, j) => (j === k ? { ...a, platform: e.target.value } : a));
                    setTop({ fobs: patchAt(form.fobs, i, { arms }) });
                  }}
                  options={[{ value: '', label: 'Platform…' }, ...fb.platforms]}
                />
                <Num
                  value={arm.length}
                  placeholder="16.999"
                  min="0"
                  onChange={(e) => {
                    const arms = (fb.arms || []).map((a, j) => (j === k ? { ...a, length: e.target.value } : a));
                    setTop({ fobs: patchAt(form.fobs, i, { arms }) });
                  }}
                />
                <Sel
                  value={arm.side}
                  onChange={(e) => {
                    const arms = (fb.arms || []).map((a, j) => (j === k ? { ...a, side: e.target.value } : a));
                    setTop({ fobs: patchAt(form.fobs, i, { arms }) });
                  }}
                  options={['LEFT', 'RIGHT']}
                />
                <button
                  type="button"
                  onClick={() => setTop({ fobs: patchAt(form.fobs, i, { arms: (fb.arms || []).filter((_, j) => j !== k) }) })}
                  className="rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </ItemCard>
      );
    })}
    </Section>
  );
}
