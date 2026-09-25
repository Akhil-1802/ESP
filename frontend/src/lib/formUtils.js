/**
 * Shared form utility functions.
 * Absorbs duplicated helpers across config and form sections.
 */

/** Patch an item at index `i` in an immutable list. */
export const patchAt = (list, i, patch) =>
  list.map((item, k) => (k === i ? { ...item, ...patch } : item));

/** Round number to 3 decimal places and stringify. */
export const fmt = (n) => String(Math.round(Number(n) * 1000) / 1000);

/** Check if a value is blank (undefined, null, or empty string). */
export const isBlank = (v) => v === undefined || v === null || String(v).trim() === '';

/** Return `fallback` if blank, otherwise parsed number. */
export const numOr = (v, fallback) => {
  if (isBlank(v)) return fallback;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : NaN;
};

/** Return `fallback` if blank, otherwise trimmed string. */
export const strOr = (v, fallback) => (isBlank(v) ? fallback : String(v).trim());
