import { useCallback } from 'react';

/** Returns a stable (formPatch) => set(form => ({...form, ...formPatch})) setter. */
export function useFormSetter(set) {
  return useCallback((patch) => set((f) => ({ ...f, ...patch })), [set]);
}
