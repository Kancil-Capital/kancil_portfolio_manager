"use client";

import {
  Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Line, ComposedChart,
} from "recharts";
import type { ScatterPoint } from "@/lib/types";

interface Props {
  points: ScatterPoint[];
}

function pearsonR(xs: number[], ys: number[]) {
  const n = xs.length;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  const num = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0);
  const den = Math.sqrt(
    xs.reduce((a, x) => a + (x - mx) ** 2, 0) *
    ys.reduce((a, y) => a + (y - my) ** 2, 0)
  );
  return den === 0 ? 0 : num / den;
}

function linearRegression(xs: number[], ys: number[]) {
  const n = xs.length;
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = ys.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((a, x, i) => a + x * ys[i], 0);
  const sumX2 = xs.reduce((a, x) => a + x * x, 0);
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

export function LagScatter({ points }: Props) {
  if (points.length < 5) return null;

  const xs = points.map((p) => p.sentiment);
  const ys = points.map((p) => p.next_day_return);
  const r = pearsonR(xs, ys);
  const r2 = r * r;

  const { slope, intercept } = linearRegression(xs, ys);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const trendLine = [
    { sentiment: xMin, trend: slope * xMin + intercept },
    { sentiment: xMax, trend: slope * xMax + intercept },
  ];

  return (
    <div className="flex flex-col gap-1">
      <ResponsiveContainer width="100%" height={160}>
        <ComposedChart margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <CartesianGrid stroke="#37415144" />
          <XAxis
            dataKey="sentiment"
            type="number"
            domain={["auto", "auto"]}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 9, fill: "#6B7280" }}
            tickFormatter={(v) => v.toFixed(2)}
            label={{ value: "Sentiment", position: "insideBottom", offset: -2, fontSize: 9, fill: "#6B7280" }}
          />
          <YAxis
            dataKey="next_day_return"
            type="number"
            domain={["auto", "auto"]}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 9, fill: "#6B7280" }}
            tickFormatter={(v) => `${v.toFixed(1)}%`}
          />
          <ReferenceLine x={0} stroke="#4B5563" strokeWidth={1} />
          <ReferenceLine y={0} stroke="#4B5563" strokeWidth={1} />
          <Tooltip
            cursor={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0]?.payload;
              if (p?.next_day_return == null) return null;
              return (
                <div className="rounded border px-2 py-1 text-xs" style={{ background: "#374151", borderColor: "#4B5563", color: "#F9FAFB" }}>
                  <div className="font-mono">sent: {p.sentiment?.toFixed(3)}</div>
                  <div className="font-mono">ret: {p.next_day_return?.toFixed(2)}%</div>
                </div>
              );
            }}
          />
          <Scatter data={points} fill="#3B82F6" fillOpacity={0.55} r={3} />
          <Line data={trendLine} dataKey="trend" dot={false} stroke="#10B981" strokeWidth={1.5} strokeDasharray="4 2" legendType="none" />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex justify-end gap-3 text-[10px]" style={{ color: "#6B7280" }}>
        <span>R² = <span className="font-mono" style={{ color: r2 > 0.1 ? "#10B981" : "#9CA3AF" }}>{r2.toFixed(3)}</span></span>
        <span>ρ = <span className="font-mono" style={{ color: r >= 0 ? "#10B981" : "#EF4444" }}>{r >= 0 ? "+" : ""}{r.toFixed(3)}</span></span>
        <span>n = {points.length}</span>
      </div>
    </div>
  );
}
