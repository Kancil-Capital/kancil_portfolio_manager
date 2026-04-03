"use client";

import type { LagCorrelation } from "@/lib/types";

interface Props {
  correlations: LagCorrelation[];
}

function corrToColor(c: number): string {
  // -1 → red, 0 → dark gray, +1 → green
  const clamped = Math.max(-1, Math.min(1, c));
  if (clamped >= 0) {
    // 0 → #374151, +1 → #10B981
    const t = clamped;
    const r = Math.round(55 + t * (16 - 55));
    const g = Math.round(65 + t * (185 - 65));
    const b = Math.round(81 + t * (129 - 81));
    return `rgb(${r},${g},${b})`;
  } else {
    // 0 → #374151, -1 → #EF4444
    const t = -clamped;
    const r = Math.round(55 + t * (239 - 55));
    const g = Math.round(65 + t * (68 - 65));
    const b = Math.round(81 + t * (68 - 81));
    return `rgb(${r},${g},${b})`;
  }
}

export function LagHeatmap({ correlations }: Props) {
  if (!correlations.length) {
    return (
      <div className="flex items-center justify-center text-xs" style={{ color: "#6B7280", height: 120 }}>
        Insufficient data
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Colour scale legend */}
      <div className="flex items-center gap-2">
        <span className="text-[10px]" style={{ color: "#EF4444" }}>−1</span>
        <div
          className="h-2 flex-1 rounded-full"
          style={{
            background: "linear-gradient(to right, #EF4444, #374151, #10B981)",
          }}
        />
        <span className="text-[10px]" style={{ color: "#10B981" }}>+1</span>
      </div>

      {/* Cells */}
      <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.min(correlations.length, 4)}, 1fr)` }}>
        {correlations.map(({ lag, correlation }) => (
          <div
            key={lag}
            className="flex flex-col items-center justify-center rounded p-2"
            style={{
              background: corrToColor(correlation),
              minHeight: 56,
            }}
          >
            <span className="text-[10px] font-medium" style={{ color: "rgba(255,255,255,0.6)" }}>
              {lag}d lag
            </span>
            <span
              className="font-mono text-sm font-medium"
              style={{ color: "#fff" }}
            >
              {correlation >= 0 ? "+" : ""}
              {correlation.toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      {/* Best lag callout */}
      {correlations.length > 0 && (() => {
        const best = correlations.reduce((a, b) =>
          Math.abs(a.correlation) >= Math.abs(b.correlation) ? a : b
        );
        return (
          <div
            className="rounded px-3 py-2 text-xs"
            style={{ background: "#111827", color: "#9CA3AF" }}
          >
            Strongest signal at{" "}
            <span className="font-mono font-medium" style={{ color: "#F9FAFB" }}>
              {best.lag}d lag
            </span>{" "}
            (r ={" "}
            <span
              className="font-mono font-medium"
              style={{ color: corrToColor(best.correlation) }}
            >
              {best.correlation >= 0 ? "+" : ""}
              {best.correlation.toFixed(3)}
            </span>
            )
          </div>
        );
      })()}
    </div>
  );
}
