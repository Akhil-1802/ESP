import { useState } from 'react';

/** Shared form primitives: cards, labeled inputs, list helpers. */

export function Section({ id, title, hint, count, onAdd, addLabel, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section id={id} className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden transition-all">
      <div
        className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-3.5 py-2.5 bg-slate-50/70 cursor-pointer select-none hover:bg-slate-100/80 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span
          className="text-slate-400 hover:text-slate-600 transition-transform duration-200 inline-flex items-center justify-center w-4 h-4"
          style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}
        >
          <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
            <path d="M6 4l8 6-8 6V4z" />
          </svg>
        </span>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {typeof count === 'number' && (
          <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-xs font-medium text-slate-700">
            {count}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {onAdd && (
            <button
              type="button"
              onClick={onAdd}
              className="rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-700 transition-colors shadow-sm"
            >
              {addLabel || '+ Add'}
            </button>
          )}
        </div>
      </div>
      {open && (
        <div className="space-y-3.5 px-3.5 py-3.5 text-sm">
          {hint && <p className="text-xs text-slate-500 leading-relaxed">{hint}</p>}
          {children}
        </div>
      )}
    </section>
  );
}

export function ItemCard({ title, onRemove, children }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-700">{title}</span>
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto rounded-md px-2 py-0.5 text-sm text-red-600 hover:bg-red-50"
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
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-[11px] leading-snug text-slate-400">{hint}</span>}
    </label>
  );
}

const inputCls =
  'w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none transition-colors';

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
