import type { ReactionTone as ReactionToneType } from "../lib/api";
import { pct } from "../lib/format";

export function ReactionTone({ tone }: { tone: ReactionToneType }) {
  const total = tone.sampleSize || 1;
  const appreciative = tone.appreciative / total;
  const critical = tone.critical / total;
  const mixed = tone.mixed / total;

  if (tone.sampleSize === 0) {
    return <p className="text-xs text-ink-400">No comments with clear reaction wording yet.</p>;
  }

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-ink-800">
        <div className="h-full bg-signal-500" style={{ width: `${appreciative * 100}%` }} title="Appreciative" />
        <div className="h-full bg-ink-500" style={{ width: `${mixed * 100}%` }} title="Mixed / unclear" />
        <div className="h-full bg-bloom-500" style={{ width: `${critical * 100}%` }} title="Critical" />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <Legend swatch="bg-signal-500" label="Appreciative" value={pct(appreciative)} />
        <Legend swatch="bg-ink-500" label="Mixed / unclear" value={pct(mixed)} />
        <Legend swatch="bg-bloom-500" label="Critical" value={pct(critical)} />
      </div>
      <p className="mt-2 text-[11px] text-ink-400">
        Reaction tone from wording in {tone.sampleSize.toLocaleString()} comments — a description of the sample, not a
        quality score.
      </p>
    </div>
  );
}

function Legend({ swatch, label, value }: { swatch: string; label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-ink-300">
      <span className={`h-2 w-2 rounded-full ${swatch}`} />
      {label} <span className="text-ink-100">{value}</span>
    </span>
  );
}
