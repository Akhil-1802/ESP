import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CrossoversSection,
  FobsSection,
  GradientsSection,
  MainTracksSection,
  PlatformsSection,
  RobsSection,
  SidingsSection,
  SourceSection,
  StationYardSection,
  StationsSection,
  TracksSection,
} from './components/sections.jsx';
import {
  blankArm,
  blankCrossover,
  blankFob,
  blankGradient,
  blankLine,
  blankLoop,
  blankRob,
  blankSiding,
  blankStation,
} from './lib/formDefaults.js';
import { DxfViewer } from './components/DxfViewer.jsx';
import { JsonViewer } from './components/JsonViewer.jsx';
import { StatusBanner } from './components/StatusBanner.jsx';
import {
  buildConfig,
  fillCentredChainages,
  fillFobCentres,
  fobsNeedingCentre,
  loopsNeedingCentre,
  platformLayers,
  trackOptions,
  validateForm,
} from './lib/config.js';
import { downloadBlob, fetchMainCenter, generateDxf, convertKmlDirect } from './lib/api.js';
import { dxfToSvg, svgToPngBlob } from './lib/dxfPreview.js';

const initialForm = () => ({
  kmlFile: null,
  directKml: false,
  startKm: '',
  startM: '',
  startChainage: '0.000',
  mainLength: null,
  selectedTrackId: null,
  outputDxf: '',
  trackSourceLayer: '',
  stationMarkers: [],
  loops: [],
  mainLines: [],
  mainLineDirection: 'UP',
  additionalLines: [],
  platforms: [],
  crossoverMode: 'manual',
  crossovers: [],
  stations: [],
  fobs: [],
  robs: [],
  sidings: [],
  gradients: [],
});

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState({ kind: 'idle' });
  const [result, setResult] = useState(null);

  // Panel visibility toggles
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(false);

  const sidebarRef = useRef(null);
  // ---- Resizable inputs sidebar -------------------------------------
  const SIDEBAR_MIN_W = 300;
  const SIDEBAR_MAX_W = 1000;
  const SIDEBAR_DEFAULT_W = 370;
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_W);
  const dragRef = useRef(null);

  useEffect(() => {
    const onMove = (e) => {
      if (!dragRef.current) return;
      const dx = e.clientX - dragRef.current.startX;
      setSidebarWidth(
        Math.min(SIDEBAR_MAX_W, Math.max(SIDEBAR_MIN_W, dragRef.current.startW + dx)),
      );
    };
    const onUp = () => {
      if (!dragRef.current) return;
      dragRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
    };
  }, []);

  const startSidebarResize = (e) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startW: sidebarWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  // Force scroll resets on mount to prevent any unwanted horizontal browser displacement
  useEffect(() => {
    window.scrollTo(0, 0);
    document.documentElement.scrollLeft = 0;
    document.body.scrollLeft = 0;
  }, []);

  const tracks = useMemo(() => trackOptions(form), [form]);
  const layers = useMemo(() => platformLayers(form), [form]);
  const config = useMemo(() => buildConfig(form), [form]);
  const configText = useMemo(() => JSON.stringify(config, null, 2), [config]);
  const busy = status.kind === 'busy';

  const onPreviewDirectKml = async () => {
    if (!form.kmlFile) {
      setStatus({ kind: 'error', messages: ['KML file: upload the track alignment (.kml).'] });
      sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    setStatus({ kind: 'busy' });
    try {
      const { blob, filename } = await convertKmlDirect({ kmlFile: form.kmlFile });
      let preview = { svg: null, w: 0, h: 0, entities: 0, error: '' };
      try {
        preview = { ...dxfToSvg(await blob.arrayBuffer()), error: '' };
      } catch {
        preview = { ...preview, error: 'Preview unavailable for this file — download the DXF instead.' };
      }
      setResult({
        blob,
        filename,
        json: JSON.stringify({ mode: 'direct_kml_1to1', file: form.kmlFile.name }, null, 2),
        ...preview,
      });
      setStatus({ kind: 'ok', filename });
    } catch (err) {
      setStatus({ kind: 'error', messages: [err.message] });
      sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const onGenerate = async () => {
    let working = form;
    if (working.directKml) {
      await onPreviewDirectKml();
      return;
    }
    const pendingLoops = loopsNeedingCentre(working);
    const pendingFobs = fobsNeedingCentre(working);
    if (pendingLoops.length > 0 || pendingFobs.length > 0) {
      if (!working.kmlFile) {
        setStatus({ kind: 'error', messages: ['KML file: upload the track alignment (.kml).'] });
        sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }
      setStatus({ kind: 'busy' });
      try {
        const c = await fetchMainCenter({ kmlFile: working.kmlFile, selectedTrackId: working.selectedTrackId });
        working = fillFobCentres(fillCentredChainages(working, c), c);
        setForm(working);
      } catch (err) {
        setStatus({ kind: 'error', messages: [err.message] });
        sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }
    }
    const errors = validateForm(working);
    if (errors.length > 0) {
      setStatus({ kind: 'error', messages: errors });
      sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    const finalConfig = buildConfig(working);
    setStatus({ kind: 'busy' });
    try {
      const { blob, filename } = await generateDxf({ config: finalConfig, kmlFile: working.kmlFile });
      let preview = { svg: null, w: 0, h: 0, entities: 0, error: '' };
      try {
        preview = { ...dxfToSvg(await blob.arrayBuffer()), error: '' };
      } catch {
        preview = { ...preview, error: 'Preview unavailable for this file — download the DXF instead.' };
      }
      setResult({ blob, filename, json: JSON.stringify(finalConfig, null, 2), ...preview });
      setStatus({ kind: 'ok', filename });
    } catch (err) {
      setStatus({ kind: 'error', messages: [err.message] });
      sidebarRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const onLoadDemo = async () => {
    setStatus({ kind: 'busy' });
    try {
      const res = await fetch('/sample_esp.dxf');
      if (!res.ok) throw new Error('Could not load demo DXF file.');
      const buf = await res.arrayBuffer();
      const preview = dxfToSvg(buf);
      const blob = new Blob([buf], { type: 'application/dxf' });
      setResult({
        blob,
        filename: 'ESP_sample.dxf',
        json: configText,
        ...preview,
        error: '',
      });
      setStatus({ kind: 'ok', filename: 'ESP_sample.dxf (Demo)' });
    } catch (err) {
      setStatus({ kind: 'error', messages: [err.message] });
    }
  };

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(configText);
      setStatus({ kind: 'ok', filename: 'Config JSON copied to clipboard.' });
    } catch {
      setStatus({ kind: 'error', messages: ['Clipboard unavailable — use Download JSON instead.'] });
    }
  };

  const downloadJson = () => {
    const textToDownload = result ? result.json : configText;
    downloadBlob(new Blob([textToDownload], { type: 'application/json' }), 'inputconfig.json');
  };

  const downloadResultPng = async () => {
    if (!result || !result.svg) return;
    try {
      const blob = await svgToPngBlob(result.svg, result.w, result.h);
      downloadBlob(blob, result.filename.replace(/\.dxf$/i, '') + '.png');
    } catch {
      setStatus({ kind: 'error', messages: ['PNG export failed in this browser — download the DXF instead.'] });
    }
  };

  const handleDownloadDxf = () => {
    if (result && result.blob) {
      downloadBlob(result.blob, result.filename);
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-900 text-slate-800 font-sans">
      {/* Top Main App Header */}
      <header className="z-20 flex h-12 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-3">
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Toggle Sidebar Button */}
          <button
            type="button"
            onClick={() => setLeftOpen(!leftOpen)}
            className={`flex h-7.5 items-center gap-1.5 rounded-lg border px-2 text-xs font-medium transition-colors cursor-pointer shrink-0 ${leftOpen
              ? 'border-emerald-600/50 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50'
              : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            title={leftOpen ? 'Collapse inputs sidebar' : 'Expand inputs sidebar'}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h8m-8 6h16" />
            </svg>
            <span>Inputs</span>
          </button>

          {/* Logo & App Title */}
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-6.5 w-6.5 shrink-0 items-center justify-center rounded-md bg-emerald-600 text-white shadow-sm font-bold text-[11px]">
              ESP
            </div>
            <div className="min-w-0">
              <h1 className="text-xs font-bold text-slate-100 leading-none truncate">
                ESP Generator
              </h1>
              <p className="text-[9.5px] text-slate-400 leading-none mt-0.5 hidden sm:block truncate">
                Engineering Scale Plan · DXF Studio
              </p>
            </div>
          </div>
        </div>

        {/* Center status badge */}
        <div className="hidden md:flex items-center gap-2">
          {status.kind === 'busy' && (
            <span className="flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-950/60 px-2.5 py-0.5 text-[11px] text-sky-300">
              <span className="h-2 w-2 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
              Generating…
            </span>
          )}
          {status.kind === 'ok' && (
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-950/60 px-2.5 py-0.5 text-[11px] text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Ready: {status.filename}
            </span>
          )}
          {status.kind === 'error' && (
            <span className="flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-950/60 px-2.5 py-0.5 text-[11px] text-rose-300">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
              {status.messages.length} issue{status.messages.length > 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Right Header Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Toggle JSON Panel Button */}
          <button
            type="button"
            onClick={() => setRightOpen(!rightOpen)}
            className={`flex h-7.5 items-center gap-1.5 rounded-lg border px-2 text-xs font-medium transition-colors cursor-pointer ${rightOpen
              ? 'border-emerald-600/50 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50'
              : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            title={rightOpen ? 'Collapse JSON panel' : 'Expand JSON panel'}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>JSON</span>
          </button>

          {/* Primary Generate Button */}
          <button
            type="button"
            onClick={onGenerate}
            disabled={busy}
            className="flex h-7.5 items-center gap-1.5 rounded-lg bg-emerald-600 px-3 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50 transition-all cursor-pointer"
          >
            {busy ? (
              <>
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Generating…</span>
              </>
            ) : (
              <>
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span>Generate DXF</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* 3-Panel Main Workbench */}
      <div className="relative flex flex-1 overflow-hidden min-h-0">
        {/* ============================================================ */}
        {/* PANEL 1: LEFT SIDEBAR (Inputs)                               */}
        {/* ============================================================ */}
        {leftOpen ? (
          <aside
            style={{ width: `${sidebarWidth}px` }}
            className="relative flex shrink-0 flex-col border-r border-slate-200 bg-slate-100 z-10 shadow-md"
          >
            {/* Sidebar Header */}
            <div className="flex h-9 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-3">
              <div className="flex items-center gap-1.5">
                <svg className="h-3.5 w-3.5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                <h2 className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                  Input Parameters
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setLeftOpen(false)}
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                title="Collapse sidebar"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            </div>

            {/* Scrollable Form Sections */}
            <div
              ref={sidebarRef}
              className="flex-1 overflow-y-auto p-3 space-y-3 text-xs"
            >
              <StatusBanner status={status} />

              <SourceSection form={form} set={setForm} onPreviewKml={onGenerate} onPreviewDirectKml={onPreviewDirectKml} />

              <MainTracksSection form={form} set={setForm} />

              {(form.stationMarkers || []).length > 0 ? (
                <>
                  <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-3 py-2 text-slate-300">
                    <span className="font-semibold text-emerald-400 block text-[11px] uppercase tracking-wider">
                      Station-Referenced Yard Components
                    </span>
                    <span className="text-[10.5px] text-slate-400 block mt-0.5">
                      {(form.stationMarkers || []).length} station{(form.stationMarkers || []).length > 1 ? 's' : ''} configured. Each section below takes its station as reference for loop lines, platforms, and yard elements.
                    </span>
                  </div>

                  {(form.stationMarkers || []).map((stn, idx) => (
                    <StationYardSection
                      key={idx}
                      station={stn}
                      stationIndex={idx}
                      form={form}
                      set={setForm}
                      tracks={tracks}
                      layers={layers}
                    />
                  ))}
                </>
              ) : (
                <>
                  <div className="rounded-lg border border-amber-500/20 bg-amber-950/20 px-3 py-2 text-amber-200/90">
                    <span className="font-semibold text-amber-300 block text-[11px]">
                      Single / Standalone Layout Mode
                    </span>
                    <span className="text-[10.5px] text-amber-200/70 block mt-0.5">
                      To configure loop lines and platforms referenced to specific stations, enter <strong>No. of stations</strong> in Section 1 above.
                    </span>
                  </div>

                  <TracksSection form={form} set={setForm} />
                  <PlatformsSection form={form} set={setForm} tracks={tracks} />
                  <CrossoversSection form={form} set={setForm} tracks={tracks} />
                  <StationsSection form={form} set={setForm} layers={layers} />
                  <FobsSection form={form} set={setForm} tracks={tracks} layers={layers} />
                  <RobsSection form={form} set={setForm} tracks={tracks} layers={layers} />
                  <SidingsSection form={form} set={setForm} tracks={tracks} />
                  <GradientsSection form={form} set={setForm} tracks={tracks} />
                </>
              )}
            </div>

            {/* Drag handle: resize the inputs sidebar */}
            <div
              onPointerDown={startSidebarResize}
              onDoubleClick={() => setSidebarWidth(SIDEBAR_DEFAULT_W)}
              title="Drag to resize · double-click to reset"
              className="group absolute right-0 top-0 z-30 h-full w-1.5 cursor-col-resize touch-none bg-transparent hover:bg-emerald-500/50 active:bg-emerald-500/70 transition-colors"
            >
              <span className="pointer-events-none absolute right-0 top-1/2 h-10 w-1 -translate-y-1/2 rounded-l bg-slate-300 group-hover:bg-emerald-500" />
            </div>

            {/* Sticky Sidebar Bottom Generate Action */}
            <div className="shrink-0 border-t border-slate-200 bg-white p-2.5 shadow-sm">
              <button
                type="button"
                onClick={onGenerate}
                disabled={busy}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-slate-900 py-2 text-xs font-semibold text-white shadow hover:bg-slate-800 disabled:opacity-50 transition-colors cursor-pointer"
              >
                {busy ? (
                  <>
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    <span>Processing Alignment…</span>
                  </>
                ) : (
                  <>
                    <svg className="h-3.5 w-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Generate DXF Drawing</span>
                  </>
                )}
              </button>
            </div>
          </aside>
        ) : (
          /* Collapsed strip button */
          <div className="flex flex-col border-r border-slate-800 bg-slate-950 py-2 px-1">
            <button
              type="button"
              onClick={() => setLeftOpen(true)}
              className="flex items-center gap-1 rounded bg-slate-800 p-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white cursor-pointer"
              title="Expand Inputs Sidebar"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
            <div className="mt-3 flex flex-col items-center gap-1 font-mono text-[9px] text-slate-500 [writing-mode:vertical-lr] select-none">
              INPUTS
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* PANEL 2: CENTER VIEWPORT (Big DXF Viewer)                   */}
        {/* ============================================================ */}
        <main className="flex-1 min-w-0 h-full overflow-hidden flex flex-col bg-slate-950">
          <DxfViewer
            key={result ? result.filename : 'empty'}
            result={result}
            busy={busy}
            onDownloadDxf={handleDownloadDxf}
            onDownloadPng={downloadResultPng}
            onDownloadJson={downloadJson}
            onLoadDemo={onLoadDemo}
          />
        </main>

        {/* ============================================================ */}
        {/* PANEL 3: RIGHT PANEL (Compact JSON File)                     */}
        {/* ============================================================ */}
        {rightOpen ? (
          <aside className="relative flex w-[270px] sm:w-[290px] shrink-0 flex-col h-full z-10 shadow-md">
            <JsonViewer
              liveConfigText={configText}
              resultConfigText={result ? result.json : null}
              onCopy={copyJson}
              onDownload={downloadJson}
              onClose={() => setRightOpen(false)}
            />
          </aside>
        ) : (
          /* Collapsed strip button */
          <div
            onClick={() => setRightOpen(true)}
            className="flex flex-col items-center border-l border-slate-800 bg-slate-950 py-2 px-1 cursor-pointer hover:bg-slate-900 transition-colors"
            title="Expand JSON Panel"
          >
            <button
              type="button"
              className="flex items-center gap-1 rounded bg-slate-800 p-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white cursor-pointer"
              title="Expand JSON Panel"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="mt-3 flex flex-col items-center gap-1 font-mono text-[9px] font-semibold text-slate-400 hover:text-emerald-400 [writing-mode:vertical-lr] select-none tracking-widest uppercase">
              JSON
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Re-exports keep section factories importable for tests/smoke scripts.
export { blankArm, blankCrossover, blankFob, blankGradient, blankLine, blankLoop, blankSiding, blankStation };
