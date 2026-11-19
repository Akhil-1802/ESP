import { chainageRangeReference } from '../lib/chainageRange.js';

export function ChainageRangeReference({ form, units = 'metres', className = '' }) {
  return (
    <p className={`mt-1 text-[11px] leading-relaxed text-[var(--text-muted)] ${className}`}>
      {chainageRangeReference(form, units)}
    </p>
  );
}
