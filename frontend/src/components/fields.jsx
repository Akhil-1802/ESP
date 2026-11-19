import { createContext, useContext, useEffect, useState } from 'react';

/** Context to broadcast Collapse All / Expand All signals from sections to ItemCards */
export const CardCollapseContext = createContext(null);

export function useCardCollapse() {
  const [itemsExpanded, setItemsExpanded] = useState(true);
  const [collapseSignal, setCollapseSignal] = useState(null);

  const toggleAll = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    const next = !itemsExpanded;
    setItemsExpanded(next);
    setCollapseSignal({ id: Date.now(), open: next });
  };

  return { itemsExpanded, collapseSignal, toggleAll };
}

/** Shared form primitives: cards, labeled inputs, list helpers. */

export function YardAddButton({ onClick, children }) {
  return (
    <button type="button" onClick={onClick}
      className="ml-auto inline-flex min-h-8 shrink-0 items-center justify-center whitespace-nowrap rounded-lg bg-[var(--accent)] px-3 py-1 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] cursor-pointer">
      + Add {children}
    </button>
  );
}

export function Section({ id, title, hint, count, onAdd, addLabel, actions, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  const { itemsExpanded, collapseSignal, toggleAll } = useCardCollapse();

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
          {count > 0 && open && (
            <button
              type="button"
              onClick={toggleAll}
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
              title={itemsExpanded ? 'Collapse all items in this section' : 'Expand all items in this section'}
            >
              {itemsExpanded ? 'Collapse all' : 'Expand all'}
            </button>
          )}
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
        <CardCollapseContext.Provider value={collapseSignal}>
          <div className="space-y-3.5 px-3.5 py-3.5 text-sm">
            {hint && <p className="text-xs text-[var(--text-muted)] leading-relaxed">{hint}</p>}
            {children}
          </div>
        </CardCollapseContext.Provider>
      )}
    </section>
  );
}

export function ItemCard({
  title,
  subtitle,
  badge,
  onRemove,
  defaultOpen = true,
  isOpen,
  onToggle,
  collapsible = true,
  children,
}) {
  const collapseSignal = useContext(CardCollapseContext);
  const [localOpen, setLocalOpen] = useState(defaultOpen);

  useEffect(() => {
    if (collapseSignal && typeof collapseSignal.open === 'boolean') {
      setLocalOpen(collapseSignal.open);
    }
  }, [collapseSignal]);

  const open = isOpen !== undefined ? isOpen : localOpen;

  const handleToggle = () => {
    if (!collapsible) return;
    if (onToggle) {
      onToggle(!open);
    } else {
      setLocalOpen(!open);
    }
  };

  return (
    <div className={`rounded-lg border border-[var(--border)] bg-[var(--surface-soft)] p-3 transition-all ${!open ? 'hover:border-slate-300' : ''}`}>
      <div
        className={`flex items-center gap-2 select-none ${
          collapsible ? 'cursor-pointer group' : ''
        } ${open ? 'mb-2.5 pb-2 border-b border-[var(--border)]' : ''}`}
        onClick={handleToggle}
      >
        {collapsible && (
          <span
            className="text-[var(--text-muted)] group-hover:text-[var(--accent)] transition-transform duration-200 inline-flex items-center justify-center w-4 h-4 shrink-0"
            style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}
            title={open ? 'Collapse item' : 'Expand item'}
          >
            <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
              <path d="M6 4l8 6-8 6V4z" />
            </svg>
          </span>
        )}
        <span className="text-sm font-semibold text-[var(--text-primary)] group-hover:text-[var(--accent)] transition-colors truncate">
          {title}
        </span>
        {subtitle && (
          <span className="text-xs text-[var(--text-muted)] truncate hidden sm:inline">
            {subtitle}
          </span>
        )}
        {badge && (
          <span className="rounded bg-[var(--surface)] border border-[var(--border)] px-1.5 py-0.5 text-[11px] font-mono text-[var(--text-muted)] shrink-0">
            {badge}
          </span>
        )}
        {!open && (
          <span className="text-[11px] text-[var(--text-muted)] italic hidden sm:inline ml-1">
            (click to expand)
          </span>
        )}
        {onRemove && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="ml-auto rounded-md px-2 py-0.5 text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer shrink-0"
            title="Remove"
          >
            Remove
          </button>
        )}
      </div>
      {open && <div>{children}</div>}
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
