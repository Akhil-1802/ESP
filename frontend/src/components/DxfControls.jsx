/**
 * Viewport toolbars, zoom controls, export buttons, and layer toggles.
 */

export function DxfControls({
  result,
  isDark,
  setIsDark,
  isFullscreen,
  toggleFullscreen,
  currentZoomPercent,
  zoomIn,
  zoomOut,
  fitToView,
  focusTrackInfo,
  reset1to1,
  layersVisible,
  toggleLayer,
  onDownloadDxf,
  onDownloadPng,
  onDownloadJson,
  isTrimmed = false,
  onToggleTrim = null,
  busy = false,
}) {
  return (
    <>
      {/* Top Header / Viewport Toolbar */}
      <div
        className={`z-10 flex h-10 shrink-0 items-center justify-between border-b px-3 backdrop-blur-md transition-colors ${
          isDark
            ? 'border-slate-800 bg-slate-900/90 text-slate-100'
            : 'border-slate-200 bg-white text-slate-800 shadow-xs'
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 ring-4 ring-emerald-500/20" />
            <span className="text-[11px] font-bold uppercase tracking-wider">
              CAD Canvas
            </span>
          </div>

          {result ? (
            <div className="flex items-center gap-2 border-l border-slate-700/50 pl-2.5 min-w-0">
              <span className="max-w-[180px] truncate text-xs font-medium" title={result.filename}>
                {result.filename}
              </span>
              {result.entities > 0 && (
                <span
                  className={`rounded px-1.5 py-0.2 font-mono text-[10px] ${
                    isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {result.entities} entities
                </span>
              )}
            </div>
          ) : (
            <span className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Ready — awaiting generation
            </span>
          )}
        </div>

        {/* View Controls & Action Buttons */}
        <div className="flex items-center gap-1.5 shrink-0">
          {result && result.svg && (
            <>
              {/* Zoom controls */}
              <div
                className={`flex items-center rounded-lg border p-0.5 ${
                  isDark ? 'border-slate-700 bg-slate-800/90' : 'border-slate-300 bg-slate-100'
                }`}
              >
                <button
                  type="button"
                  onClick={zoomOut}
                  className={`flex h-6 w-6 items-center justify-center rounded text-xs font-semibold cursor-pointer ${
                    isDark ? 'text-slate-300 hover:bg-slate-700 hover:text-white' : 'text-slate-700 hover:bg-slate-200'
                  }`}
                  title="Zoom Out"
                >
                  −
                </button>
                <span className="w-11 text-center font-mono text-[10.5px] font-medium">
                  {currentZoomPercent}%
                </span>
                <button
                  type="button"
                  onClick={zoomIn}
                  className={`flex h-6 w-6 items-center justify-center rounded text-xs font-semibold cursor-pointer ${
                    isDark ? 'text-slate-300 hover:bg-slate-700 hover:text-white' : 'text-slate-700 hover:bg-slate-200'
                  }`}
                  title="Zoom In"
                >
                  +
                </button>
              </div>

              {focusTrackInfo && (
                <button
                  type="button"
                  onClick={() => focusTrackInfo(3.8)}
                  className={`rounded-lg border px-2.5 py-1 text-xs font-semibold cursor-pointer transition-colors shadow-2xs flex items-center gap-1 ${
                    isDark
                      ? 'border-emerald-500/50 bg-emerald-950/60 text-emerald-300 hover:bg-emerald-900/80 hover:text-emerald-100'
                      : 'border-emerald-600 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                  }`}
                  title="Zoom closely to track parts, eliminating empty blank spaces"
                >
                  <span>🚂</span>
                  <span>Track Parts</span>
                </button>
              )}

              {focusTrackInfo && result?.trackWaypoints && result.trackWaypoints.length > 1 && (
                <div
                  className={`hidden sm:flex items-center gap-0.5 rounded-lg border p-0.5 ${
                    isDark ? 'border-slate-700 bg-slate-800/80' : 'border-slate-300 bg-slate-100'
                  }`}
                  title="Pan camera to specific track segment"
                >
                  {result.trackWaypoints.map((wp, i) => (
                    <button
                      key={wp.name || i}
                      type="button"
                      onClick={() => focusTrackInfo(3.8, wp)}
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium cursor-pointer transition-colors ${
                        isDark
                          ? 'text-slate-300 hover:bg-slate-700 hover:text-white'
                          : 'text-slate-700 hover:bg-slate-200'
                      }`}
                      title={`Focus on track ${wp.name}`}
                    >
                      {wp.name}
                    </button>
                  ))}
                </div>
              )}

              {focusTrackInfo && result?.featureFocus?.hasFeatures && (
                <button
                  type="button"
                  onClick={() => focusTrackInfo(3.8)}
                  className={`rounded-lg border px-2 py-1 text-xs font-medium cursor-pointer transition-colors flex items-center gap-1 ${
                    isDark
                      ? 'border-indigo-500/50 bg-indigo-950/50 text-indigo-300 hover:bg-indigo-900/70 hover:text-indigo-100'
                      : 'border-indigo-400 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                  }`}
                  title="Focus directly onto station yard, platforms, and loops"
                >
                  <span>🚉</span>
                  <span>Station</span>
                </button>
              )}

              <button
                type="button"
                onClick={fitToView}
                className={`rounded-lg border px-2 py-1 text-xs font-medium cursor-pointer transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800/90 text-slate-200 hover:bg-slate-700 hover:text-white'
                    : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
                title="Fit to Screen (full extent)"
              >
                Fit
              </button>

              {focusTrackInfo && (
                <>
                  <button
                    type="button"
                    onClick={() => focusTrackInfo(2.0)}
                    className={`rounded-lg border px-1.5 py-1 text-xs font-mono font-medium cursor-pointer transition-colors ${
                      isDark
                        ? 'border-slate-700 bg-slate-800/90 text-slate-300 hover:bg-slate-700 hover:text-white'
                        : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                    title="Zoom to 200%"
                  >
                    2x
                  </button>
                  <button
                    type="button"
                    onClick={() => focusTrackInfo(4.0)}
                    className={`rounded-lg border px-1.5 py-1 text-xs font-mono font-medium cursor-pointer transition-colors ${
                      isDark
                        ? 'border-slate-700 bg-slate-800/90 text-slate-300 hover:bg-slate-700 hover:text-white'
                        : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                    title="Zoom to 400%"
                  >
                    4x
                  </button>
                  <button
                    type="button"
                    onClick={() => focusTrackInfo(8.0)}
                    className={`rounded-lg border px-1.5 py-1 text-xs font-mono font-medium cursor-pointer transition-colors ${
                      isDark
                        ? 'border-slate-700 bg-slate-800/90 text-slate-300 hover:bg-slate-700 hover:text-white'
                        : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                    title="Zoom to 800%"
                  >
                    8x
                  </button>
                </>
              )}
              <div className={`mx-0.5 h-4 w-[1px] ${isDark ? 'bg-slate-700/50' : 'bg-slate-300'}`} />
            </>
          )}

          {/* Theme toggle */}
          <button
            type="button"
            onClick={() => setIsDark(!isDark)}
            className={`rounded-lg border p-1 text-xs cursor-pointer transition-colors ${
              isDark
                ? 'border-slate-700 bg-slate-800/90 text-amber-300 hover:bg-slate-700'
                : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
            title={isDark ? 'Switch to Light Paper mode' : 'Switch to Dark CAD mode'}
          >
            {isDark ? '☼' : '☾'}
          </button>

          {/* Fullscreen toggle */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className={`rounded-lg border p-1 text-xs cursor-pointer transition-colors ${
              isDark
                ? 'border-slate-700 bg-slate-800/90 text-slate-200 hover:bg-slate-700 hover:text-white'
                : 'border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Canvas'}
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isFullscreen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 9L4 4m0 0l5 0m-5 0l0 5m11 11l5 5m0 0l-5 0m5 0l0-5m-11 0l-5 5m0 0l5 0m-5 0l0-5m11-11l5-5m0 0l-5 0m5 0l0 5" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5h-4m4 0v-4m0 4l-5-5" />
              )}
            </svg>
          </button>

          {/* Export Buttons */}
          {result && (
            <>
              {onToggleTrim && (
                <button
                  type="button"
                  onClick={onToggleTrim}
                  disabled={busy}
                  className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-50 ${
                    isTrimmed
                      ? 'bg-emerald-700 hover:bg-emerald-800 text-white ring-1 ring-emerald-400'
                      : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  }`}
                  title={
                    isTrimmed
                      ? 'Plan is finalized. Click to view full survey extent.'
                      : 'Finalize the engineering scale plan.'
                  }
                >
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{isTrimmed ? 'Plan Finalized' : 'Finalize Plan'}</span>
                </button>
              )}
              <button
                type="button"
                onClick={onDownloadDxf}
                className="flex items-center gap-1 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] px-2.5 py-1 text-xs font-semibold text-white shadow-xs transition-colors cursor-pointer"
                title="Download DXF drawing"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                DXF
              </button>
              <button
                type="button"
                onClick={onDownloadPng}
                disabled={!result.svg}
                className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium transition-colors cursor-pointer disabled:opacity-40 ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700'
                    : 'border-[var(--border)] bg-[var(--surface-soft)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface)]'
                }`}
                title="Export as PNG image"
              >
                PNG
              </button>
              <button
                type="button"
                onClick={onDownloadJson}
                className={`flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700'
                    : 'border-[var(--border)] bg-[var(--surface-soft)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface)]'
                }`}
                title="Download config JSON"
              >
                JSON
              </button>
            </>
          )}
        </div>
      </div>

      {/* Layer Filter Toolbar */}
      {result && result.svg && (
        <div
          className={`z-10 flex h-7 shrink-0 items-center gap-1.5 overflow-x-auto border-b px-3 text-[10.5px] transition-colors ${
            isDark
              ? 'border-slate-800/80 bg-slate-950/70 text-slate-400'
              : 'border-[var(--border)] bg-[var(--surface-soft)] text-[var(--text-secondary)]'
          }`}
        >
          <span className="font-semibold text-[10px] uppercase tracking-wider mr-1 text-slate-500">
            Layers:
          </span>

          {[
            { key: 'track', label: 'Tracks', color: 'bg-sky-400', activeCls: 'bg-sky-500/20 text-sky-400 border-sky-500/40' },
            { key: 'crossover', label: 'Turnouts / Crossovers', color: 'bg-amber-400', activeCls: 'bg-amber-500/20 text-amber-400 border-amber-500/40' },
            { key: 'platform', label: 'Platforms & Stairs', color: 'bg-purple-400', activeCls: 'bg-purple-500/20 text-purple-400 border-purple-500/40' },
            { key: 'station', label: 'Stations', color: 'bg-indigo-400', activeCls: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/40' },
            { key: 'fob', label: 'FOBs', color: 'bg-teal-400', activeCls: 'bg-teal-500/20 text-teal-400 border-teal-500/40' },
            { key: 'signal', label: 'SRJ / Fouling', color: 'bg-rose-400', activeCls: 'bg-rose-500/20 text-rose-400 border-rose-500/40' },
            { key: 'fencing', label: 'Fencing / Boundary', color: 'bg-emerald-400', activeCls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' },
            { key: 'reference', label: 'Reference / Chainage', color: 'bg-slate-400', activeCls: 'bg-slate-500/20 text-slate-300 border-slate-500/40' },
            { key: 'text', label: 'Text Labels', color: 'bg-emerald-400', activeCls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' },
          ].map(({ key, label, color, activeCls }) => (
            <button
              key={key}
              type="button"
              onClick={() => toggleLayer(key)}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 font-medium transition-colors cursor-pointer border ${
                layersVisible[key]
                  ? activeCls
                  : 'opacity-40 hover:opacity-75 border-transparent'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${color}`} />
              {label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
