export function StatusBanner({ status }) {
  if (!status || status.kind === 'idle') return null;
  if (status.kind === 'busy')
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[rgba(50,95,244,0.06)] px-3 py-2 text-xs text-[var(--accent)] shadow-2xs flex items-center gap-2">
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent shrink-0" />
        <span className="font-medium">Generating DXF on the backend…</span>
      </div>
    );
  if (status.kind === 'ok')
    return (
      <div className="rounded-xl border border-emerald-500/25 bg-emerald-50/80 px-3 py-2 text-xs text-emerald-800 shadow-2xs">
        <span className="font-semibold">Ready:</span> <b>{status.filename}</b>
      </div>
    );
  return (
    <div className="rounded-xl border border-rose-500/25 bg-rose-50/80 px-3 py-2 text-xs text-rose-800 shadow-2xs">
      <p className="font-semibold mb-1">Please fix the following:</p>
      <ul className="list-disc space-y-0.5 pl-4 text-[11px]">
        {status.messages.map((m, i) => (
          <li key={i}>{m}</li>
        ))}
      </ul>
    </div>
  );
}
