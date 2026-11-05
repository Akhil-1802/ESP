import { useState, useMemo } from 'react';

export function TrackSelectionPanel({
  candidateTracks = [],
  selectedTrackId,
  confirmedTrackId,
  onSelectTrack,
  onConfirmMainLine,
}) {
  const [classifications, setClassifications] = useState({});

  const topTracks = useMemo(() => {
    return (candidateTracks || []).slice(0, 4);
  }, [candidateTracks]);

  const activeTrack = useMemo(() => {
    return (
      topTracks.find((t) => t.candidate_id === selectedTrackId) ||
      topTracks[0] ||
      null
    );
  }, [topTracks, selectedTrackId]);

  const updateClassification = (candId, value) => {
    setClassifications((prev) => ({ ...prev, [candId]: value }));
  };

  if (!topTracks || topTracks.length === 0) {
    return null;
  }

  return (
    <div className="col-span-full rounded-xl border border-[var(--border)] bg-[var(--surface-soft)] p-3.5 space-y-3 shadow-[var(--shadow)]">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] pb-2.5">
        <div className="flex items-center gap-2">
          <span className="text-base">🛤️</span>
          <div>
            <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wide">
              KML Track Alignment Selection
            </span>
            <span className="ml-2 rounded-full bg-[rgba(50,95,244,0.08)] border border-[var(--border)] px-2 py-0.5 text-[10px] font-semibold text-[var(--accent)]">
              {topTracks.length} Candidate Paths (Top Distances)
            </span>
          </div>
        </div>
        <span className="text-[11px] text-[var(--text-secondary)]">
          Select and confirm the continuous Main Line alignment for ESP generation.
        </span>
      </div>

      {/* Candidate List - Full Width */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[11px] font-semibold text-[var(--text-muted)] px-1">
          <span>Candidate Track & CAD Entity</span>
          <span>Length · Segments · Classification</span>
        </div>

        <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
          {topTracks.map((cand) => {
            const isSelected = activeTrack?.candidate_id === cand.candidate_id;
            const isConfirmed = confirmedTrackId === cand.candidate_id;
            const currentClass =
              classifications[cand.candidate_id] ||
              (isConfirmed ? 'Main Line' : cand.classification);

            return (
              <div
                key={cand.candidate_id}
                onClick={() => onSelectTrack && onSelectTrack(cand)}
                className={`rounded-lg border p-2.5 text-xs transition-all cursor-pointer select-none ${
                  isSelected
                    ? 'border-[var(--accent)] bg-white shadow-sm ring-2 ring-[rgba(50,95,244,0.18)]'
                    : 'border-[var(--border)] bg-white/90 hover:bg-white hover:border-[var(--accent)]'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {/* Left: Name & CAD Handle */}
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className="w-3.5 h-3.5 rounded-full flex-shrink-0 border border-slate-300 shadow-xs"
                      style={{ backgroundColor: cand.color }}
                      title={`Palette color: ${cand.color}`}
                    />
                    <div className="truncate">
                      <span className="font-bold text-[var(--text-primary)] text-xs">
                        {cand.name}
                      </span>
                      {cand.cad_name && (
                        <span className="ml-1.5 font-mono text-[11px] text-[var(--text-muted)] bg-[var(--surface-soft)] border border-[var(--border)] rounded px-1.5 py-0.5">
                          {cand.cad_name}
                        </span>
                      )}
                      <span className="ml-2 text-[10.5px] text-[var(--text-muted)]">
                        ({cand.segment_count} {cand.segment_count === 1 ? 'seg' : 'segs'})
                      </span>
                    </div>
                  </div>

                  {/* Right: Length Badge & Status */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="font-mono font-bold text-[var(--text-primary)] bg-[var(--surface-soft)] border border-[var(--border)] rounded px-2 py-0.5 text-xs">
                      {cand.length_m.toFixed(2)} m
                    </span>
                    {isConfirmed && (
                      <span className="rounded bg-emerald-50 border border-emerald-300 px-2 py-0.5 text-[10.5px] font-bold text-emerald-700">
                        ✓ MAIN
                      </span>
                    )}
                  </div>
                </div>

                {/* Classification Controls */}
                <div className="mt-2 flex items-center justify-between gap-2 pt-1.5 border-t border-[var(--border)]">
                  <span className="text-[11px] font-medium text-[var(--text-muted)]">
                    Role in Layout:
                  </span>
                  <div className="flex items-center gap-2">
                    <select
                      value={currentClass}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateClassification(cand.candidate_id, e.target.value)}
                      className="rounded border border-[var(--border)] bg-white px-2 py-1 text-xs font-medium text-[var(--text-secondary)] hover:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] focus:outline-none"
                    >
                      <option value="Main Line">Main Line</option>
                      <option value="Loop Line">Loop Line</option>
                      <option value="Siding">Siding</option>
                      <option value="Other">Other / Unclassified</option>
                      <option value="Ignore">Ignore</option>
                    </select>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectTrack && onSelectTrack(cand);
                        onConfirmMainLine && onConfirmMainLine(cand);
                      }}
                      className={`rounded px-2.5 py-1 text-xs font-semibold shadow-xs transition-colors cursor-pointer ${
                        isConfirmed
                          ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                          : 'bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]'
                      }`}
                    >
                      {isConfirmed ? '✓ Main Line' : 'Select as Main'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Confirmation Banner */}
      {activeTrack && (
        <div className="pt-1">
          <button
            type="button"
            onClick={() => onConfirmMainLine && onConfirmMainLine(activeTrack)}
            className={`w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-xs font-bold shadow-sm transition-all cursor-pointer ${
              confirmedTrackId === activeTrack.candidate_id
                ? 'bg-emerald-600 text-white hover:bg-emerald-500 ring-2 ring-emerald-400/50'
                : 'bg-gradient-to-r from-[var(--accent-start)] to-[var(--accent)] text-white hover:from-[var(--accent-strong)] hover:to-[var(--accent-strong)]'
            }`}
          >
            <span>
              {confirmedTrackId === activeTrack.candidate_id
                ? '✓ Confirmed as Main Line'
                : '✓ Confirm Selected Track as Main Line'}
            </span>
            <span className="font-normal opacity-90">
              ({activeTrack.name}
              {activeTrack.cad_name ? ` · ${activeTrack.cad_name}` : ''} ·{' '}
              {activeTrack.length_m.toFixed(2)} m)
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
