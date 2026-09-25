export function StatusBanner({ status }) {
  if (!status || status.kind === 'idle') return null;
  if (status.kind === 'busy')
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800 shadow-sm flex items-center gap-2">
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-sky-600 border-t-transparent shrink-0" />
        <span>Generating DXF on the backend…</span>
      </div>
    );
  if (status.kind === 'ok')
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 shadow-sm">
        <span className="font-semibold">Ready:</span> <b>{status.filename}</b>
      </div>
    );
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 shadow-sm">
      <p className="font-semibold mb-1">Please fix the following:</p>
      <ul className="list-disc space-y-0.5 pl-4 text-[11px]">
        {status.messages.map((m, i) => (
          <li key={i}>{m}</li>
        ))}
      </ul>
    </div>
  );
}
