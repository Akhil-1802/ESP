import React from 'react';

export function QuickGuideModal({ isOpen, onClose, onLoadDemo }) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative flex flex-col w-full max-w-2xl max-h-[90vh] rounded-2xl bg-[var(--surface)] text-[var(--text-primary)] border border-[var(--border)] shadow-[var(--shadow)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)] bg-[var(--surface-soft)]">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgba(50,95,244,0.12)] text-[var(--accent)] text-lg">
              📖
            </span>
            <div>
              <h2 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
                Railway ESP Generator — Quick Guide
              </h2>
              <p className="text-[11px] text-[var(--text-muted)]">
                Beginner walkthrough for creating CAD Engineering Scale Plans
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface)] text-sm transition-colors cursor-pointer"
            aria-label="Close guide"
          >
            ✕
          </button>
        </div>

        {/* Modal Body (Scrollable) */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 text-xs sm:text-sm">
          {/* Quick Overview */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-soft)] p-3.5 space-y-1.5">
            <h3 className="font-semibold text-xs text-[var(--accent)] uppercase tracking-wider">
              What does this project do?
            </h3>
            <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed">
              This application converts raw <b>KML track survey alignments</b> into professional, CAD-accurate <b>DXF Engineering Scale Plans (ESP)</b> compliant with railway standards. It automatically calculates station chainages, turnouts, loop lines, island platforms, and foot overbridges.
            </p>
          </div>

          {/* Workflow Steps */}
          <div className="space-y-3">
            <h3 className="font-bold text-xs uppercase tracking-wider text-[var(--text-primary)]">
              5-Step Creation Process
            </h3>

            {/* Step 1 */}
            <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] p-3 hover:border-[var(--accent)] transition-colors">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent)] text-white text-xs font-bold mt-0.5">
                1
              </span>
              <div className="space-y-0.5">
                <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                  Upload KML Alignment File
                </h4>
                <p className="text-[11.5px] text-[var(--text-secondary)] leading-relaxed">
                  Upload your survey <code className="rounded bg-slate-100 px-1 py-0.5 text-slate-800">.kml</code> in Section 1. The system automatically reads the 3D track paths, segments, and lengths.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] p-3 hover:border-[var(--accent)] transition-colors">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent-start)] text-white text-xs font-bold mt-0.5">
                2
              </span>
              <div className="space-y-0.5">
                <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                  Confirm Continuous Main Line
                </h4>
                <p className="text-[11.5px] text-[var(--text-secondary)] leading-relaxed">
                  In the <b>KML Track Alignment Selection</b> card, confirm the longest continuous track as your <b>Main Line</b>. You can click <i>&quot;View Alignment with Chainages&quot;</i> to visually verify 100m ticks and station flags.
                </p>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] p-3 hover:border-[var(--accent)] transition-colors">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent-mid)] text-white text-xs font-bold mt-0.5">
                3
              </span>
              <div className="space-y-0.5">
                <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                  Set Station Datum &amp; Reference Chainage
                </h4>
                <p className="text-[11.5px] text-[var(--text-secondary)] leading-relaxed">
                  Define your Station Centre chainage (e.g., Station building location).
                </p>
                <div className="mt-1 rounded-md bg-amber-500/10 border border-amber-500/20 p-2 text-[11px] text-amber-800">
                  ⚠️ <b>Straight Track Requirement:</b> Railway loop turnouts require a straight stretch of track (minimum 550m to 686m CSR). Ensure your station datum is located on a straight track segment.
                </div>
              </div>
            </div>

            {/* Step 4 */}
            <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] p-3 hover:border-[var(--accent)] transition-colors">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent-end)] text-white text-xs font-bold mt-0.5">
                4
              </span>
              <div className="space-y-0.5">
                <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                  Configure Loops, Platforms &amp; Structures
                </h4>
                <p className="text-[11.5px] text-[var(--text-secondary)] leading-relaxed">
                  Add <b>Loop lines</b> (standard track spacing is 5.30 m, turnouts 1 in 8.5 or 1 in 12), passenger <b>Platforms</b>, and <b>Foot Overbridges (FOB)</b>.
                </p>
              </div>
            </div>

            {/* Step 5 */}
            <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] p-3 hover:border-[var(--accent)] transition-colors">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[var(--accent-strong)] text-white text-xs font-bold mt-0.5">
                5
              </span>
              <div className="space-y-0.5">
                <h4 className="font-semibold text-xs text-[var(--text-primary)]">
                  Generate DXF &amp; Export
                </h4>
                <p className="text-[11.5px] text-[var(--text-secondary)] leading-relaxed">
                  Click <b>Generate DXF Drawing</b>. View the live drawing in the canvas with red CAD strokes. Toggle CAD layers or export as <b>.DXF</b> (AutoCAD / Civil 3D), <b>.PNG</b> image, or <b>.JSON</b> config.
                </p>
              </div>
            </div>
          </div>

          {/* Canvas Navigation Quick Reference */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-soft)] p-3 space-y-1.5 font-mono text-[11px]">
            <span className="font-bold text-[var(--text-primary)] uppercase tracking-wider block font-sans text-xs">
              Canvas Navigation Shortcuts
            </span>
            <div className="grid grid-cols-2 gap-2 text-[var(--text-secondary)]">
              <div>🖱️ <b>Pan:</b> Left-click and drag</div>
              <div>🔍 <b>Zoom:</b> Scroll wheel or +/-</div>
              <div>🎯 <b>Reset View:</b> Double-click / Fit</div>
              <div>🎨 <b>CAD Layers:</b> Top right toggles</div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-[var(--border)] bg-[var(--surface-soft)]">
          {onLoadDemo && (
            <button
              type="button"
              onClick={() => {
                onClose();
                onLoadDemo();
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[rgba(50,95,244,0.12)] border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--accent)] hover:bg-[rgba(50,95,244,0.2)] transition-colors cursor-pointer"
            >
              <span>⚡ Load Sample Station</span>
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="ml-auto inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-[var(--accent-start)] to-[var(--accent)] hover:from-[var(--accent-strong)] hover:to-[var(--accent-strong)] px-4 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors cursor-pointer"
          >
            Got it, Let&apos;s Start!
          </button>
        </div>
      </div>
    </div>
  );
}

