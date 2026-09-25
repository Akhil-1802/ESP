import { useState, useCallback } from 'react';
import { fetchMainCenter } from './api.js';

/**
 * Returns [fetchCentre, { busy, msg }] for a given updater.
 * Eliminates duplicate fetchMainCenter wrappers across form sections.
 */
export function useCentreFetch(updater, msgBuilder) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const fetchCentre = useCallback(
    async (form, index, extra) => {
      if (!form.kmlFile) {
        setMsg('Upload the KML file first — the centre is read from your alignment.');
        return;
      }
      setBusy(true);
      setMsg('');
      try {
        const c = await fetchMainCenter({ kmlFile: form.kmlFile });
        updater(form, index, c, extra);
        if (msgBuilder) {
          setMsg(msgBuilder(form, index, c, extra));
        }
      } catch (err) {
        setMsg(err.message);
      } finally {
        setBusy(false);
      }
    },
    [updater, msgBuilder],
  );

  return [fetchCentre, { busy, msg }];
}
