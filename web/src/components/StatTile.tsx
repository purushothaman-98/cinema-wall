import type { ReactNode } from "react";

export function StatTile({
  label,
  value,
  hint,
  accent = "ember",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  accent?: "ember" | "bloom" | "signal" | "violet";
}) {
  const bar: Record<string, string> = {
    ember: "from-ember-500 to-bloom-500",
    bloom: "from-bloom-500 to-violet-500",
    signal: "from-signal-500 to-ember-400",
    violet: "from-violet-500 to-bloom-500",
  };
  return (
    <div className="panel panel-hover relative overflow-hidden p-5">
      <div className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r ${bar[accent]}`} />
      <p className="kicker">{label}</p>
      <p className="mt-2 font-display text-3xl font-bold tracking-tight text-ink-100">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-400">{hint}</p>}
    </div>
  );
}
