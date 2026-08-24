import type { ReactNode } from "react";

export function Section({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="mb-3.5 flex items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink-100">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-ink-400">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function LoadingBlock() {
  return (
    <div className="grid place-items-center py-24 text-sm text-ink-400">
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-ember-500 border-t-transparent" />
        Loading data…
      </div>
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="panel border-bloom-500/30 p-6 text-sm text-bloom-300">
      Couldn&apos;t load data: {message}
    </div>
  );
}
