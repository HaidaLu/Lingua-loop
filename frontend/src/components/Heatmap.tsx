import { useMemo } from "react";
import type { HeatmapDay } from "../types";

function level(count: number): number {
  if (count <= 0) return 0;
  if (count <= 2) return 1;
  if (count <= 5) return 2;
  if (count <= 9) return 3;
  return 4;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function Heatmap({ days }: { days: HeatmapDay[] }) {
  const { cells, monthLabels, weekCount } = useMemo(() => {
    if (days.length === 0) return { cells: [], monthLabels: [], weekCount: 0 };
    const first = new Date(days[0].date + "T00:00:00");
    const pad = first.getDay(); // 0=Sunday; GitHub starts each column on Sunday
    const cells: (HeatmapDay | null)[] = [...Array(pad).fill(null), ...days];
    while (cells.length % 7 !== 0) cells.push(null);
    const weekCount = cells.length / 7;

    const monthLabels: { col: number; label: string }[] = [];
    let lastMonth = -1;
    for (let w = 0; w < weekCount; w++) {
      const cell = cells[w * 7] || cells[w * 7 + 6];
      if (!cell) continue;
      const m = new Date(cell.date + "T00:00:00").getMonth();
      if (m !== lastMonth) {
        monthLabels.push({ col: w, label: MONTHS[m] });
        lastMonth = m;
      }
    }
    return { cells, monthLabels, weekCount };
  }, [days]);

  if (days.length === 0) return null;

  return (
    <div className="heatmap">
      <div className="hm-months" style={{ gridTemplateColumns: `repeat(${weekCount}, 11px)` }}>
        {monthLabels.map((m) => (
          <span key={m.col} style={{ gridColumnStart: m.col + 1 }}>
            {m.label}
          </span>
        ))}
      </div>
      <div className="hm-grid">
        {cells.map((c, i) =>
          c ? (
            <div
              key={c.date}
              className={`hm-cell l${level(c.count)}`}
              title={`${c.date} · ${c.reviews} reviews + ${c.added} new`}
            />
          ) : (
            <div key={`e${i}`} className="hm-cell empty" />
          ),
        )}
      </div>
      <div className="hm-legend">
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((l) => (
          <div key={l} className={`hm-cell l${l}`} />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}
