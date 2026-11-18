import { Field, Grid, Section, Text, Num } from './fields.jsx';

export function KeyPlanSection({ options, onChange, ready, finalized, busy, onGenerate, onRefinalize }) {
  const change = (key) => (event) => onChange({ ...options, [key]: event.target.value });
  return (
    <Section title="Key Plan" hint="Create a schematic from the current finalized ESP. Sizes and spacing adapt to the container.">
      <Grid>
        <Field label="Container width (mm)">
          <Num aria-label="Key plan width" min="210" max="1680" value={options.width} onChange={change('width')} />
        </Field>
        <Field label="Container height (mm)">
          <Num aria-label="Key plan height" min="100" max="1200" value={options.height} onChange={change('height')} />
        </Field>
        <Field label="Left destination">
          <Text aria-label="Key plan left destination" maxLength={100} value={options.left_destination} onChange={change('left_destination')} placeholder="Station name" />
        </Field>
        <Field label="Right destination">
          <Text aria-label="Key plan right destination" maxLength={100} value={options.right_destination} onChange={change('right_destination')} placeholder="Station name" />
        </Field>
        <Field span2 label="Station caption" hint="Blank uses the finalized station names and chainages.">
          <Text aria-label="Key plan station caption" maxLength={160} value={options.station_caption} onChange={change('station_caption')} />
        </Field>
        <Field span2 label="North reference angle (optional)" hint="Degrees counterclockwise from right. Blank uses the survey reference; this is a schematic.">
          <Num aria-label="Key plan north angle" min="-360" max="360" value={options.north_angle} onChange={change('north_angle')} placeholder="Use survey reference" />
        </Field>
      </Grid>
      <button type="button" disabled={!ready || busy} onClick={onGenerate}
        className="mt-3 w-full rounded-lg bg-[var(--accent)] px-3 py-2 font-semibold text-white disabled:opacity-50 cursor-pointer">
        Generate Key Plan
      </button>
      {!ready && <p className="mt-2 text-[11px] text-[var(--text-muted)]">Finalize the current ESP first. Editing the ESP requires finalization again.</p>}
      {finalized && !ready && <button type="button" disabled={busy} onClick={onRefinalize}
        className="mt-2 text-[var(--accent)] underline cursor-pointer">Finalize again to refresh the design</button>}
    </Section>
  );
}
