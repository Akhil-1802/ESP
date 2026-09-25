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
}) {
  const containerRef = useRef(null);

  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, vbX: 0, vbY: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDark, setIsDark] = useState(true);
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

    const padFactor = 1.06;
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

  // Initial fitted viewBox derived directly during render
  const initialViewBox = useMemo(() => {
    if (!result || !result.w || !result.h) return null;
    const padFactor = 1.06;
    const rawW = result.w * padFactor;
    const rawH = result.h * padFactor;
    const ar = 16 / 9;
    const rawAR = rawW / rawH;
    const fitW = rawAR > ar ? rawW : rawH * ar;
    const fitH = rawAR > ar ? rawW / ar : rawH;
    const fitX = result.x0 - (fitW - result.w) / 2;
    const fitY = result.y0 - (fitH - result.h) / 2;
    return { x: fitX, y: fitY, w: fitW, h: fitH, baseW: fitW, baseH: fitH };
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
      const minW = Math.max(result.w * 0.002, 2);
      const maxW = result.w * 8;
      const nextW = Math.min(Math.max(prev.w / factor, minW), maxW);
      const nextH = prev.h * (nextW / prev.w);

      const nextX = prev.x + centerXRatio * (prev.w - nextW);
      const nextY = prev.y + centerYRatio * (prev.h - nextH);

      return { ...prev, x: nextX, y: nextY, w: nextW, h: nextH };
    });
  };

  const zoomIn = () => zoomByFactor(1.35);
  const zoomOut = () => zoomByFactor(1 / 1.35);
  const reset1to1 = () => fitToView();

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
      const vbStr = `viewBox="${viewBox.x.toFixed(3)} ${viewBox.y.toFixed(3)} ${viewBox.w.toFixed(3)} ${viewBox.h.toFixed(3)}" preserveAspectRatio="none"`;
      s = s.replace(/viewBox="[^"]*"\s*(preserveAspectRatio="[^"]*")?/, vbStr);
      s = s.replace(/width="[^"]*"/, 'width="100%"');
      s = s.replace(/height="[^"]*"/, 'height="100%"');
    }

    const bgFill = isDark ? '#0a0e17' : '#f8fafc';
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
      hiddenRules.push('.cad-text { display: none !important; }');
    }

    const dynamicStyle = `
      <style>
        .cad-bg { fill: ${bgFill} !important; }
        .cad-geom line, .cad-geom path, .cad-geom circle { vector-effect: non-scaling-stroke; stroke-linecap: round; stroke-linejoin: round; }
        .cad-text text { font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: ${textColor}; stroke: ${textHalo}; }
        ${hiddenRules.join('\n')}
      </style>
    `;

    s = s.replace(/<style>[\s\S]*?<\/style>/, dynamicStyle);
    return s;
  }, [result, viewBox, isDark, layersVisible]);

  return (
    <div
      ref={containerRef}
      className={`relative flex h-full w-full flex-col overflow-hidden select-none transition-colors duration-200 ${
        isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-100 text-slate-800'
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
        reset1to1={reset1to1}
        layersVisible={layersVisible}
        toggleLayer={toggleLayer}
        onDownloadDxf={onDownloadDxf}
        onDownloadPng={onDownloadPng}
        onDownloadJson={onDownloadJson}
      />

      {/* Main Canvas Viewport Area */}
      <div
        className="relative flex-1 cursor-grab overflow-hidden active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {activeSvg ? (
          <div
            className="h-full w-full pointer-events-none"
            dangerouslySetInnerHTML={{ __html: activeSvg }}
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-slate-400">
            <div className="rounded-2xl border border-dashed border-slate-700 p-6">
              <svg className="mx-auto h-12 w-12 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium">No drawing loaded yet</p>
            <p className="max-w-xs text-xs text-slate-500">
              Configure parameters on the left and click &quot;Generate DXF&quot;, or load the standard railway station sample.
            </p>
            {onLoadDemo && (
              <button
                type="button"
                onClick={onLoadDemo}
                className="mt-2 rounded-lg bg-sky-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-sky-500 transition-colors cursor-pointer"
              >
                Load Sample Station
              </button>
            )}
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
