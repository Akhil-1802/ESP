import { ChainageRangeReference } from './ChainageRangeReference.jsx';
import { useRef, useState } from 'react';
import { getTrackCentre, loadKmlAlignment } from '../lib/kmlAlignment.js';
import { calculateEndChainageFromKmM, fillCentredChainages, fillFobCentres, formatStartChainage } from '../lib/config.js';
import { blankStationMarker } from '../lib/formDefaults.js';
import { removeYard } from '../lib/stationYard.js';
import { stationsFromRows, mergeImportedStations } from '../lib/stationWorkbook.js';
import { isBlank } from '../lib/formUtils.js';
import { Field, Grid, Section, Text, YardAddButton } from './fields.jsx';
import { useFormSetter } from '../lib/useFormSetter.js';
import { TrackSelectionPanel } from './TrackSelectionPanel.jsx';

export function SourceSection({
  form,
  set,
  onPreviewKml,
  onPreviewDirectKml,
  alignmentState,
  onAlignmentStateChange,
}) {
  const setTop = useFormSetter(set);
  const [centreBusy, setCentreBusy] = useState(false);
  const [centreMsg, setCentreMsg] = useState('');
  const [candidateTracks, setCandidateTracks] = useState([]);
  const [confirmedTrackId, setConfirmedTrackId] = useState(null);
  const requestIdRef = useRef(0);
  const file = form.kmlFile;
  const stationMarkers = form.stationMarkers || [];
  const stationFileInput = useRef(null);
  const [importingStations, setImportingStations] = useState(false);
  const [stationImportMessage, setStationImportMessage] = useState('');

  async function importStations(event) {
    const workbook = event.target.files?.[0];
    event.target.value = '';
    if (!workbook) return;
    setImportingStations(true);
    setStationImportMessage('');
    try {
      const { default: readWorkbook } = await import('read-excel-file');
      const rows = await readWorkbook(workbook).catch(() => {
        throw new Error('Could not read the workbook. Choose a valid .xlsx file.');
      });
      const imported = stationsFromRows(rows);
      set((previous) => ({
        ...previous,
        stationMarkers: mergeImportedStations(previous.stationMarkers || [], imported),
      }));
      setStationImportMessage(`Processed ${imported.length} station rows from ${workbook.name}.`);
    } catch (error) {
      setStationImportMessage(error.message);
    } finally {
      setImportingStations(false);
    }
  }

  const addStationMarker = () => {
    const current = form.stationMarkers || [];
    setTop({ stationMarkers: [...current, blankStationMarker(current.length + 1)] });
  };

  const updateStationMarker = (idx, patch) => {
    const current = [...(form.stationMarkers || [])];
    current[idx] = { ...current[idx], ...patch };
    setTop({ stationMarkers: current });
  };

  const removeStationMarker = (idx) => {
    set((current) => removeYard(current, idx));
  };

  const onFile = async (chosen) => {
    const requestId = ++requestIdRef.current;
    set((f) => ({
      ...f,
      kmlFile: chosen,
      selectedTrackId: null,
      alignmentPoints: null,
      mainLength: null,
      mainCenter: null,
    }));
    setCentreMsg('');
    setCandidateTracks([]);
    setConfirmedTrackId(null);
    setCentreBusy(false);

    if (!chosen) {
      onAlignmentStateChange?.({ status: 'empty', message: '' });
      return;
    }
    onAlignmentStateChange?.({
      status: 'processing',
      message: 'Processing KML alignment…',
    });
    setCentreBusy(true);
    try {
      const { tracks, track: defaultTrack, centre: c } = await loadKmlAlignment(chosen);
      if (requestId !== requestIdRef.current) return;
      setCandidateTracks(tracks);
      const defaultTrackId = defaultTrack.candidate_id;
      setConfirmedTrackId(defaultTrackId);
      set((f) => ({
        ...fillFobCentres(fillCentredChainages(f, c), c),
        selectedTrackId: defaultTrackId,
        alignmentPoints: defaultTrack.pts_utm,
        mainLength: c.main_length_m,
        mainCenter: c.main_center_m,
      }));
      setCentreMsg(
        `Track length: ${c.main_length_m.toFixed(2)} m (MAIN centre: ${c.main_center_m.toFixed(2)} m)`,
      );
      onAlignmentStateChange?.({
        status: 'ready',
        message: `Alignment ready · ${c.main_length_m.toFixed(2)} m`,
      });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setCentreMsg(err.message);
      onAlignmentStateChange?.({ status: 'error', message: err.message });
    } finally {
      if (requestId === requestIdRef.current) setCentreBusy(false);
    }
  };

  const onSelectCandidateTrack = (cand) => {
    if (!file || !cand) return;
    ++requestIdRef.current;
    setTop({ selectedTrackId: cand.candidate_id, alignmentPoints: null, mainLength: null, mainCenter: null });
    onAlignmentStateChange?.({
      status: 'processing',
      message: `Processing ${cand.name || 'selected track'}…`,
    });
    setCentreBusy(true);
    try {
      const c = getTrackCentre(cand);
      set((f) => ({
        ...fillFobCentres(fillCentredChainages(f, c), c),
        selectedTrackId: cand.candidate_id,
        alignmentPoints: cand.pts_utm || null,
        mainLength: c.main_length_m,
        mainCenter: c.main_center_m,
      }));
      setCentreMsg(
        `Previewing track ${cand.name}: ${c.main_length_m.toFixed(2)} m (MAIN centre: ${c.main_center_m.toFixed(2)} m)`,
      );
      onAlignmentStateChange?.({ status: 'ready', message: `Alignment ready · ${c.main_length_m.toFixed(2)} m` });
      return c;
    } catch (err) {
      setCentreMsg(err.message);
      onAlignmentStateChange?.({ status: 'error', message: err.message });
    } finally {
      setCentreBusy(false);
    }
  };

  const onConfirmCandidateMainLine = (cand) => {
    if (!cand) return;
    const centre = onSelectCandidateTrack(cand);
    if (!centre) return;
    setConfirmedTrackId(cand.candidate_id);
    setCentreMsg(
      `✓ Confirmed Main Line: ${cand.name} (${centre.main_length_m.toFixed(2)} m). Ready for ESP generation.`,
    );
  };

  const calculatedEnd = calculateEndChainageFromKmM(form.startKm, form.startM, form.mainLength);
  const startDisplay = formatStartChainage(form.startKm, form.startM);

  return (
    <Section
      id="source"
      title="1 · Source & output"
      hint="The uploaded KML is always the alignment source. The output name is used for the downloaded DXF."
    >
      <Grid>
        <Field span2 label="KML alignment file *" hint={file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'Required, e.g. ESP.kml'}>
          <input
            type="file"
            accept=".kml"
            onChange={(e) => onFile(e.target.files[0] || null)}
            className="w-full text-xs text-[var(--text-secondary)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--accent)] hover:file:bg-[var(--accent-strong)] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white file:transition-colors file:cursor-pointer"
          />
          {(centreBusy || centreMsg) && (
            <span className="mt-0.5 block text-[11px] leading-snug text-[var(--accent)]">
              {centreBusy ? 'Reading track geometry from KML…' : centreMsg}
            </span>
          )}
          {file && alignmentState?.status === 'ready' && (
            <div className="mt-2.5 flex flex-col gap-1.5">
              <div className="flex flex-wrap gap-2">
                {onPreviewKml && (
                  <button
                    type="button"
                    onClick={onPreviewKml}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-[var(--accent-start)] to-[var(--accent)] hover:from-[var(--accent-strong)] hover:to-[var(--accent-strong)] px-3 py-1.5 text-xs font-semibold text-white shadow-xs transition-all cursor-pointer"
                  >
                    <span>👁️ View Alignment with Chainages</span>
                  </button>
                )}
                {onPreviewDirectKml && (
                  <button
                    type="button"
                    onClick={onPreviewDirectKml}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-soft)] text-[var(--accent)] hover:bg-[rgba(50,95,244,0.08)] px-3 py-1.5 text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                  >
                    <span>🗺️ View Exact KML (1:1 Multi-Line)</span>
                  </button>
                )}
              </div>
              <p className="text-[10.5px] text-[var(--text-muted)] leading-tight">
                💡 <b>Alignment Check:</b> <i>View Alignment</i> shows mainline chainages &amp; station flag. <i>View Exact KML</i> previews the raw multi-line survey.
              </p>
            </div>
          )}
        </Field>

        {/* Visual Track Selection Panel */}
        {candidateTracks.length > 0 && (
          <TrackSelectionPanel
            candidateTracks={candidateTracks}
            selectedTrackId={form.selectedTrackId}
            confirmedTrackId={confirmedTrackId}
            onSelectTrack={onSelectCandidateTrack}
            onConfirmMainLine={onConfirmCandidateMainLine}
            stationMarkers={stationMarkers}
          />
        )}

        {/* Alignment Reference Chainages Card */}
        <div className="col-span-full rounded-xl border border-[var(--border)] bg-[var(--surface-soft)] p-3 space-y-2.5 shadow-2xs">
          <div className="flex flex-wrap items-center justify-between gap-1">
            <span className="text-xs font-semibold text-[var(--text-primary)]">Track Reference Chainages</span>
            {form.mainLength != null && (
              <span className="text-[11px] font-semibold text-[var(--accent)] bg-[rgba(50,95,244,0.08)] border border-[var(--border)] rounded px-2 py-0.5">
                KML Track Length: {form.mainLength.toFixed(2)} m
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
            {/* Start Reference Chainage */}
            <div>
              <span className="mb-1 block text-xs font-medium text-slate-700">
                Start reference chainage *
              </span>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                    KM
                  </span>
                  <Text
                    type="number"
                    step="any"
                    value={form.startKm ?? ''}
                    placeholder="e.g. -4 or 4"
                    onChange={(e) => setTop({ startKm: e.target.value })}
                  />
                </div>
                <div>
                  <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                    M (optional)
                  </span>
                  <Text
                    type="number"
                    min="0"
                    step="any"
                    value={form.startM ?? ''}
                    placeholder="e.g. 900 or empty"
                    onChange={(e) => setTop({ startM: e.target.value })}
                  />
                </div>
              </div>
              <span className="mt-1 block text-[11px] text-slate-500">
                Starts at:{' '}
                <strong className="text-slate-700 font-semibold">
                  {startDisplay || '0.000'}
                </strong>
              </span>
              <ChainageRangeReference form={form} units="kilometres" />
            </div>

            {/* End Chainage (Calculated) */}
            <div>
              <span className="mb-1 block text-xs font-medium text-slate-700">
                End chainage (calculated)
              </span>
              <div>
                <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                  Derived Target
                </span>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={
                    calculatedEnd ??
                    (form.mainLength != null ? 'Invalid start chainage' : '— (Upload KML to calculate)')
                  }
                  className="w-full rounded-lg border border-slate-300 bg-slate-100 px-2.5 py-1.5 text-xs font-semibold text-slate-800 cursor-not-allowed select-all"
                />
              </div>
              <span className="mt-1 block text-[11px] text-slate-500">
                {form.mainLength != null
                  ? `Formula: ${startDisplay || '0'} + ${form.mainLength.toFixed(2)} m`
                  : 'Awaiting KML alignment file'}
              </span>
            </div>
          </div>
        </div>

        {/* Stations along Alignment Card */}
        <div className="col-span-full rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs font-semibold text-slate-700 block">Stations along Alignment</span>
              <span className="text-[10px] text-slate-500 block">
                Mark station reference chainages along track alignment
              </span>
            </div>
            <div className="flex items-center gap-2">
              <YardAddButton onClick={addStationMarker}>station</YardAddButton>
              <input ref={stationFileInput} type="file" accept=".xlsx" hidden onChange={importStations} />
              <button type="button" disabled={importingStations} onClick={() => stationFileInput.current?.click()}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
                {importingStations ? 'Importing…' : 'Import Excel'}
              </button>
            </div>
          </div>

          {stationImportMessage && <p role="status" className="text-xs text-slate-700">{stationImportMessage}</p>}
          {stationMarkers.length === 0 ? (
            <div className="rounded-md border border-dashed border-slate-300 bg-white/50 p-2.5 text-center text-[11px] text-slate-500">
              No station references added. The yard continues to use the processed alignment centre. Add a station when you have a known station chainage.
            </div>
          ) : (
            <div className="space-y-2.5">
              {stationMarkers.map((stn, idx) => {
                const hasKm = !isBlank(stn.km);
                const hasM = !isBlank(stn.m);
                const chDisplay = hasKm || hasM ? formatStartChainage(stn.km, stn.m) : null;

                return (
                  <div
                    key={idx}
                    className="rounded-lg border border-slate-200 bg-white p-2.5 space-y-2 shadow-2xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold text-slate-700">
                          Station #{idx + 1}
                        </span>
                        <label className="inline-flex items-center gap-1 cursor-pointer select-none text-[10px] text-slate-600 bg-slate-100 hover:bg-slate-200/80 px-1.5 py-0.5 rounded transition-colors">
                          <input
                            type="checkbox"
                            checked={stn.showFlag !== false}
                            onChange={(e) => updateStationMarker(idx, { showFlag: e.target.checked })}
                            className="rounded border-slate-300 text-[var(--accent)] focus:ring-[var(--accent)] h-3 w-3"
                          />
                          <span>🚩 Station Flag</span>
                        </label>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeStationMarker(idx)}
                        className="text-[11px] font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded px-1.5 py-0.5 transition-colors cursor-pointer"
                        title="Remove this station"
                      >
                        ✕ Remove
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-start">
                      {/* Station Name */}
                      <div>
                        <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          Station Name *
                        </span>
                        <Text
                          value={stn.name ?? ''}
                          placeholder={`STATION ${idx + 1}`}
                          onChange={(e) => updateStationMarker(idx, { name: e.target.value })}
                        />
                      </div>

                      {/* Station Chainage KM */}
                      <div>
                        <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          KM *
                        </span>
                        <Text
                          type="number"
                          min="0"
                          step="any"
                          value={stn.km ?? ''}
                          placeholder="e.g. 2"
                          onChange={(e) => updateStationMarker(idx, { km: e.target.value })}
                        />
                      </div>

                      {/* Station Chainage M (optional) */}
                      <div>
                        <span className="mb-1 block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          M (optional)
                        </span>
                        <Text
                          type="number"
                          min="0"
                          step="any"
                          value={stn.m ?? ''}
                          placeholder="e.g. 400 or empty"
                          onChange={(e) => updateStationMarker(idx, { m: e.target.value })}
                        />
                      </div>
                    </div>

                    <ChainageRangeReference form={form} units="kilometres" />

                    {/* Station Summary / Placement Badge */}
                    <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-500 pt-0.5">
                      <span>
                        Placement:{' '}
                        <strong className="text-slate-700 font-semibold">
                          {chDisplay ? `CH-${chDisplay}` : 'Awaiting chainage'}
                        </strong>
                        {stn.showFlag !== false && (
                          <span className="ml-1.5 text-rose-600 font-medium text-[10px]">🚩 Flag enabled</span>
                        )}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        Visible in KML alignment view until loops are added
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <Field label="Output DXF name" hint="Used for the download (default ESP_frontend.dxf)">
          <Text
            value={form.outputDxf}
            placeholder="ESP_frontend.dxf"
            onChange={(e) => setTop({ outputDxf: e.target.value })}
          />
        </Field>
        <Field label="Track source layer" hint="Layer of MAIN in the source (KML converts to MAIN_TRACK)">
          <Text
            value={form.trackSourceLayer}
            placeholder="MAIN_TRACK"
            onChange={(e) => setTop({ trackSourceLayer: e.target.value })}
          />
        </Field>
      </Grid>
    </Section>
  );
}
