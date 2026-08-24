import type { HeatmapCell } from "../lib/api";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function ArrivalHeatmap({ cells }: { cells: HeatmapCell[] }) {
  const max = Math.max(...cells.map((c) => c.count), 1);
  const byKey = new Map(cells.map((c) => [`${c.day}:${c.hour}`, c.count]));

  return (
    <div>
      <div className="overflow-x-auto pb-1">
        <div className="grid min-w-[560px] grid-cols-[auto_repeat(24,minmax(0,1fr))] gap-[3px]">
          <div />
          {Array.from({ length: 24 }).map((_, hour) => (
            <div key={hour} className="text-center text-[9px] text-ink-500">
              {hour % 3 === 0 ? hour : ""}
            </div>
          ))}
          {DAYS.map((day, dayIdx) => (
            <FragmentRow key={day} day={day} dayIdx={dayIdx} byKey={byKey} max={max} />
          ))}
        </div>
      </div>
      <p className="mt-2 text-[11px] text-ink-400">Comment arrival by hour of day, UTC — darker means busier.</p>
    </div>
  );
}

function FragmentRow({
  day,
  dayIdx,
  byKey,
  max,
}: {
  day: string;
  dayIdx: number;
  byKey: Map<string, number>;
  max: number;
}) {
  return (
    <>
      <div className="pr-2 text-right text-[10px] leading-[18px] text-ink-400">{day}</div>
      {Array.from({ length: 24 }).map((_, hour) => {
        const count = byKey.get(`${dayIdx}:${hour}`) ?? 0;
        const intensity = count / max;
        return (
          <div
            key={hour}
            className="h-[18px] rounded-[3px]"
            title={`${day} ${hour}:00 UTC — ${count.toLocaleString()} comments`}
            style={{
              backgroundColor:
                intensity === 0 ? "rgba(255,255,255,0.03)" : `rgba(255, 95, 46, ${0.12 + intensity * 0.78})`,
            }}
          />
        );
      })}
    </>
  );
}
