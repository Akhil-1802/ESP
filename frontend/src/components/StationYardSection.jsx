import { useState } from 'react';
import { fmt, isBlank } from '../lib/formUtils.js';
import { useFormSetter } from '../lib/useFormSetter.js';
import {
  FOB_MAX_SPAN_M,
  estimateFobSpan,
  formatStartChainage,
  getExtendedLoopEnds,
  getPlatformBounds,
  getStationTrackDistance,
  getTrackRange,
  parseKmM,
} from '../lib/config.js';
import {
  blankArm,
  blankCrossover,
  blankFob,
  blankGradient,
  blankLoop,
  blankRob,
  blankSiding,
  blankStation,
} from '../lib/formDefaults.js';
import { Check, Empty, Field, Grid, ItemCard, Num, Sel, Text } from './fields.jsx';

export function StationYardSection({
  station,
  stationIndex,
  form,
  set,
  tracks,
  layers,
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
  const stnDist = getStationTrackDistance(station, form.startKm, form.startM);

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

  const loopEnds = getExtendedLoopEnds(form);

  const addStandardCrossovers = () => {
    const l1 = stationLoops[0]?.name || 'LOOP_1';
    const l2 = stationLoops[1]?.name || (tracks.find((t) => t.startsWith('LOOP_') && t !== l1) || 'LOOP_2');
    const c1Chainage = stationLoops[0]?.c1 || loopEnds[l1]?.c1 || 'AUTO';
    const c2Chainage = stationLoops[1]?.c2 || loopEnds[l2]?.c2 || 'AUTO';
    const defaults = [
      {
        ...blankCrossover(),
        from: l1,
        to: 'MAIN_LINE',
        chainage: c1Chainage,
        direction: 'FORWARD',
        turnout: '1:12',
        stationIndex,
      },
      {
        ...blankCrossover(),
        from: 'MAIN_LINE',
        to: l2,
        chainage: c2Chainage,
        direction: 'FORWARD',
        turnout: '1:12',
        stationIndex,
      },
      {
        ...blankCrossover(),
        from: 'MAIN_LINE',
        to: l1,
        chainage: 'AUTO',
        direction: 'FORWARD',
        turnout: '1:12',
        autoAnchor: '',
        stationIndex,
      },
      {
        ...blankCrossover(),
        from: l2,
        to: 'MAIN_LINE',
        chainage: 'AUTO',
        direction: 'REVERSE',
        turnout: '1:12',
        autoAnchor: '',
        stationIndex,
      },
    ];
    setTop({
      crossovers: [
        ...(form.crossovers || []).filter((x) => (x.stationIndex ?? 0) !== stationIndex),
        ...defaults,
      ],
    });
  };

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
    setTop({ stations: (form.stations || []).filter((s) => s !== bldObj) });
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
    const offset = Number(fobObj?.offset || 40.0);
    const dir = fobObj?.direction || 'INCREASING';
    const width = Number(fobObj?.width || 3.0);
    const hw = width / 2.0;
    const towardsSide = dir === 'INCREASING' ? 'LEFT' : 'RIGHT';
    let armTowardsStation = 0.0;
    for (const a of fobObj?.arms || []) {
      if ((a.side || '').toUpperCase() === towardsSide) {
        armTowardsStation = Math.max(armTowardsStation, Number(a.length || 0.0));
      }
    }
    const stn = stationBuildings[0] || form.stations?.[0];
    const stnLen = Number(stn?.length || 40.0);
    const edgeOffset = stnLen / 2.0;
    const extra = hw + armTowardsStation;
    const fobCh = dir === 'INCREASING'
      ? stnDist + edgeOffset + offset + extra
      : Math.max(0, stnDist - edgeOffset - (offset + extra));

    updateFobAt(fobObj, {
      chainage: fmt(fobCh),
      offset: String(offset),
      direction: dir,
    });
  };

  // -------------------------------------------------------------
  // 5. ROBs belonging to this station
  // -------------------------------------------------------------
  const stationRobs = (form.robs || []).filter(
    (r) => (r.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addRob = () => {
    const defaultPlat = safeLayers[0] || 'PLATFORM_1';
    const newRob = {
      ...blankRob(),
      platform: defaultPlat,
      referenceEnd: 'START',
      offset: '50.0',
      width: '10.0',
      referenceTrack: 'MAIN_LINE',
      stationIndex,
    };
    setTop({ robs: [...(form.robs || []), newRob] });
  };

  const updateRobAt = (robObj, patch) => {
    const globalIdx = (form.robs || []).indexOf(robObj);
    if (globalIdx < 0) return;
    const current = [...form.robs];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ robs: current });
  };

  const removeRob = (robObj) => {
    setTop({ robs: (form.robs || []).filter((r) => r !== robObj) });
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

  // -------------------------------------------------------------
  // 7. Gradients belonging to this station
  // -------------------------------------------------------------
  const stationGradients = (form.gradients || []).filter(
    (g) => (g.stationIndex ?? (form.stationMarkers?.length > 1 ? -1 : 0)) === stationIndex,
  );

  const addGradient = () => {
    const parsedStn = parseKmM(station?.chainage);
    const hasKm = !isBlank(station?.km);
    const hasM = !isBlank(station?.m);
    const stnKm = hasKm ? String(station.km) : (hasM ? '0' : (parsedStn.km || '0'));
    const stnM = hasM ? String(station.m) : (parsedStn.m || '');
    const defaultCh = formatStartChainage(stnKm, stnM);
    const newGradient = {
      ...blankGradient(),
      km: stnKm,
      m: stnM,
      chainage: defaultCh,
      direction: 'UP',
      rl: '',
      leftValue: '',
      leftDirection: 'STRAIGHT',
      rightValue: '',
      rightDirection: 'RISE',
      stationIndex,
    };
    setTop({ gradients: [...(form.gradients || []), newGradient] });
  };

  const updateGradientAt = (gradObj, patch) => {
    const globalIdx = (form.gradients || []).indexOf(gradObj);
    if (globalIdx < 0) return;
    const current = [...form.gradients];
    current[globalIdx] = { ...current[globalIdx], ...patch };
    setTop({ gradients: current });
  };

  const removeGradient = (gradObj) => {
    setTop({ gradients: (form.gradients || []).filter((g) => g !== gradObj) });
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
              Station {stationIndex + 1}
            </span>
            <h2 className="text-sm font-bold text-[var(--text-primary)] truncate">
              {stnName}
            </h2>
            <span className="rounded-full bg-[rgba(50,95,244,0.08)] border border-[var(--border)] px-2 py-0.5 text-[10.5px] font-semibold text-[var(--accent)]">
              Datum: {stnDisp} (at {stnDist.toFixed(1)} m)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
          <span>{stationLoops.length} loops · {stationPlatforms.length} platforms · {stationCrossovers.length} crossovers · {stationRobs.length} ROBs</span>
        </div>
      </div>

      {open && (
        <div className="p-3.5 space-y-4 text-xs bg-slate-50/30">
          {/* ========================================================= */}
          {/* 1. Loop Lines (same fields as TracksSection)              */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🔄</span> Loops &amp; Additional Lines ({stationLoops.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Loops are bounded parallel lines (C1 → C2) referenced to {stnName}.
                </p>
              </div>
              <button
                type="button"
                onClick={addLoop}
                className="rounded-lg bg-emerald-700 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-600 transition-colors cursor-pointer shadow-sm"
              >
                + Add loop
              </button>
            </div>

            {stationLoops.length === 0 ? (
              <Empty>No loops configured for {stnName}. Click "+ Add loop" to add one.</Empty>
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
                    title={`${l.name?.trim() || `LOOP_${globalLoopIdx + 1}`} · Referenced to ${stnName}`}
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
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🏗️</span> Platforms ({stationPlatforms.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  SIDE sits next to one track; ISLAND sits between two (blank = 7.0 m / 550 m / 1.68 m / 0.84 m).
                </p>
              </div>
              <button
                type="button"
                onClick={addPlatform}
                className="rounded-lg bg-emerald-700 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-600 transition-colors cursor-pointer shadow-sm"
              >
                + Add platform
              </button>
            </div>

            {stationPlatforms.length === 0 ? (
              <Empty>No platforms configured for {stnName}. Click "+ Add platform" to add one.</Empty>
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
                        label={`Centre on station point (${stnName} at ${stnDisp})`}
                      />
                      <p className="mt-0.5 text-[10.5px] text-slate-400">
                        Takes {stnName} at {stnDist.toFixed(1)} m as center and builds the {p.length || '550'} m platform around it.
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
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🔀</span> Crossovers ({stationCrossovers.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Only the START chainage is input — the second SRJ is derived. Type AUTO to let the engine place it.
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={addStandardCrossovers}
                  className="rounded-lg border border-emerald-600/60 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 transition-colors cursor-pointer"
                  title="Populate standard 4 Class B crossovers (C1–C4) for this station"
                >
                  + Standard 4 (C1–C4)
                </button>
                <button
                  type="button"
                  onClick={addCrossover}
                  className="rounded-lg bg-emerald-700 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-600 transition-colors cursor-pointer shadow-sm"
                >
                  + Add crossover
                </button>
              </div>
            </div>

            {stationCrossovers.length === 0 ? (
              <Empty>
                No crossovers configured for {stnName}. Click "+ Standard 4 (C1–C4)" to add the standard set, or "+ Add crossover" for a custom one.
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
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🏢</span> Station Building ({stationBuildings.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Rectangular footprint placed against a platform edge. Blank length/width = 40 × 10 m.
                </p>
              </div>
              <button
                type="button"
                onClick={addStationBuilding}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer shadow-sm"
              >
                + Add station building
              </button>
            </div>

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
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🌉</span> Foot Over Bridge (FOB) ({stationFobs.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Basic deck connecting platforms at {stnName} (validated at 6.25 m clearance and 30 m maximum span).
                </p>
              </div>
              <button
                type="button"
                onClick={addFob}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer shadow-sm"
              >
                + Add FOB
              </button>
            </div>

            {stationFobs.length === 0 ? (
              <p className="text-[11px] text-slate-500">No FOB configured for this station.</p>
            ) : (
              stationFobs.map((fb, idx) => {
                const globalFobIdx = (form.fobs || []).indexOf(fb);
                const est = estimateFobSpan(form, globalFobIdx);
                return (
                  <ItemCard
                    key={idx}
                    title={`FOB ${globalFobIdx + 1}`}
                    onRemove={() => removeFob(fb)}
                  >
                    <Grid>
                      <Field label="Reference track *">
                        <Sel
                          value={fb.refTrack || 'MAIN_LINE'}
                          onChange={(e) => updateFobAt(fb, { refTrack: e.target.value })}
                          options={allTracks}
                        />
                      </Field>
                      <Field label="FOB chainage (MAIN m)" hint="Default = 40m from station edge">
                        <Text
                          value={fb.chainage}
                          placeholder="MAIN_CENTER"
                          onChange={(e) => updateFobAt(fb, { chainage: e.target.value })}
                        />
                        <button
                          type="button"
                          onClick={() => applyStationFobCentre(fb)}
                          className="mt-1 rounded-md border border-slate-300 px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 cursor-pointer"
                        >
                          Use {stnName} centre
                        </button>
                      </Field>
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
                        est > FOB_MAX_SPAN_M ? (
                          <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
                            Estimated span ~{est.toFixed(2)} m — over the {FOB_MAX_SPAN_M} m maximum.
                          </p>
                        ) : (
                          <p className="mt-2 text-xs text-slate-500">
                            Estimated span ~{est.toFixed(2)} m (within the {FOB_MAX_SPAN_M} m maximum).
                          </p>
                        )
                      )}
                    </div>

                    <div className="mt-3">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-600">Landing arms (optional, parallel to track)</span>
                        <button
                          type="button"
                          onClick={() => addArmToFob(fb)}
                          className="ml-auto rounded-md border border-slate-300 px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100 cursor-pointer"
                        >
                          + Add arm
                        </button>
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
                                options={['LEFT', 'RIGHT']}
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

          {/* ========================================================= */}
          {/* 6. Road Over Bridges (same fields as RobsSection)         */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🚗</span> Road Over Bridges (ROB) ({stationRobs.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Position is calculated from selected platform start (- offset) or platform end (+ offset).
                </p>
              </div>
              <button
                type="button"
                onClick={addRob}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer shadow-sm"
              >
                + Add ROB
              </button>
            </div>

            {stationRobs.length === 0 ? (
              <p className="text-[11px] text-slate-500">No ROB configured for this station.</p>
            ) : (
              stationRobs.map((rob, idx) => {
                const globalRobIdx = (form.robs || []).indexOf(rob);
                const platName = rob.platform || safeLayers[0];
                const bounds = getPlatformBounds(form, platName);
                const refEnd = (rob.referenceEnd || 'START').toUpperCase();
                const offsetNum = Number(rob.offset || 0);

                let centerCh = null;
                let formulaText = '';
                if (bounds) {
                  if (refEnd === 'START') {
                    centerCh = bounds.start - offsetNum;
                    formulaText = `${bounds.start.toFixed(2)} m - ${offsetNum.toFixed(2)} m = ${centerCh.toFixed(2)} m`;
                  } else {
                    centerCh = bounds.end + offsetNum;
                    formulaText = `${bounds.end.toFixed(2)} m + ${offsetNum.toFixed(2)} m = ${centerCh.toFixed(2)} m`;
                  }
                }

                return (
                  <ItemCard
                    key={idx}
                    title={`ROB ${globalRobIdx + 1}`}
                    onRemove={() => removeRob(rob)}
                  >
                    <Grid>
                      <Field label="Reference Platform *">
                        <Sel
                          value={rob.platform || safeLayers[0]}
                          onChange={(e) => updateRobAt(rob, { platform: e.target.value })}
                          options={safeLayers}
                        />
                      </Field>

                      <Field
                        label="Platform End Selection *"
                        hint={refEnd === 'START' ? 'Drawn at Start - Offset' : 'Drawn at End + Offset'}
                      >
                        <Sel
                          value={refEnd}
                          onChange={(e) => updateRobAt(rob, { referenceEnd: e.target.value })}
                          options={[
                            { value: 'START', label: 'Platform Start (Start - Offset)' },
                            { value: 'END', label: 'Platform End (End + Offset)' },
                          ]}
                        />
                      </Field>

                      {bounds && (
                        <div className="col-span-full rounded-md bg-slate-100 px-3 py-1.5 text-xs text-slate-700 flex flex-wrap items-center justify-between gap-2">
                          <span>
                            <strong>{bounds.platform} Bounds:</strong> Start = <strong>{bounds.start.toFixed(2)} m</strong>, End = <strong>{bounds.end.toFixed(2)} m</strong>
                          </span>
                          <span className="text-slate-500 font-mono">
                            Centre: {formulaText || (centerCh !== null ? `${centerCh.toFixed(2)} m` : '—')}
                          </span>
                        </div>
                      )}

                      <Field
                        label="Offset from Platform (m) *"
                        hint={refEnd === 'START' ? 'Distance before platform start' : 'Distance after platform end'}
                      >
                        <Num
                          value={rob.offset ?? '50.0'}
                          onChange={(e) => updateRobAt(rob, { offset: e.target.value })}
                          min="0"
                          placeholder="50.0"
                        />
                      </Field>

                      <Field
                        label="ROB Width (m) *"
                        hint="Width along track (X-axis); spans all tracks"
                      >
                        <Num
                          value={rob.width ?? '10.0'}
                          onChange={(e) => updateRobAt(rob, { width: e.target.value })}
                          min="1"
                          placeholder="10.0"
                        />
                      </Field>

                      <Field label="Reference Track" hint="Track alignment to sample center & angle">
                        <Sel
                          value={rob.referenceTrack || 'MAIN_LINE'}
                          onChange={(e) => updateRobAt(rob, { referenceTrack: e.target.value })}
                          options={allTracks}
                        />
                      </Field>
                    </Grid>
                  </ItemCard>
                );
              })
            )}
          </div>

          {/* ========================================================= */}
          {/* 7. Sidings (same fields as SidingsSection)                */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>🛤️</span> Sidings ({stationSidings.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Dead-end sidings running to a parallel spacing, holding CSL, and terminating in a dead end.
                </p>
              </div>
              <button
                type="button"
                onClick={addSiding}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer shadow-sm"
              >
                + Add siding
              </button>
            </div>

            {stationSidings.length === 0 ? (
              <p className="text-[11px] text-slate-500">No sidings configured for {stnName}.</p>
            ) : (
              stationSidings.map((s, idx) => {
                const globalSidingIdx = (form.sidings || []).indexOf(s);
                const range = getTrackRange(s.sourceTrack, form);
                return (
                  <ItemCard
                    key={idx}
                    title={`S${globalSidingIdx + 1}${s.sourceTrack ? ` · ${s.sourceTrack}` : ''}${s.csl ? ` (CSL: ${s.csl}m)` : ''}`}
                    onRemove={() => removeSiding(s)}
                  >
                    <Grid>
                      <Field label="Source track *">
                        <Sel
                          value={s.sourceTrack}
                          onChange={(e) => updateSidingAt(s, { sourceTrack: e.target.value })}
                          options={trackOpts}
                        />
                      </Field>
                      <Field
                        label={
                          <span className="flex items-center justify-between">
                            <span>Start chainage (m) *</span>
                            {range && (
                              <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-mono font-medium text-slate-600">
                                {range.label} m
                              </span>
                            )}
                          </span>
                        }
                        hint={range ? `Chainage range on ${s.sourceTrack}: ${range.label} m` : 'Select a track to see valid chainage range'}
                      >
                        <Text
                          value={s.chainage}
                          placeholder={range ? `e.g. ${range.label}` : 'e.g. 250'}
                          onChange={(e) => updateSidingAt(s, { chainage: e.target.value })}
                        />
                        {range && Number.isFinite(range.c1) && (
                          <span className="mt-1 flex flex-wrap gap-1.5">
                            <button
                              type="button"
                              className={chipCls}
                              onClick={() => updateSidingAt(s, { chainage: String(range.c1) })}
                            >
                              Start {range.c1}m
                            </button>
                            {Number.isFinite(range.c2) && (
                              <>
                                <button
                                  type="button"
                                  className={chipCls}
                                  onClick={() =>
                                    updateSidingAt(s, {
                                      chainage: String(Math.round(((range.c1 + range.c2) / 2) * 10) / 10),
                                    })
                                  }
                                >
                                  Mid {Math.round(((range.c1 + range.c2) / 2) * 10) / 10}m
                                </button>
                                <button
                                  type="button"
                                  className={chipCls}
                                  onClick={() => updateSidingAt(s, { chainage: String(range.c2) })}
                                >
                                  End {range.c2}m
                                </button>
                              </>
                            )}
                          </span>
                        )}
                      </Field>
                      <Field label="Side">
                        <Sel
                          value={s.side || 'LEFT'}
                          onChange={(e) => updateSidingAt(s, { side: e.target.value })}
                          options={['LEFT', 'RIGHT']}
                        />
                      </Field>
                      <Field label="Direction">
                        <Sel
                          value={s.direction || 'FORWARD'}
                          onChange={(e) => updateSidingAt(s, { direction: e.target.value })}
                          options={['FORWARD', 'BACKWARD']}
                        />
                      </Field>
                      <Field label="Clear Standing Length (CSL) m" hint="Blank = 120">
                        <Num
                          value={s.csl}
                          placeholder="120.0"
                          min="0"
                          onChange={(e) => updateSidingAt(s, { csl: e.target.value })}
                        />
                      </Field>
                      <Field label="Turnout Designation">
                        <Sel
                          value={s.turnout || '1:8.5'}
                          onChange={(e) => updateSidingAt(s, { turnout: e.target.value })}
                          options={['1:8.5', '1:12', '1:16']}
                        />
                      </Field>
                      <Field label="Parallel Spacing (m)" hint="Blank = 5.3">
                        <Num
                          value={s.spacing}
                          placeholder="5.3"
                          min="5.3"
                          onChange={(e) => updateSidingAt(s, { spacing: e.target.value })}
                        />
                      </Field>
                    </Grid>
                  </ItemCard>
                );
              })
            )}
          </div>

          {/* ========================================================= */}
          {/* 8. Gradient Annotations (same fields as GradientsSection) */}
          {/* ========================================================= */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span>📐</span> Gradient Annotations ({stationGradients.length})
                </h3>
                <p className="text-[10.5px] text-slate-500">
                  Draws horizontal gradient annotations on the railway alignment referenced to {stnName}.
                </p>
              </div>
              <button
                type="button"
                onClick={addGradient}
                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer shadow-sm"
              >
                + Add Gradient
              </button>
            </div>

            {stationGradients.length === 0 ? (
              <p className="text-[11px] text-slate-500">No gradient annotations configured for {stnName}.</p>
            ) : (
              stationGradients.map((g, idx) => {
                const globalGradIdx = (form.gradients || []).indexOf(g);
                const parsed = parseKmM(g.chainage);
                const kmVal = g.km !== undefined && g.km !== null ? String(g.km) : parsed.km;
                const mVal = g.m !== undefined && g.m !== null ? String(g.m) : parsed.m;
                const hasKm = kmVal !== undefined && kmVal !== null && String(kmVal).trim() !== '';
                const hasM = mVal !== undefined && mVal !== null && String(mVal).trim() !== '';
                const displayCh = (hasKm || hasM) ? formatStartChainage(kmVal, mVal) : '';
                const gradCh = (g.chainage !== undefined && g.chainage !== null && String(g.chainage).trim() !== '')
                  ? String(g.chainage).trim()
                  : displayCh;
                const parseToMeters = (chStr) => {
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

                let offsetDisplay = null;
                if (gradCh !== '') {
                  const gMeters = parseToMeters(gradCh);
                  const sMeters = parseToMeters(stnDisp);
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

                let cardTitle = `Gradient ${globalGradIdx + 1}`;
                if (leftVal || rightVal) {
                  const lPart = leftVal ? `Left: ${leftVal} (${leftDir})` : null;
                  const rPart = rightVal ? `Right: ${rightVal} (${rightDir})` : null;
                  cardTitle = [lPart, rPart].filter(Boolean).join(' | ');
                } else if (gradCh || displayCh) {
                  cardTitle = `Gradient at ${displayCh || gradCh}`;
                }

                return (
                  <ItemCard
                    key={idx}
                    title={cardTitle}
                    onRemove={() => removeGradient(g)}
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
                      {/* KM and M Option */}
                      <div className="sm:col-span-5 space-y-1">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="mb-1 block text-xs font-medium text-slate-700">
                              KM (optional)
                            </span>
                            <Text
                              type="number"
                              min="0"
                              step="any"
                              value={kmVal}
                              placeholder={stnKmVal || '0'}
                              onChange={(e) => {
                                const newKm = e.target.value;
                                const newCh = formatStartChainage(newKm, mVal);
                                updateGradientAt(g, { km: newKm, m: mVal, chainage: newCh });
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
                              placeholder={stnMVal || '0'}
                              onChange={(e) => {
                                const newM = e.target.value;
                                const newCh = formatStartChainage(kmVal, newM);
                                updateGradientAt(g, { km: kmVal, m: newM, chainage: newCh });
                              }}
                            />
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            updateGradientAt(g, { km: stnKmVal, m: stnMVal, chainage: stnDisp });
                          }}
                          className="text-[11px] font-medium text-emerald-700 hover:text-emerald-900 border border-emerald-300 bg-emerald-50 rounded px-2 py-0.5 cursor-pointer"
                        >
                          Fill with {stnName} reference ({stnDisp})
                        </button>
                      </div>

                      <div className="sm:col-span-3">
                        <Field label="Direction">
                          <Sel
                            value={g.direction || 'UP'}
                            onChange={(e) => updateGradientAt(g, { direction: e.target.value })}
                            options={['UP', 'DN']}
                          />
                        </Field>
                      </div>

                      <div className="sm:col-span-4">
                        <Field label="RL (Reduced Level)" hint="e.g. 102.45">
                          <Text
                            value={g.rl ?? ''}
                            placeholder="102.45"
                            onChange={(e) => updateGradientAt(g, { rl: e.target.value })}
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
                              onChange={(e) => updateGradientAt(g, { leftValue: e.target.value })}
                            />
                          </Field>
                          <Field label="Profile">
                            <Sel
                              value={leftDir}
                              onChange={(e) => updateGradientAt(g, { leftDirection: e.target.value })}
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
                              onChange={(e) => updateGradientAt(g, { rightValue: e.target.value, gradientValue: e.target.value })}
                            />
                          </Field>
                          <Field label="Profile">
                            <Sel
                              value={rightDir}
                              onChange={(e) => updateGradientAt(g, { rightDirection: e.target.value, direction: e.target.value })}
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
                          {offsetDisplay ? `Offset: ${offsetDisplay} from Station C/L (${stnDisp})` : 'Aligned with Station Center'}
                        </span>
                      </div>
                    </div>
                  </ItemCard>
                );
              })
            )}
          </div>
        </div>
      )}
    </section>
  );
}
