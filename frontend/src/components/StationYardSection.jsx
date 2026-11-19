import { GradientsSection } from './GradientsSection.jsx';
import { absoluteChainageAtDistance } from '../lib/chainageRange.js';
import { ChainageRangeReference } from './ChainageRangeReference.jsx';
import { BridgeCard } from './BridgeFields.jsx';
import { useState } from 'react';
import { fmt, isBlank } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import {
  FOB_MAX_SPAN_M,
  estimateFobSpan,
  formatStartChainage,
  getExtendedLoopEnds,
  getStationTrackDistance,
  getTrackRange,
  parseKmM,
} from '../lib/config.js';
import {
  blankArm,
  blankCrossover,
  blankFob,
  blankLoop,
  blankBridge,
  blankSiding,
  blankStation,
} from '../lib/formDefaults.js';
import { Check, Empty, Field, Grid, ItemCard, Num, Sel, Text, YardAddButton } from './fields.jsx';

export function StationYardSection({
  station,
  stationIndex,
  form,
  set,
  tracks,
  layers,
  hasGenerated,
  isAlignmentDatum = false,
  referenceDistance = null,
}) {
  const setTop = useFormSetter(set);
  const [open, setOpen] = useState(true);

  const stnName = station?.name?.trim() || `STATION ${stationIndex + 1}`;
  const parsedStn = parseKmM(station?.chainage);
  const hasKmStn = !isBlank(station?.km);
  const hasMStn = !isBlank(station?.m);
  const stnKmVal = hasKmStn ? String(station.km) : (hasMStn ? '0' : (parsedStn.km || '0'));
  const stnMVal = hasMStn ? String(station.m) : (parsedStn.m || '');
  const stnDisp = formatStartChainage(stnKmVal, stnMVal) || station?.chainage || '0.000';
  const stnDist = Number.isFinite(referenceDistance)
    ? referenceDistance
    : getStationTrackDistance(station, form.startKm, form.startM);

  const allTracks = tracks || ['MAIN_LINE'];
  const safeLayers = layers && layers.length > 0 ? layers : ['PLATFORM_1'];
  const trackOpts = [{ value: '', label: 'Select track…' }, ...allTracks];
  const layerOpts = [{ value: '', label: 'Select platform…' }, ...safeLayers];
  const chipCls =
    'rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer';

  // -------------------------------------------------------------
  // 1. Loops belonging to this station
  // -------------------------------------------------------------
  const stationLoops = (form.loops || []).filter(
    (l) => (l.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const loopReferenceTracks = (globalIdx) => [
    'MAIN_LINE',
    ...(form.mainLines || []).map((_, i) => `MAIN_LINE_${i + 1}`),
    ...(form.loops || []).slice(0, globalIdx).map((loop, i) => loop.name?.trim() || `LOOP_${i + 1}`),
  ];

  const addLoop = () => {
    const c1Val = Math.max(0, Math.round(stnDist - 375));
    const c2Val = Math.round(stnDist + 375);
    const existingCount = (form.loops || []).length;
    const newLoop = {
      ...blankLoop(),
      name: `LOOP_${existingCount + 1}`,
      side: stationLoops.length % 2 === 0 ? 'LEFT' : 'RIGHT',
      referenceTrack: 'MAIN_LINE',
      spacing: '',
      c1: fmt(c1Val),
      c2: fmt(c2Val),
      crossoverDistance: '',
      extStart: '',
      extEnd: '',
      stationIndex,
    };
    setTop({ loops: [...(form.loops || []), newLoop] });
  };

  const updateLoopAt = (loopObj, patch) => {
    const globalIdx = (form.loops || []).indexOf(loopObj);
    if (globalIdx < 0) return;
    const current = [...form.loops];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ loops: current });
  };

  const removeLoop = (loopObj) => {
    setTop({ loops: (form.loops || []).filter((l) => l !== loopObj) });
  };

  const autoCentreLoop = (loopObj) => {
    const c1Val = Math.max(0, Math.round(stnDist - 375));
    const c2Val = Math.round(stnDist + 375);
    updateLoopAt(loopObj, { c1: fmt(c1Val), c2: fmt(c2Val) });
  };

  // -------------------------------------------------------------
  // 2. Platforms belonging to this station
  // -------------------------------------------------------------
  const stationPlatforms = (form.platforms || []).filter(
    (p) => (p.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addPlatform = () => {
    const defaultTrack = stationLoops.length > 0 ? stationLoops[0].name || 'MAIN_LINE' : 'MAIN_LINE';
    const newPlatform = {
      track: defaultTrack,
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
      stationIndex,
    };
    setTop({ platforms: [...(form.platforms || []), newPlatform] });
  };

  const updatePlatformAt = (platObj, patch) => {
    const globalIdx = (form.platforms || []).indexOf(platObj);
    if (globalIdx < 0) return;
    const current = [...form.platforms];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ platforms: current });
  };

  const removePlatform = (platObj) => {
    setTop({ platforms: (form.platforms || []).filter((p) => p !== platObj) });
  };

  // -------------------------------------------------------------
  // 3. Crossovers belonging to this station
  // -------------------------------------------------------------
  const stationCrossovers = (form.crossovers || []).filter(
    (x) => (x.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addCrossover = () => {
    const defaultFrom = stationLoops[0]?.name || 'MAIN_LINE';
    const defaultTo = stationLoops[0]?.name ? 'MAIN_LINE' : (tracks[1] || 'LOOP_1');
    const newX = {
      ...blankCrossover(),
      from: defaultFrom,
      to: defaultTo,
      chainage: stationLoops[0]?.c1 || 'AUTO',
      direction: 'FORWARD',
      turnout: '',
      autoAnchor: '',
      stationIndex,
    };
    setTop({ crossovers: [...(form.crossovers || []), newX] });
  };

  const updateCrossoverAt = (xObj, patch) => {
    const globalIdx = (form.crossovers || []).indexOf(xObj);
    if (globalIdx < 0) return;
    const current = [...form.crossovers];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ crossovers: current });
  };

  const removeCrossover = (xObj) => {
    setTop({ crossovers: (form.crossovers || []).filter((x) => x !== xObj) });
  };

  // -------------------------------------------------------------
  // 3. Station Buildings belonging to this station
  // -------------------------------------------------------------
  const stationBuildings = (form.stations || []).filter(
    (s) => (s.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addStationBuilding = () => {
    const defaultPlatform = safeLayers[0] || 'PLATFORM_1';
    const parsedStn = parseKmM(station?.chainage);
    const hasKm = !isBlank(station?.km);
    const hasM = !isBlank(station?.m);
    const stnKm = hasKm ? String(station.km) : (hasM ? '0' : (parsedStn.km || '0'));
    const stnM = hasM ? String(station.m) : (parsedStn.m || '');
    const defaultCh = formatStartChainage(stnKm, stnM);
    const newBuilding = {
      ...blankStation(),
      platform: defaultPlatform,
      length: '',
      width: '',
      side: 'RIGHT',
      name: '',
      chainage: defaultCh,
      stationIndex,
    };
    setTop({ stations: [...(form.stations || []), newBuilding] });
  };

  const updateBuildingAt = (bldObj, patch) => {
    const globalIdx = (form.stations || []).indexOf(bldObj);
    if (globalIdx < 0) return;
    const current = [...form.stations];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ stations: current });
  };

  const removeBuilding = (bldObj) => {
    const removed = (form.stations || []).indexOf(bldObj);
    setTop({
      stations: (form.stations || []).filter((s) => s !== bldObj),
      bridges: (form.bridges || []).map((bridge) => ({ ...bridge,
        stationBuildingIndex: bridge.stationBuildingIndex == null || bridge.stationBuildingIndex === '' ? null
          : Number(bridge.stationBuildingIndex) === removed ? null
          : Number(bridge.stationBuildingIndex) > removed ? Number(bridge.stationBuildingIndex) - 1 : bridge.stationBuildingIndex,
      })),
    });
  };

  // -------------------------------------------------------------
  // 4. FOBs belonging to this station
  // -------------------------------------------------------------
  const stationFobs = (form.fobs || []).filter(
    (fb) => (fb.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addFob = () => {
    const defaultPlats = safeLayers.slice(0, 2);
    const newFob = {
      ...blankFob(),
      refTrack: 'MAIN_LINE',
      chainage: '',
      offset: '',
      direction: 'INCREASING',
      width: '',
      platforms: defaultPlats,
      arms: defaultPlats.map((p) => ({ platform: p, length: '', side: 'LEFT' })),
      stationIndex,
    };
    setTop({ fobs: [...(form.fobs || []), newFob] });
  };

  const updateFobAt = (fobObj, patch) => {
    const globalIdx = (form.fobs || []).indexOf(fobObj);
    if (globalIdx < 0) return;
    const current = [...form.fobs];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ fobs: current });
  };

  const removeFob = (fobObj) => {
    setTop({ fobs: (form.fobs || []).filter((fb) => fb !== fobObj) });
  };

  const toggleFobPlatform = (fobObj, layer) => {
    const has = (fobObj.platforms || []).includes(layer);
    const nextPlats = has
      ? (fobObj.platforms || []).filter((p) => p !== layer)
      : [...(fobObj.platforms || []), layer];
    const nextArms = has
      ? (fobObj.arms || []).filter((a) => a.platform !== layer)
      : [...(fobObj.arms || []), { platform: layer, length: '', side: 'LEFT' }];
    updateFobAt(fobObj, {
      platforms: nextPlats,
      arms: nextArms,
    });
  };

  const addArmToFob = (fobObj) => {
    const currentArms = fobObj.arms || [];
    const usedPlats = new Set(currentArms.map((a) => a.platform).filter(Boolean));
    const availablePlat =
      (fobObj.platforms || []).find((p) => !usedPlats.has(p)) ||
      (fobObj.platforms || [])[0] ||
      safeLayers[0] ||
      '';
    updateFobAt(fobObj, {
      arms: [...currentArms, { platform: availablePlat, length: '', side: 'LEFT' }],
    });
  };

  const updateArmAt = (fobObj, armIdx, patch) => {
    const arms = [...(fobObj.arms || [])];
    arms[armIdx] = { ...arms[armIdx], ...patch };
    updateFobAt(fobObj, { arms });
  };

  const removeArmFromFob = (fobObj, armIdx) => {
    updateFobAt(fobObj, {
      arms: (fobObj.arms || []).filter((_, idx) => idx !== armIdx),
    });
  };

  const applyStationFobCentre = (fobObj) => {
    const centerCh = stnDist ?? (form.mainCenter ? Number(form.mainCenter) : 0);
    updateFobAt(fobObj, {
      chainage: absoluteChainageAtDistance(form, centerCh),
    });
  };

  // -------------------------------------------------------------
  // 5. bridges belonging to this station
  // -------------------------------------------------------------
  const stationBridges = (form.bridges || []).filter(
    (r) => (r.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addBridge = () => {
    const buildingIndex = (form.stations || []).findIndex((s) =>
      (s.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex);
    setTop({ bridges: [...(form.bridges || []), {
      ...blankBridge(), stationIndex,
      stationBuildingIndex: buildingIndex >= 0 ? buildingIndex : null,
    }] });
  };

  const updateBridgeAt = (bridgeObj, patch) => {
    const globalIdx = (form.bridges || []).indexOf(bridgeObj);
    if (globalIdx < 0) return;
    const current = [...form.bridges];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ bridges: current });
  };

  const removeBridge = (bridgeObj) => {
    setTop({ bridges: (form.bridges || []).filter((r) => r !== bridgeObj) });
  };

  // -------------------------------------------------------------
  // 6. Sidings belonging to this station
  // -------------------------------------------------------------
  const stationSidings = (form.sidings || []).filter(
    (s) => (s.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addSiding = () => {
    const defaultTrack =
      stationLoops[0]?.name || allTracks.find((t) => t.startsWith('LOOP')) || allTracks[0] || 'MAIN_LINE';
    const newSiding = {
      ...blankSiding(),
      sourceTrack: defaultTrack,
      chainage: '',
      side: 'LEFT',
      direction: 'FORWARD',
      turnout: '1:8.5',
      spacing: '5.3',
      csl: '120.0',
      stationIndex,
    };
    setTop({ sidings: [...(form.sidings || []), newSiding] });
  };

  const updateSidingAt = (sidingObj, patch) => {
    const globalIdx = (form.sidings || []).indexOf(sidingObj);
    if (globalIdx < 0) return;
    const current = [...form.sidings];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ sidings: current });
  };

  const removeSiding = (sidingObj) => {
    setTop({ sidings: (form.sidings || []).filter((s) => s !== sidingObj) });
  };

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[0_2px_12px_rgba(25,49,104,0.04)] overflow-hidden transition-all">
      {/* Station Section Accordion Header */}
      <div
        className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-3.5 py-2.5 bg-[var(--surface-soft)] cursor-pointer select-none hover:bg-[rgba(50,95,244,0.04)] transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="text-[var(--accent)] transition-transform duration-200 inline-flex items-center justify-center w-4 h-4"
            style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}
          >
            <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
              <path d="M6 4l8 6-8 6V4z" />
            </svg>
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="rounded-md bg-gradient-to-r from-[var(--accent-start)] to-[var(--accent)] text-white font-bold text-[11px] px-2 py-0.5 shadow-2xs">
              {isAlignmentDatum ? 'Yard' : `Station ${stationIndex + 1}`}
            </span>
            <h2 className="text-sm font-bold text-[var(--text-primary)] truncate">
              {stnName}
            </h2>
            <span className="rounded-full bg-[rgba(50,95,244,0.08)] border border-[var(--border)] px-2 py-0.5 text-[10.5px] font-semibold text-[var(--accent)]">
              {isAlignmentDatum ? 'Reference' : 'Datum'}: {isAlignmentDatum ? 'Alignment centre' : stnDisp} (at {stnDist.toFixed(1)} m)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
          <span>{stationLoops.length} loops · {stationPlatforms.length} platforms · {stationCrossovers.length} crossovers · {stationBridges.length} bridges</span>
        </div>
      </div>

      {open && (
        <div className="p-3.5 space-y-4 text-xs bg-slate-50/30">
          {/* ========================================================= */}
          {/* 1. Loop Lines (same fields as TracksSection)              */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>🔄</span> Loops &amp; Additional Lines ({stationLoops.length})
              </h3>
              <YardAddButton onClick={addLoop}>loop</YardAddButton>
            </div>
            <p className="text-[10.5px] text-slate-500">
              Loops are bounded parallel lines (C1 → C2) referenced to {isAlignmentDatum ? 'the alignment centre' : stnName}.
            </p>

            {stationLoops.length === 0 ? (
              <Empty>No loops configured for this yard. Click "+ Add loop" to add one.</Empty>
            ) : (
              stationLoops.map((l, idx) => {
                const globalLoopIdx = (form.loops || []).indexOf(l);
                const defaultC1 = Math.max(0, Math.round(stnDist - 375));
                const defaultC2 = Math.round(stnDist + 375);
                const c1Val = l.c1 !== undefined && l.c1 !== null && l.c1 !== '' ? l.c1 : defaultC1;
                const c2Val = l.c2 !== undefined && l.c2 !== null && l.c2 !== '' ? l.c2 : defaultC2;
                const extentLen = Math.abs(Number(c2Val) - Number(c1Val)) || 750;
                return (
                  <ItemCard
                    key={idx}
                    title={`${l.name?.trim() || `LOOP_${globalLoopIdx + 1}`} · Referenced to ${isAlignmentDatum ? 'alignment centre' : stnName}`}
                    badge={`${l.side || 'LEFT'} · ${extentLen}m`}
                    subtitle={`[${c1Val} → ${c2Val}] · Spacing: ${l.spacing || 5.3}m`}
                    onRemove={() => removeLoop(l)}
                  >
                    <div className="mb-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
                      <div className="font-medium">
                        Centre: <span className="font-bold">{stnDist.toFixed(1)} m</span> · Extent: [<span className="font-bold">{c1Val}</span> to <span className="font-bold">{c2Val}</span>] m ({extentLen} m)
                      </div>
                      <button
                        type="button"
                        onClick={() => autoCentreLoop(l)}
                        className="mt-1 text-emerald-700 underline hover:text-emerald-900 font-medium cursor-pointer"
                      >
                        Reset to 750 m centre
                      </button>
                    </div>

                    <Grid>
                      <Field label="Name" hint="Unique track name">
                        <Text
                          value={l.name}
                          placeholder={`LOOP_${globalLoopIdx + 1}`}
                          onChange={(e) => updateLoopAt(l, { name: e.target.value })}
                        />
                      </Field>
                      <Field label="Side of Referenced Track">
                        <Sel
                          value={l.side}
                          onChange={(e) => updateLoopAt(l, { side: e.target.value })}
                          options={['LEFT', 'RIGHT']}
                        />
                      </Field>
                      <Field label="Reference track" hint="This loop offsets from the selected track">
                        <Sel
                          value={l.referenceTrack || 'MAIN_LINE'}
                          onChange={(e) => updateLoopAt(l, { referenceTrack: e.target.value })}
                          options={loopReferenceTracks(globalLoopIdx)}
                        />
                      </Field>
                      <Field label="Spacing from Referenced Track (m) *" hint="Centre-to-centre, ≥ 5.3 (blank = 5.3)">
                        <Num
                          value={l.spacing}
                          placeholder="5.3"
                          min="5.3"
                          onChange={(e) => updateLoopAt(l, { spacing: e.target.value })}
                        />
                      </Field>
                      <Field label="C1 chainage (MAIN m) *" hint={`First crossover point (blank C1+C2 = auto-centre, default ${defaultC1})`}>
                        <Num
                          value={l.c1}
                          placeholder={String(defaultC1)}
                          min="0"
                          onChange={(e) => updateLoopAt(l, { c1: e.target.value })}
                        />
                      </Field>
                      <Field label="C2 chainage (MAIN m)" hint={`Second point (blank = C1 + distance, default ${defaultC2})`}>
                        <Num
                          value={l.c2}
                          placeholder={String(defaultC2)}
                          min="0"
                          onChange={(e) => updateLoopAt(l, { c2: e.target.value })}
                        />
                      </Field>
                      <Field label="Crossover distance (m)" hint="Used when C2 is blank (default 750)">
                        <Num
                          value={l.crossoverDistance}
                          placeholder="750.0"
                          min="0"
                          onChange={(e) => updateLoopAt(l, { crossoverDistance: e.target.value })}
                        />
                      </Field>
                      <Field label="Overrun before C1 (m)" hint="OVER RUN LINE past the turnout (blank = 120)">
                        <Num
                          value={l.extStart}
                          placeholder="120.0"
                          min="0"
                          onChange={(e) => updateLoopAt(l, { extStart: e.target.value })}
                        />
                      </Field>
                      <Field label="Overrun past C2 (m)" hint="OVER RUN LINE past the turnout (blank = 120)">
                        <Num
                          value={l.extEnd}
                          placeholder="120.0"
                          min="0"
                          onChange={(e) => updateLoopAt(l, { extEnd: e.target.value })}
                        />
                      </Field>
                    </Grid>
                  </ItemCard>
                );
              })
            )}
          </div>

          {/* ========================================================= */}
          {/* 2. Platforms (same fields as PlatformsSection)            */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>🏗️</span> Platforms ({stationPlatforms.length})
              </h3>
              <YardAddButton onClick={addPlatform}>platform</YardAddButton>
            </div>
            <p className="text-[10.5px] text-slate-500">
              SIDE sits next to one track; ISLAND sits between two (blank = 7.0 m / 550 m / 1.68 m / 0.84 m).
            </p>

            {stationPlatforms.length === 0 ? (
              <Empty>No platforms configured for this yard. Click "+ Add platform" to add one.</Empty>
            ) : (
              stationPlatforms.map((p, idx) => {
                const globalPlatIdx = (form.platforms || []).indexOf(p);
                return (
                  <ItemCard
                    key={idx}
                    title={`PLATFORM_${globalPlatIdx + 1}${p.name?.trim() ? ` · ${p.name.trim()}` : ''}`}
                    badge={`${p.type || 'SIDE'} · ${p.track || 'Track'}`}
                    subtitle={`${p.length || 550}m × ${p.width || 7}m`}
                    onRemove={() => removePlatform(p)}
                  >
                    <Grid>
                      <Field label="Track *">
                        <Sel
                          value={p.track}
                          onChange={(e) => updatePlatformAt(p, { track: e.target.value })}
                          options={trackOpts}
                        />
                      </Field>
                      <Field label="Type">
                        <Sel
                          value={p.type}
                          onChange={(e) => updatePlatformAt(p, { type: e.target.value })}
                          options={['SIDE', 'ISLAND']}
                        />
                      </Field>
                      {p.type === 'ISLAND' ? (
                        <Field label="Second track *" hint="The other track it serves">
                          <Sel
                            value={p.track2}
                            onChange={(e) => updatePlatformAt(p, { track2: e.target.value })}
                            options={trackOpts}
                          />
                        </Field>
                      ) : (
                        <Field label="Side of track">
                          <Sel
                            value={p.side}
                            onChange={(e) => updatePlatformAt(p, { side: e.target.value })}
                            options={['LEFT', 'RIGHT']}
                          />
                        </Field>
                      )}
                      <Field label="Clearance (m)" hint="Track centre → near edge (blank = 1.68)">
                        <Num
                          value={p.clearance}
                          placeholder="1.68"
                          min="0"
                          onChange={(e) => updatePlatformAt(p, { clearance: e.target.value })}
                        />
                      </Field>
                      <Field label="Width (m)" hint="Blank = 7.0">
                        <Num
                          value={p.width}
                          placeholder="7.0"
                          min="0"
                          onChange={(e) => updatePlatformAt(p, { width: e.target.value })}
                        />
                      </Field>
                      <Field label="Length (m)" hint="Blank = 550">
                        <Num
                          value={p.length}
                          placeholder="550.0"
                          min="0"
                          onChange={(e) => updatePlatformAt(p, { length: e.target.value })}
                        />
                      </Field>
                      <Field label="Height (m)" hint="Text label only (blank = 0.84)">
                        <Num
                          value={p.height}
                          placeholder="0.84"
                          min="0"
                          onChange={(e) => updatePlatformAt(p, { height: e.target.value })}
                        />
                      </Field>
                      <Field label="Platform name">
                        <Text
                          value={p.name}
                          placeholder="HIGH LEVEL PASSENGER PLATFORM"
                          onChange={(e) => updatePlatformAt(p, { name: e.target.value })}
                        />
                      </Field>
                    </Grid>
                    <div className="mt-3">
                      <Check
                        checked={p.centerOnTrack !== false}
                        onChange={(v) => updatePlatformAt(p, { centerOnTrack: v })}
                        label={`Centre on ${isAlignmentDatum ? 'alignment' : 'station'} point (${isAlignmentDatum ? `${stnDist.toFixed(1)} m` : `${stnName} at ${stnDisp}`})`}
                      />
                      <p className="mt-0.5 text-[10.5px] text-slate-400">
                        Takes {isAlignmentDatum ? 'the alignment reference' : stnName} at {stnDist.toFixed(1)} m as center and builds the {p.length || '550'} m platform around it.
                      </p>
                    </div>
                  </ItemCard>
                );
              })
            )}
          </div>

          {/* ========================================================= */}
          {/* 3. Crossovers (same fields as CrossoversSection)           */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>🔀</span> Crossovers ({stationCrossovers.length})
              </h3>
              <YardAddButton onClick={addCrossover}>crossover</YardAddButton>
            </div>
            <p className="text-[10.5px] text-slate-500">
              Only the START chainage is input — the second SRJ is derived. Type AUTO to let the engine place it.
            </p>

            {!hasGenerated && (
              <div className="rounded-lg border border-blue-200 bg-blue-50/80 p-2.5 text-xs text-blue-900 shadow-2xs">
                <div className="flex items-start gap-2">
                  <span className="text-sm select-none" aria-hidden="true">ℹ️</span>
                  <div className="leading-snug">
                    <span className="font-semibold">Crossover chainages:</span> Crossover chainages will be shown after you generate DXF once (chainages require backend calculation).
                  </div>
                </div>
              </div>
            )}

            {stationCrossovers.length === 0 ? (
              <Empty>
                No crossovers configured for {stnName}. Click "+ Add crossover" to add one.
              </Empty>
            ) : (
              stationCrossovers.map((x, idx) => {
                const globalXIdx = (form.crossovers || []).indexOf(x);
                const itemLoopEnds = getExtendedLoopEnds(form, globalXIdx);
                const targetTrack = itemLoopEnds[x.from] ? x.from : (itemLoopEnds[x.to] ? x.to : null);
                const ends = targetTrack ? itemLoopEnds[targetTrack] : null;
                const setChainage = (v) => updateCrossoverAt(x, { chainage: v });
                const chipCls = 'rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 cursor-pointer';
                return (
                  <ItemCard
                    key={idx}
                    title={`C${globalXIdx + 1}${x.from && x.to ? ` · ${x.from} → ${x.to}` : ''}`}
                    badge={x.chainage ? `CH ${x.chainage}` : 'AUTO'}
                    subtitle={`${x.direction || 'NORMAL'} · ${x.turnout || '1:12'}`}
                    onRemove={() => removeCrossover(x)}
                  >
                    <Grid>
                      <Field label="From track *">
                        <Sel
                          value={x.from}
                          onChange={(e) => updateCrossoverAt(x, { from: e.target.value })}
                          options={trackOpts}
                        />
                      </Field>
                      <Field label="To track *">
                        <Sel
                          value={x.to}
                          onChange={(e) => updateCrossoverAt(x, { to: e.target.value })}
                          options={trackOpts}
                        />
                      </Field>
                      <Field
                        label="Start chainage (MAIN m) *"
                        hint={
                          ends
                            ? `First SRJ on ${x.from || targetTrack} — range [${ends.c1}, ${ends.c2}], or AUTO${
                                ends.isExtended ? ` (Extended from [${ends.baseC1}, ${ends.baseC2}])` : ''
                              }`
                            : 'First SRJ, or AUTO'
                        }
                      >
                        <Text
                          value={x.chainage}
                          placeholder={ends ? `${ends.c1} or ${ends.c2} or AUTO` : 'chainage or AUTO'}
                          onChange={(e) => setChainage(e.target.value)}
                        />
                        {ends && (
                          <span className="mt-1 flex flex-wrap gap-1.5">
                            <button type="button" className={chipCls} onClick={() => setChainage(String(ends.c1))}>
                              Loop start {ends.c1}
                            </button>
                            <button type="button" className={chipCls} onClick={() => setChainage(String(ends.c2))}>
                              Loop end {ends.c2}
                            </button>
                            <button type="button" className={chipCls} onClick={() => setChainage('AUTO')}>
                              AUTO
                            </button>
                          </span>
                        )}
                      </Field>
                      <Field label="Direction">
                        <Sel
                          value={x.direction || 'FORWARD'}
                          onChange={(e) => updateCrossoverAt(x, { direction: e.target.value })}
                          options={['FORWARD', 'REVERSE']}
                        />
                      </Field>
                      {String(x.chainage || '').trim().toUpperCase() === 'AUTO' && globalXIdx > 0 && (
                        <Field label="AUTO anchor crossover" hint="13 m same direction; 54 m opposite direction">
                          <Sel
                            value={x.autoAnchor || ''}
                            onChange={(e) => updateCrossoverAt(x, { autoAnchor: e.target.value })}
                            options={[
                              { value: '', label: 'Previous crossover (default)' },
                              ...(form.crossovers || []).slice(0, globalXIdx).map((item, k) => ({
                                value: `C${k + 1}`,
                                label: `C${k + 1} · ${item.from || '?'} → ${item.to || '?'}`,
                              })),
                            ]}
                          />
                        </Field>
                      )}
                      <Field label="Turnout" hint="Blank = 1:12">
                        <Sel
                          value={x.turnout || ''}
                          onChange={(e) => updateCrossoverAt(x, { turnout: e.target.value })}
                          options={[{ value: '', label: 'Default (1:12)' }, '1:12', '1:8.5']}
                        />
                      </Field>
                    </Grid>
                  </ItemCard>
                );
              })
            )}
          </div>

          {/* ========================================================= */}
          {/* 4. Station Building (same fields as StationsSection)       */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>🏢</span> Station Building ({stationBuildings.length})
              </h3>
              <YardAddButton onClick={addStationBuilding}>station building</YardAddButton>
            </div>
            <p className="text-[10.5px] text-slate-500">
              Rectangular footprint placed against a platform edge. Blank length/width = 40 × 10 m.
            </p>

            {stationBuildings.length === 0 ? (
              <p className="text-[11px] text-slate-500">No station building configured for {stnName}.</p>
            ) : (
              stationBuildings.map((s, idx) => {
                const globalStnIdx = (form.stations || []).indexOf(s);
                return (
                  <ItemCard
                    key={idx}
                    title={s.name?.trim() || `Station ${globalStnIdx + 1}`}
                    onRemove={() => removeBuilding(s)}
                  >
                    <Grid>
                      <Field label="Platform *">
                        <Sel
                          value={s.platform}
                          onChange={(e) => updateBuildingAt(s, { platform: e.target.value })}
                          options={layerOpts}
                        />
                      </Field>
                      <Field label="Length (m)" hint="Blank = 40">
                        <Num
                          value={s.length}
                          placeholder="40.0"
                          min="0"
                          onChange={(e) => updateBuildingAt(s, { length: e.target.value })}
                        />
                      </Field>
                      <Field label="Width (m)" hint="Blank = 10">
                        <Num
                          value={s.width}
                          placeholder="10.0"
                          min="0"
                          onChange={(e) => updateBuildingAt(s, { width: e.target.value })}
                        />
                      </Field>
                      <Field label="Side of platform">
                        <Sel
                          value={s.side}
                          onChange={(e) => updateBuildingAt(s, { side: e.target.value })}
                          options={['LEFT', 'RIGHT']}
                        />
                      </Field>
                      <Field label="Building name">
                        <Text
                          value={s.name}
                          placeholder={idx === 0 ? 'STATION BUILDING' : `STATION ${idx + 1}`}
                          onChange={(e) => updateBuildingAt(s, { name: e.target.value })}
                        />
                      </Field>
                      <Field label="Station chainage (KM)" hint={`Referenced to ${stnName} (${stnDisp})`}>
                        <div className="flex gap-1.5 items-center">
                          <Text
                            value={s.chainage ?? ''}
                            placeholder={stnDisp}
                            onChange={(e) => updateBuildingAt(s, { chainage: e.target.value })}
                          />
                          <button
                            type="button"
                            onClick={() => updateBuildingAt(s, { chainage: stnDisp })}
                            className="shrink-0 text-[11px] font-medium text-emerald-700 hover:text-emerald-900 border border-emerald-300 bg-emerald-50 rounded px-2 py-1 cursor-pointer"
                            title="Reset to station reference chainage"
                          >
                            Use {stnDisp}
                          </button>
                        </div>
                        <ChainageRangeReference form={form} units="kilometres" />
                      </Field>
                    </Grid>
                  </ItemCard>
                );
              })
            )}
          </div>

          {/* ========================================================= */}
          {/* 5. Foot Over Bridge (same fields as FobsSection)           */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>🌉</span> Foot Over Bridge (FOB) ({stationFobs.length})
              </h3>
              <YardAddButton onClick={addFob}>FOB</YardAddButton>
            </div>
            <p className="text-[10.5px] text-slate-500">
              Basic deck connecting platforms at {stnName} (validated at 6.25 m clearance and 30 m maximum span).
            </p>

            {stationFobs.length === 0 ? (
              <p className="text-[11px] text-slate-500">No FOB configured for this station.</p>
            ) : (
              stationFobs.map((fb, idx) => {
                const globalFobIdx = (form.fobs || []).indexOf(fb);
                const est = estimateFobSpan(form, globalFobIdx);
                const isOffsetMode = fb.placementMode !== 'fixed';
                return (
                  <ItemCard
                    key={idx}
                    title={`FOB ${globalFobIdx + 1}`}
                    badge={isOffsetMode ? `Offset ${fb.offset || 40}m (${fb.direction || 'INCREASING'})` : (fb.chainage ? `CH ${fb.chainage}` : 'Station-centred')}
                    subtitle={`Width: ${fb.width || 3.0}m · ${fb.refTrack || 'MAIN_LINE'}`}
                    onRemove={() => removeFob(fb)}
                  >
                    <div className="mb-3 flex items-center gap-4 text-xs font-medium text-slate-700">
                      <span className="text-slate-500">Placement mode:</span>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name={`stn-fob-mode-${idx}`}
                          checked={isOffsetMode}
                          onChange={() => updateFobAt(fb, { placementMode: 'offset' })}
                          className="text-sky-600 focus:ring-sky-500"
                        />
                        <span>Offset from station edge (Recommended)</span>
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name={`stn-fob-mode-${idx}`}
                          checked={!isOffsetMode}
                          onChange={() => {
                            const defaultCh = fb.chainage || absoluteChainageAtDistance(form, stnDist ?? form.mainCenter);
                            updateFobAt(fb, { placementMode: 'fixed', chainage: defaultCh });
                          }}
                          className="text-sky-600 focus:ring-sky-500"
                        />
                        <span>Absolute chainage</span>
                      </label>
                    </div>

                    <Grid>
                      <Field label="Reference track *">
                        <Sel
                          value={fb.refTrack || 'MAIN_LINE'}
                          onChange={(e) => updateFobAt(fb, { refTrack: e.target.value })}
                          options={allTracks}
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
                              onChange={(e) => updateFobAt(fb, { offset: e.target.value })}
                            />
                          </Field>
                          <Field label="Placement direction">
                            <Sel
                              value={fb.direction || 'INCREASING'}
                              onChange={(e) => updateFobAt(fb, { direction: e.target.value })}
                              options={['INCREASING', 'DECREASING']}
                            />
                          </Field>
                        </>
                      ) : (
                        <Field label="Absolute chainage *" hint="MAIN datum: km+metres (12+850), or absolute metres (12850)">
                          <Text
                            value={fb.chainage}
                            placeholder={absoluteChainageAtDistance(form, stnDist) || '12+850'}
                            onChange={(e) => updateFobAt(fb, { chainage: e.target.value })}
                          />
                          <ChainageRangeReference form={form} />
                          <button
                            type="button"
                            onClick={() => applyStationFobCentre(fb)}
                            className="mt-1 rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 cursor-pointer"
                          >
                            Use {stnName} centre
                          </button>
                        </Field>
                      )}
                      <Field label="Deck width (m)" hint="Blank = 3.0">
                        <Num
                          value={fb.width}
                          placeholder="3.0"
                          min="0"
                          onChange={(e) => updateFobAt(fb, { width: e.target.value })}
                        />
                      </Field>
                    </Grid>

                    <div className="mt-3">
                      <span className="mb-1 block text-xs font-medium text-slate-600">
                        Platforms to connect * (≥ 2)
                      </span>
                      <div className="flex flex-wrap gap-3">
                        {safeLayers.length === 0 && <span className="text-sm text-slate-400">No platforms defined yet.</span>}
                        {safeLayers.map((layer) => (
                          <Check
                            key={layer}
                            checked={(fb.platforms || []).includes(layer)}
                            onChange={() => toggleFobPlatform(fb, layer)}
                            label={layer}
                          />
                        ))}
                      </div>
                      {est !== null && (
                        <p className="mt-2 text-xs text-slate-500">
                          Estimated span ~{est.toFixed(2)} m.
                        </p>
                      )}
                    </div>

                    <div className="mt-3">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-slate-600">Landing arms (optional, parallel to track)</span>
                        <YardAddButton onClick={() => addArmToFob(fb)}>arm</YardAddButton>
                      </div>
                      {(fb.arms || []).length === 0 && (
                        <Empty>No landing arms (deck only). Add arms to lead onto platforms.</Empty>
                      )}
                      {(fb.arms || []).map((arm, aIdx) => (
                        <div key={aIdx} className="mb-2 rounded-lg border border-slate-200 bg-white p-2.5">
                          <div className="mb-1.5 flex items-center justify-between text-xs font-medium text-slate-700">
                            <span>Arm {aIdx + 1}</span>
                            <button
                              type="button"
                              onClick={() => removeArmFromFob(fb, aIdx)}
                              className="text-red-600 hover:underline cursor-pointer"
                            >
                              Remove arm
                            </button>
                          </div>
                          <Grid cols={3}>
                            <Field label="Arm platform *">
                              <Sel
                                value={arm.platform}
                                onChange={(e) => updateArmAt(fb, aIdx, { platform: e.target.value })}
                                options={[
                                  ...(isBlank(arm.platform) ? [{ value: '', label: 'Select platform…' }] : []),
                                  ...safeLayers.filter((l) => (fb.platforms || []).includes(l)),
                                ]}
                              />
                            </Field>
                            <Field label="Arm length (m)" hint="Blank = 17.0">
                              <Num
                                value={arm.length}
                                placeholder="16.999"
                                min="0"
                                onChange={(e) => updateArmAt(fb, aIdx, { length: e.target.value })}
                              />
                            </Field>
                            <Field label="Arm side">
                              <Sel
                                value={arm.side || 'LEFT'}
                                onChange={(e) => updateArmAt(fb, aIdx, { side: e.target.value })}
                                options={['LEFT', 'RIGHT', 'BOTH']}
                              />
                            </Field>
                          </Grid>
                        </div>
                      ))}
                    </div>
                  </ItemCard>
                );
              })
            )}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold text-slate-800">Bridges ({stationBridges.length})</h3>
              <YardAddButton onClick={addBridge}>bridge</YardAddButton>
            </div>
            {stationBridges.length === 0 && <p className="text-xs text-slate-500">No bridges configured for this station.</p>}
            {stationBridges.map((bridge, idx) => (
              <BridgeCard key={idx} title={`Bridge ${(form.bridges || []).indexOf(bridge) + 1}`}
                onRemove={() => removeBridge(bridge)}
                form={form} bridge={bridge} onChange={(patch) => updateBridgeAt(bridge, patch)}
                  buildingOptions={(form.stations || []).flatMap((s, i) =>
                    (s.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex
                      ? [{ value: i, label: s.name || `Station building ${i + 1}` }] : [])} />
            ))}
          </div>
          <GradientsSection form={form} set={set} stationIndex={stationIndex} />
        </div>
      )}
    </section>
  );
}
