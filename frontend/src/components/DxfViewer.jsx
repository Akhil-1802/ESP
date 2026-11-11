import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { LAYER_CONFIG } from '../lib/dxfPreview.js';
import { DxfControls } from './DxfControls.jsx';

export function DxfViewer({
  result,
  busy,
  onDownloadDxf,
  onDownloadPng,
  onDownloadJson,
  onLoadDemo,
  isTrimmed = false,
  onToggleTrim = null,
}) {
  const containerRef = useRef(null);

  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, vbX: 0, vbY: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const [mouseCoord, setMouseCoord] = useState(null);

  // Layer category toggles (true = visible)
  const [layersVisible, setLayersVisible] = useState({
    track: true,
    crossover: true,
    platform: true,
    station: true,
    fob: true,
    signal: true,
    fencing: true,
    reference: true,
    text: true,
  });

  // Calculate default fitted viewBox matching container aspect ratio
  const calculateFittedViewBox = useCallback(() => {
    if (!containerRef.current || !result || !result.w || !result.h) return null;
    const rect = containerRef.current.getBoundingClientRect();
    const containerW = Math.max(rect.width, 200);
    const containerH = Math.max(rect.height, 150);
    const containerAR = containerW / containerH;

    const padFactor = 1.05;
    const rawW = result.w * padFactor;
    const rawH = result.h * padFactor;
    const rawAR = rawW / rawH;

    let fitW = rawW;
    let fitH = rawH;

    if (rawAR > containerAR) {
      fitH = fitW / containerAR;
    } else {
      fitW = fitH * containerAR;
    }

    const fitX = result.x0 - (fitW - result.w) / 2;
    const fitY = result.y0 - (fitH - result.h) / 2;

    return { x: fitX, y: fitY, w: fitW, h: fitH, baseW: fitW, baseH: fitH };
  }, [result]);

  // Initial fitted viewBox derived directly during render — tightly focused on track parts
  const initialViewBox = useMemo(() => {
    if (!result || !result.w || !result.h) return null;
    const padFactor = 1.05;
    const rawW = result.w * padFactor;
    const rawH = result.h * padFactor;
    const ar = 16 / 9;
    const rawAR = rawW / rawH;
    const fitW = rawAR > ar ? rawW : rawH * ar;
    const fitH = rawAR > ar ? rawW / ar : rawH;
    const fitX = result.x0 - (fitW - result.w) / 2;
    const fitY = result.y0 - (fitH - result.h) / 2;

    // Zoom into track parts by default (3.8x zoom eliminates huge blank spaces)
    const zoom = 3.8;
    const nextW = fitW / zoom;
    const nextH = fitH / zoom;
    let centerX = fitX + fitW / 2;
    let centerY = fitY + fitH / 2;
    if (result.featureFocus?.hasFeatures && Number.isFinite(result.featureFocus.x)) {
      centerX = result.featureFocus.x;
      centerY = result.featureFocus.y;
    } else if (result.trackMidpoint && Number.isFinite(result.trackMidpoint.x)) {
      centerX = result.trackMidpoint.x;
      centerY = result.trackMidpoint.y;
    }

    return {
      x: centerX - nextW / 2,
      y: centerY - nextH / 2,
      w: nextW,
      h: nextH,
      baseW: fitW,
      baseH: fitH,
    };
  }, [result]);

  const [customViewBox, setCustomViewBox] = useState(null);
  const viewBox = customViewBox || initialViewBox;
  const setViewBox = setCustomViewBox;

  const fitToView = useCallback(() => {
    const fitted = calculateFittedViewBox();
    if (fitted) {
      setCustomViewBox(fitted);
    }
  }, [calculateFittedViewBox]);

  const focusTrackInfo = useCallback((zoomMult = 3.8, targetPoint = null) => {
    const fitted = calculateFittedViewBox();
    if (!fitted) return;
    let targetCenterX = fitted.x + fitted.w / 2;
    let targetCenterY = fitted.y + fitted.h / 2;

    if (targetPoint && Number.isFinite(targetPoint.x) && Number.isFinite(targetPoint.y)) {
      targetCenterX = targetPoint.x;
      targetCenterY = targetPoint.y;
    } else if (result?.featureFocus?.hasFeatures && Number.isFinite(result.featureFocus.x)) {
      targetCenterX = result.featureFocus.x;
      targetCenterY = result.featureFocus.y;
    } else if (result?.trackMidpoint && Number.isFinite(result.trackMidpoint.x)) {
      targetCenterX = result.trackMidpoint.x;
      targetCenterY = result.trackMidpoint.y;
    }

    const nextW = fitted.baseW / zoomMult;
    const nextH = fitted.baseH / zoomMult;
    const nextX = targetCenterX - nextW / 2;
    const nextY = targetCenterY - nextH / 2;
    setCustomViewBox({ ...fitted, x: nextX, y: nextY, w: nextW, h: nextH });
  }, [calculateFittedViewBox, result]);

  // Auto-focus and zoom into the track information whenever a new result arrives
  useEffect(() => {
    setCustomViewBox(null);
    if (result && result.w && result.h) {
      const timer = setTimeout(() => {
        focusTrackInfo(3.8);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [result?.svg, result?.blob, focusTrackInfo]);

  // Window resize observer to keep aspect ratio matching
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(() => {
      setCustomViewBox((prev) => {
        if (!prev || !result) return prev;
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect || rect.width < 50 || rect.height < 50) return prev;
        const currentAR = rect.width / rect.height;
        const centerX = prev.x + prev.w / 2;
        const centerY = prev.y + prev.h / 2;

        let newW = prev.w;
        let newH = prev.h;
        if (newW / newH > currentAR) {
          newH = newW / currentAR;
        } else {
          newW = newH * currentAR;
        }
        return {
          ...prev,
          x: centerX - newW / 2,
          y: centerY - newH / 2,
          w: newW,
          h: newH,
        };
      });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [result]);

  const zoomByFactor = (factor, centerXRatio = 0.5, centerYRatio = 0.5) => {
    setViewBox((prev) => {
      if (!prev) return prev;
      const minW = Math.max(result.w * 0.0005, 0.5);
      const maxW = result.w * 10;
      const nextW = Math.min(Math.max(prev.w / factor, minW), maxW);
      const nextH = prev.h * (nextW / prev.w);

      const nextX = prev.x + centerXRatio * (prev.w - nextW);
      const nextY = prev.y + centerYRatio * (prev.h - nextH);

      return { ...prev, x: nextX, y: nextY, w: nextW, h: nextH };
    });
  };

  const zoomIn = () => zoomByFactor(1.4);
  const zoomOut = () => zoomByFactor(1 / 1.4);
  const reset1to1 = () => fitToView();

  const handleDoubleClick = (e) => {
    if (!containerRef.current || !viewBox) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mx = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const my = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
    zoomByFactor(2.0, mx / rect.width, my / rect.height);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    if (!containerRef.current || !viewBox) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mx = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const my = Math.max(0, Math.min(e.clientY - rect.top, rect.height));

    const factor = e.deltaY < 0 ? 1.25 : 1 / 1.25;
    zoomByFactor(factor, mx / rect.width, my / rect.height);
  };

  const handleMouseDown = (e) => {
    if (e.button !== 0 || !viewBox) return;
    setIsDragging(true);
    setDragStart({
      x: e.clientX,
      y: e.clientY,
      vbX: viewBox.x,
      vbY: viewBox.y,
    });
  };

  const handleMouseMove = (e) => {
    if (!containerRef.current || !viewBox) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mx = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const my = Math.max(0, Math.min(e.clientY - rect.top, rect.height));

    const worldX = viewBox.x + (mx / rect.width) * viewBox.w;
    const worldY = viewBox.y + viewBox.h - (my / rect.height) * viewBox.h;
    setMouseCoord({ x: worldX, y: worldY });

    if (!isDragging) return;

    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;

    const deltaXUnits = dx * (viewBox.w / rect.width);
    const deltaYUnits = dy * (viewBox.h / rect.height);

    setViewBox((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        x: dragStart.vbX - deltaXUnits,
        y: dragStart.vbY - deltaYUnits,
      };
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen?.().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  const toggleLayer = (key) => {
    setLayersVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const currentZoomPercent = useMemo(() => {
    if (!viewBox || !viewBox.baseW) return 100;
    return Math.round((viewBox.baseW / viewBox.w) * 100);
  }, [viewBox]);

  // Construct active SVG with dynamic viewBox, styling, and layer visibility derived from LAYER_CONFIG
  const activeSvg = useMemo(() => {
    if (!result || !result.svg) return null;
    let s = result.svg;

    if (viewBox) {
      const vbStr = `viewBox="${viewBox.x.toFixed(3)} ${viewBox.y.toFixed(3)} ${viewBox.w.toFixed(3)} ${viewBox.h.toFixed(3)}" preserveAspectRatio="xMidYMid meet"`;
      s = s.replace(/viewBox="[^"]*"\s*(preserveAspectRatio="[^"]*")?/, vbStr);
      s = s.replace(/width="[^"]*"/, 'width="100%"');
      s = s.replace(/height="[^"]*"/, 'height="100%"');
    }

    const bgFill = isDark ? '#0a0e17' : '#ffffff';
    const textColor = isDark ? '#f8fafc' : '#0f172a';
    const textHalo = isDark ? '#0a0e17' : '#ffffff';

    // Derive layer visibility dynamically from LAYER_CONFIG
    const categoryOrder = ['track', 'crossover', 'platform', 'station', 'fob', 'signal', 'fencing', 'reference'];
    const hiddenRules = categoryOrder
      .filter((cat) => !layersVisible[cat])
      .flatMap((cat) =>
        Object.entries(LAYER_CONFIG)
          .filter(([, v]) => v.category === cat)
          .map(([name]) => `[data-layer="${name}"] { display: none !important; }`),
      );
    if (!layersVisible.text) {
      hiddenRules.push('.cad-text, .cad-crossover-tag { display: none !important; }');
    }

    const badgeBg = isDark ? '#1e293b' : '#0f172a';
    const badgeBorder = isDark ? '#38bdf8' : '#2563eb';

    const dynamicStyle = `
      <style>
        .cad-bg { fill: ${bgFill} !important; }
        .cad-geom line, .cad-geom path, .cad-geom circle { vector-effect: non-scaling-stroke; stroke-linecap: round; stroke-linejoin: round; }
        .cad-text text { font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: ${textColor}; stroke: ${textHalo}; }
        .crossover-badge-bg { fill: ${badgeBg} !important; stroke: ${badgeBorder} !important; stroke-width: 0.35px !important; vector-effect: non-scaling-stroke; }
        .crossover-badge-text { fill: #ffffff !important; stroke: none !important; font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 700 !important; text-anchor: middle !important; dominant-baseline: central !important; }
        ${hiddenRules.join('\n')}
      </style>
    `;

    s = s.replace(/<style>[\s\S]*?<\/style>/, dynamicStyle);
    return s;
  }, [result, viewBox, isDark, layersVisible]);

  // Custom high-contrast CAD reticle cursor visible on any canvas background
  const cursorStyle = useMemo(() => {
    // In light mode (paper canvas): Dark navy core (#0f172a), crisp white halo (#ffffff), bold red center dot (#ef4444)
    // In dark mode: Sky cyan core (#38bdf8), black halo (#020617), bright red center dot (#ef4444)
    const fg = isDark ? '%2338bdf8' : '%230f172a';
    const halo = isDark ? '%23020617' : '%23ffffff';
    const accent = '%23ef4444';

    if (isDragging) {
      // 4-directional navigation / pan reticle with red center dot
      const panSvg = `<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g stroke='${halo}' stroke-width='4' stroke-linecap='round' stroke-linejoin='round' fill='none'><line x1='16' y1='3' x2='16' y2='29'/><polyline points='12,7 16,3 20,7'/><polyline points='12,25 16,29 20,25'/><line x1='3' y1='16' x2='29' y2='16'/><polyline points='7,12 3,16 7,20'/><polyline points='25,12 29,16 25,20'/></g><g stroke='${fg}' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round' fill='none'><line x1='16' y1='3' x2='16' y2='29'/><polyline points='12,7 16,3 20,7'/><polyline points='12,25 16,29 20,25'/><line x1='3' y1='16' x2='29' y2='16'/><polyline points='7,12 3,16 7,20'/><polyline points='25,12 29,16 25,20'/></g><circle cx='16' cy='16' r='3' fill='${accent}' stroke='${halo}' stroke-width='1'/></svg>`;
      return {
        cursor: `url("data:image/svg+xml,${panSvg}") 16 16, move`,
      };
    }

    // High-visibility CAD crosshair with central aperture / pickbox & center red target dot
    const crossSvg = `<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'><g stroke='${halo}' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round' fill='none'><line x1='16' y1='1' x2='16' y2='10'/><line x1='16' y1='22' x2='16' y2='31'/><line x1='1' y1='16' x2='10' y2='16'/><line x1='22' y1='16' x2='31' y2='16'/><rect x='11' y='11' width='10' height='10'/></g><g stroke='${fg}' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' fill='none'><line x1='16' y1='1' x2='16' y2='10'/><line x1='16' y1='22' x2='16' y2='31'/><line x1='1' y1='16' x2='10' y2='16'/><line x1='22' y1='16' x2='31' y2='16'/><rect x='11' y='11' width='10' height='10'/></g><circle cx='16' cy='16' r='2' fill='${accent}' stroke='${halo}' stroke-width='0.75'/></svg>`;
    return {
      cursor: `url("data:image/svg+xml,${crossSvg}") 16 16, crosshair`,
    };
  }, [isDark, isDragging]);

  return (
    <div
      ref={containerRef}
      className={`relative flex h-full w-full flex-col overflow-hidden select-none transition-colors duration-200 ${
        isDark ? 'bg-slate-950 text-slate-100' : 'bg-white text-slate-800'
      }`}
    >
      <DxfControls
        result={result}
        isDark={isDark}
        setIsDark={setIsDark}
        isFullscreen={isFullscreen}
        toggleFullscreen={toggleFullscreen}
        currentZoomPercent={currentZoomPercent}
        zoomIn={zoomIn}
        zoomOut={zoomOut}
        fitToView={fitToView}
        focusTrackInfo={focusTrackInfo}
        reset1to1={reset1to1}
        layersVisible={layersVisible}
        toggleLayer={toggleLayer}
        onDownloadDxf={onDownloadDxf}
        onDownloadPng={onDownloadPng}
        onDownloadJson={onDownloadJson}
        isTrimmed={isTrimmed}
        onToggleTrim={onToggleTrim}
        busy={busy}
      />

      {/* Main Canvas Viewport Area */}
      <div
        style={cursorStyle}
        className="relative flex-1 overflow-hidden"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onDoubleClick={handleDoubleClick}
      >
        {activeSvg ? (
          <div
            className="h-full w-full pointer-events-none"
            dangerouslySetInnerHTML={{ __html: activeSvg }}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center p-6 sm:p-10 text-center overflow-y-auto cursor-default">
            <div
              className={`w-full max-w-2xl rounded-2xl border p-6 sm:p-8 shadow-xl transition-all ${
                isDark
                  ? 'border-slate-800 bg-slate-900/80 backdrop-blur-md text-slate-200'
                  : 'border-slate-200 bg-white/95 backdrop-blur-md text-slate-800 shadow-[var(--shadow)]'
              }`}
            >
              {/* Header Badge & Title */}
              <div className="flex flex-col items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold bg-[rgba(50,95,244,0.12)] text-[var(--accent)] border border-[var(--border)]">
                  <span className="h-2 w-2 rounded-full bg-[var(--accent)] animate-pulse" />
                  Engineering Scale Plan (ESP) Studio
                </span>
                <h2 className="text-xl sm:text-2xl font-bold tracking-tight">
                  Welcome to Railway ESP Generator
                </h2>
                <p className={`max-w-lg text-xs sm:text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Convert real-world KML railway alignment surveys into CAD-accurate DXF Engineering Scale Plans with automatic turnouts, loops, platforms, and chainages.
                </p>
              </div>

              {/* 3 Step Onboarding Cards */}
              <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3.5 text-left">
                <div
                  className={`rounded-xl border p-3.5 transition-all ${
                    isDark ? 'border-slate-800 bg-slate-950/60' : 'border-slate-100 bg-[var(--surface-soft)]'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent)] text-white text-xs font-bold">1</span>
                    <span className="text-xs font-semibold text-[var(--text-primary)]">Upload KML</span>
                  </div>
                  <p className={`text-[11.5px] leading-snug ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    Upload your raw track survey in Section 1 on the left sidebar.
                  </p>
                </div>

                <div
                  className={`rounded-xl border p-3.5 transition-all ${
                    isDark ? 'border-slate-800 bg-slate-950/60' : 'border-slate-100 bg-[var(--surface-soft)]'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent-start)] text-white text-xs font-bold">2</span>
                    <span className="text-xs font-semibold text-[var(--text-primary)]">Confirm Main Line</span>
                  </div>
                  <p className={`text-[11.5px] leading-snug ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    Inspect candidate paths and confirm the continuous Main Line alignment.
                  </p>
                </div>

                <div
                  className={`rounded-xl border p-3.5 transition-all ${
                    isDark ? 'border-slate-800 bg-slate-950/60' : 'border-slate-100 bg-[var(--surface-soft)]'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent-end)] text-white text-xs font-bold">3</span>
                    <span className="text-xs font-semibold text-[var(--text-primary)]">Generate DXF</span>
                  </div>
                  <p className={`text-[11.5px] leading-snug ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    Configure loops & platforms, then click &quot;Generate DXF Drawing&quot;.
                  </p>
                </div>
              </div>

              {/* Sample Station CTA */}
              {onLoadDemo && (
                <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3 pt-2 border-t border-[var(--border)]">
                  <button
                    type="button"
                    onClick={onLoadDemo}
                    className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--accent-start)] via-[var(--accent)] to-[var(--accent-strong)] hover:opacity-95 px-5 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-md shadow-[rgba(50,95,244,0.3)] transition-all cursor-pointer transform hover:-translate-y-0.5"
                  >
                    <span>⚡ Try Sample Station Demo</span>
                  </button>
                  <span className={`text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    No KML ready? Click above to preview a working station immediately.
                  </span>
                </div>
              )}

              {/* Canvas Controls Summary */}
              <div
                className={`mt-5 flex flex-wrap items-center justify-center gap-4 text-[11px] font-mono pt-3 border-t ${
                  isDark ? 'border-slate-800/80 text-slate-400' : 'border-slate-100 text-slate-500'
                }`}
              >
                <span>🖱️ <b>Pan:</b> Drag left-click</span>
                <span>🔍 <b>Zoom:</b> Scroll wheel or +/-</span>
                <span>🎯 <b>Reset:</b> Double-click / Fit</span>
                <span>🎨 <b>Layers:</b> Toggle in toolbar</span>
              </div>
            </div>
          </div>
        )}

        {/* Loading Overlay */}
        {busy && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-2.5 bg-slate-950/70 backdrop-blur-xs text-white">
            <div className="h-7 w-7 animate-spin rounded-full border-3 border-sky-400 border-t-transparent" />
            <span className="text-xs font-medium tracking-wide">Generating drawing...</span>
          </div>
        )}
      </div>

      {/* Status Footer */}
      <div
        className={`z-10 flex h-6 shrink-0 items-center justify-between border-t px-3 font-mono text-[10px] transition-colors ${
          isDark
            ? 'border-slate-800 bg-slate-900/90 text-slate-400'
            : 'border-slate-200 bg-white/90 text-slate-500 shadow-2xs'
        }`}
      >
        <div className="flex items-center gap-3">
          {mouseCoord ? (
            <span>
              X: {mouseCoord.x.toFixed(2)}m &nbsp; Y: {mouseCoord.y.toFixed(2)}m
            </span>
          ) : (
            <span>Hover to track coordinates</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>Pan: Drag left-click</span>
          <span>•</span>
          <span>Zoom: Scroll wheel</span>
        </div>
      </div>
    </div>
  );
}
