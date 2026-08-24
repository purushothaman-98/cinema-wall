import type { EvidenceScore, Trend } from "../lib/api";

const EVIDENCE_STYLES: Record<EvidenceScore["label"], string> = {
  "Strong evidence": "bg-signal-500/15 text-signal-400 ring-signal-500/30",
  "Useful evidence": "bg-ember-500/15 text-ember-400 ring-ember-500/30",
  "Thin evidence": "bg-bloom-500/15 text-bloom-400 ring-bloom-500/30",
  "Awaiting evidence": "bg-ink-700 text-ink-300 ring-ink-600",
};

export function EvidenceBadge({ evidence }: { evidence: EvidenceScore }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${EVIDENCE_STYLES[evidence.label]}`}
      title={`Evidence strength score: ${evidence.score}/100 — how well-covered this film's sample is, not a quality rating`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {evidence.label}
    </span>
  );
}

const TREND_META: Record<Trend, { label: string; icon: string; className: string }> = {
  rising: { label: "Rising", icon: "↗", className: "text-signal-400" },
  cooling: { label: "Cooling", icon: "↘", className: "text-ink-300" },
  flat: { label: "Steady", icon: "→", className: "text-ink-300" },
  "insufficient-data": { label: "Not live", icon: "·", className: "text-ink-400" },
};

export function TrendBadge({ trend }: { trend: Trend }) {
  const meta = TREND_META[trend];
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold ${meta.className}`}>
      <span aria-hidden>{meta.icon}</span>
      {meta.label}
    </span>
  );
}

export function RadarBadge({ onRadar }: { onRadar: boolean }) {
  return onRadar ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ember-500/15 px-2.5 py-1 text-[11px] font-semibold text-ember-400 ring-1 ring-inset ring-ember-500/30">
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ember-400 opacity-75" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ember-500" />
      </span>
      On radar
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-700 px-2.5 py-1 text-[11px] font-semibold text-ink-300 ring-1 ring-inset ring-ink-600">
      Historical
    </span>
  );
}
