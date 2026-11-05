import { useState } from 'react';

/** Shared form primitives: cards, labeled inputs, list helpers. */

export function Section({ id, title, hint, count, onAdd, addLabel, actions, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section id={id} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[0_2px_12px_rgba(25,49,104,0.04)] overflow-hidden transition-all">
      <div
        className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] px-3.5 py-2.5 bg-[var(--surface-soft)] cursor-pointer select-none hover:bg-[rgba(50,95,244,0.04)] transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span
          className="text-[var(--text-muted)] hover:text-[var(--accent)] transition-transform duration-200 inline-flex items-center justify-center w-4 h-4"
          style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}
        >
          <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
            <path d="M6 4l8 6-8 6V4z" />
          </svg>
        </span>
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
        {typeof count === 'number' && (
          <span className="rounded-full bg-[rgba(50,95,244,0.08)] border border-[var(--border)] px-2 py-0.5 text-xs font-semibold text-[var(--accent)]">
            {count}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {actions}
          {onAdd && (
            <button
              type="button"
              onClick={onAdd}
              className="rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] px-2.5 py-1 text-xs font-semibold text-white transition-colors shadow-xs cursor-pointer"
            >
              {addLabel || '+ Add'}
            </button>
          )}
        </div>
      </div>
      {open && (
        <div className="space-y-3.5 px-3.5 py-3.5 text-sm">
          {hint && <p className="text-xs text-[var(--text-muted)] leading-relaxed">{hint}</p>}
          {children}
        </div>
      )}
    </section>
  );
}

export function ItemCard({ title, onRemove, children }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-soft)] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm font-semibold text-[var(--text-primary)]">{title}</span>
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto rounded-md px-2 py-0.5 text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
          title="Remove"
        >
          Remove
        </button>
      </div>
      {children}
    </div>
  );
}

export function Grid({ cols, children }) {
  const colCls = cols === 1 ? 'grid-cols-1' : cols === 3 ? 'grid-cols-1 sm:grid-cols-3' : 'grid-cols-1 sm:grid-cols-2';
  return <div className={`grid gap-2.5 ${colCls}`}>{children}</div>;
}

export function Field({ label, hint, span2, children }) {
  return (
    <label className={`block ${span2 ? 'col-span-full' : ''}`}>
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-[11px] leading-snug text-[var(--text-muted)]">{hint}</span>}
    </label>
  );
}

const inputCls =
  'w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[rgba(50,95,244,0.15)] focus:outline-none transition-all';

export function Text(props) {
  return <input type="text" className={inputCls} {...props} />;
}

export function Num(props) {
  return <input type="number" step="any" min={props.min} className={inputCls} {...props} />;
}

export function Sel({ options, ...props }) {
  return (
    <select className={inputCls} {...props}>
      {options.map((o) =>
        typeof o === 'string' ? (
          <option key={o} value={o}>
            {o}
          </option>
        ) : (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ),
      )}
    </select>
  );
}

export function Check({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-700">
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-slate-300 accent-slate-900"
      />
      {label}
    </label>
  );
}

export function Empty({ children }) {
  return (
    <p className="rounded-lg border border-dashed border-slate-300 bg-white px-3 py-4 text-center text-sm text-slate-400">
      {children}
    </p>
  );
}
