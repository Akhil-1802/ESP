import { useState } from 'react';

export function JsonViewer({
  liveConfigText,
  resultConfigText,
  onCopy,
  onDownload,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState('live'); // 'live' | 'result'
  const [copied, setCopied] = useState(false);
  const [showDefaults, setShowDefaults] = useState(false);

  const displayedText = activeTab === 'result' && resultConfigText ? resultConfigText : liveConfigText;
  const lineCount = (displayedText || '').split('\n').length;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displayedText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onCopy?.(displayedText);
    } catch {
      // Fallback handled by parent if needed
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-[var(--surface)] text-[var(--text-primary)] border-l border-[var(--border)] text-xs">
      {/* Panel Header - Compact */}
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-[var(--border)] px-2.5 bg-[var(--surface)]">
        <div className="flex items-center gap-1.5 min-w-0">
          <svg className="h-3.5 w-3.5 text-[var(--accent)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-primary)] truncate">
            JSON
          </span>
          <span className="rounded bg-[rgba(50,95,244,0.08)] border border-[var(--border)] px-1.5 py-0.2 font-mono text-[9px] font-semibold text-[var(--accent)]">
            {lineCount}L
          </span>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={handleCopy}
            className={`flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors cursor-pointer ${
              copied
                ? 'bg-[var(--accent)] text-white'
                : 'border border-[var(--border)] bg-[var(--surface-soft)] text-[var(--text-secondary)] hover:text-[var(--accent)] hover:border-[var(--accent)]'
            }`}
            title="Copy JSON to clipboard"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>

          <button
            type="button"
            onClick={onDownload}
            className="flex items-center gap-1 rounded border border-[var(--border)] bg-[var(--surface-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition-colors cursor-pointer"
            title="Download inputconfig.json"
          >
            .json
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded p-0.5 text-[var(--text-muted)] hover:bg-[var(--surface-soft)] hover:text-[var(--text-primary)]"
              title="Close JSON panel"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      {resultConfigText && (
        <div className="flex border-b border-[var(--border)] bg-[var(--surface-soft)] px-2 pt-1 text-[11px]">
          <button
            type="button"
            onClick={() => setActiveTab('live')}
            className={`border-b-2 px-2 py-1 font-medium transition-colors cursor-pointer ${
              activeTab === 'live'
                ? 'border-[var(--accent)] text-[var(--accent)] font-semibold'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            Live Input
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('result')}
            className={`border-b-2 px-2 py-1 font-medium transition-colors cursor-pointer ${
              activeTab === 'result'
                ? 'border-[var(--accent)] text-[var(--accent)] font-semibold'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            Result DXF
          </button>
        </div>
      )}

      {/* Code Area - Compact spacing */}
      <div className="flex-1 overflow-auto p-2.5 font-mono text-[10px] leading-snug bg-[#0f172a] text-sky-200/90 selection:bg-[var(--accent)] selection:text-white">
        <pre className="text-sky-300 whitespace-pre-wrap break-all font-mono">
          {displayedText}
        </pre>
      </div>

      {/* Collapsible Defaults Cheatsheet - Compact */}
      <div className="border-t border-slate-800 bg-slate-950/90">
        <button
          type="button"
          onClick={() => setShowDefaults(!showDefaults)}
          className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-[10.5px] font-medium text-slate-400 hover:bg-slate-800/50 transition-colors cursor-pointer"
        >
          <span className="font-semibold text-slate-300">Engineering Defaults</span>
          <span className="text-[9px] text-slate-500">{showDefaults ? '▲ hide' : '▼ show'}</span>
        </button>

        {showDefaults && (
          <div className="px-2.5 pb-2 pt-0.5 text-[10px] leading-relaxed text-slate-400 space-y-0.5">
            <p>
              <strong className="text-slate-300">Loop spacing:</strong> 5.3 m · <strong className="text-slate-300">Turnout:</strong> 1:12
            </p>
            <p>
              <strong className="text-slate-300">Blank C1/C2:</strong> 750 m loop centered on MAIN
            </p>
            <p>
              <strong className="text-slate-300">Overruns:</strong> 120 m each side
            </p>
            <p>
              <strong className="text-slate-300">Platform:</strong> 550 × 7.0 m + 10 m stairs
            </p>
            <p>
              <strong className="text-slate-300">FOB:</strong> 3.0 m width, 6.25 m clearance
            </p>
            <p>
              <strong className="text-slate-300">Station:</strong> 40 × 10 m
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
