"use client";

import { Info } from "lucide-react";
import type { LagCorrelation } from "@/lib/types";

interface Props {
  correlations: LagCorrelation[];
}

// Matches SIGNIFICANCE_LEVEL in backend/services/sentiment_service.py (on the adjusted p)
const SIGNIFICANCE = 0.05;
// Below this many paired days the analyst guidance says to treat r as weak
const WEAK_N = 30;

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

function formatR(r: number, digits = 2): string {
  return `${r >= 0 ? "+" : ""}${r.toFixed(digits)}`;
}

// "p<0.001" or "p=0.031"; spaced reads "p < 0.001" / "p = 0.031"
function formatP(p: number, spaced = false): string {
  const [op, value] = p < 0.001 ? ["<", "0.001"] : ["=", p.toFixed(3)];
  return spaced ? `p ${op} ${value}` : `p${op}${value}`;
}

const isSignificant = (c: LagCorrelation) => c.p_value < SIGNIFICANCE;

function cellTooltip(c: LagCorrelation): string {
  const lines = [
    `Sentiment ${c.lag} trading day${c.lag === 1 ? "" : "s"} ago vs return today`,
    `r = ${formatR(c.correlation, 3)}`,
    `n = ${c.n}${c.n < WEAK_N ? " (under 30: treat as weak)" : ""}`,
    `${formatP(c.p_value, true)} (adjusted): ${isSignificant(c) ? "significant" : "not significant"}`,
  ];
  return lines.join("\n");
}

function HowToRead() {
  return (
    <details className="group text-xs" style={{ color: "#9CA3AF" }}>
      <summary
        className="flex cursor-pointer list-none items-center gap-1.5 select-none"
        style={{ color: "#6B7280" }}
      >
        <Info size={12} />
        <span className="group-open:hidden">How to read this</span>
        <span className="hidden group-open:inline">Hide</span>
      </summary>
      <div className="mt-2 flex flex-col gap-2 rounded px-3 py-2 leading-relaxed" style={{ background: "#111827" }}>
        <p>
          Each cell compares a stock’s news sentiment k trading days ago with its price return
          today.
        </p>
        <p>
          <span className="font-mono" style={{ color: "#F9FAFB" }}>r</span> (−1 to 1): strength and
          direction. Positive means good news tended to come before price rises.
        </p>
        <p>
          <span className="font-mono" style={{ color: "#F9FAFB" }}>n</span>: the number of trading
          days with both news and a price. Under about 30, treat the result as weak.
        </p>
        <p>
          <span className="font-mono" style={{ color: "#F9FAFB" }}>p</span> (adjusted): how likely a
          result this strong is by pure chance, adjusted because 8 lags are tested. Below 0.05
          counts as significant. Greyed-out cells aren’t significant.
        </p>
        <p style={{ color: "#6B7280" }}>
          This is a short-term (1–8 day) relationship based on about a year of data. It isn’t a
          forecast, and it isn’t a basis for long-term decisions on its own.
        </p>
      </div>
    </details>
  );
}

export function LagHeatmap({ correlations }: Props) {
  if (!correlations.length) {
    return (
      <div className="flex items-center justify-center text-xs" style={{ color: "#6B7280", height: 120 }}>
        Insufficient data
      </div>
    );
  }

  const significant = correlations.filter(isSignificant);
  const best = significant.length
    ? significant.reduce((a, b) => (Math.abs(a.correlation) >= Math.abs(b.correlation) ? a : b))
    : null;

  return (
    <div className="flex flex-col gap-3">
      {/* Colour scale legend */}
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px]" style={{ color: "#EF4444" }}>−1</span>
        <div
          className="h-2 flex-1 rounded-full"
          style={{
            background: "linear-gradient(to right, #EF4444, #374151, #10B981)",
          }}
        />
        <span className="font-mono text-[10px]" style={{ color: "#10B981" }}>+1</span>
      </div>

      {/* Cells: lag in trading days; not-significant cells are greyed out */}
      <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.min(correlations.length, 4)}, 1fr)` }}>
        {correlations.map((c) => {
          const sig = isSignificant(c);
          return (
            <div
              key={c.lag}
              title={cellTooltip(c)}
              className="flex cursor-help flex-col items-center justify-center gap-0.5 rounded p-2"
              style={{
                background: sig ? corrToColor(c.correlation) : "#374151",
                opacity: sig ? 1 : 0.5,
                minHeight: 72,
              }}
            >
              <span className="text-[10px] font-medium" style={{ color: "rgba(255,255,255,0.6)" }}>
                {c.lag}d lag
              </span>
              <span className="font-mono text-sm font-medium" style={{ color: "#fff" }}>
                {formatR(c.correlation)}
              </span>
              <span className="font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.7)" }}>
                n=
                <span style={c.n < WEAK_N ? { color: "#F59E0B" } : undefined}>{c.n}</span>
                {" "}{formatP(c.p_value)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Best lag callout: significant lags only */}
      <div
        className="rounded px-3 py-2 text-xs"
        style={{ background: "#111827", color: "#9CA3AF" }}
      >
        {best ? (
          <>
            Strongest significant signal at{" "}
            <span className="font-mono font-medium" style={{ color: "#F9FAFB" }}>
              {best.lag}d lag
            </span>{" "}
            (r ={" "}
            <span className="font-mono font-medium" style={{ color: corrToColor(best.correlation) }}>
              {formatR(best.correlation, 3)}
            </span>
            ,{" "}
            <span className="font-mono font-medium" style={{ color: "#F9FAFB" }}>
              {formatP(best.p_value, true)}
            </span>
            )
          </>
        ) : (
          <>No significant lag: adjusted p ≥ 0.05 at every lag tested</>
        )}
      </div>

      <HowToRead />
    </div>
  );
}
