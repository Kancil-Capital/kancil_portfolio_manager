"use client";

import {
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";

interface Props {
  scores: number[];
}

const BINS = [
  { label: "<−0.4", min: -Infinity, max: -0.4, color: "#EF4444" },
  { label: "−0.4−0.2", min: -0.4, max: -0.2, color: "#F87171" },
  { label: "−0.2−0", min: -0.2, max: 0, color: "#6B7280" },
  { label: "0−0.2", min: 0, max: 0.2, color: "#6B7280" },
  { label: "0.2−0.4", min: 0.2, max: 0.4, color: "#34D399" },
  { label: ">0.4", min: 0.4, max: Infinity, color: "#10B981" },
];

export function SentimentHistogram({ scores }: Props) {
  if (!scores.length) return null;

  const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
  const sorted = [...scores].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];

  const data = BINS.map((b) => ({
    label: b.label,
    count: scores.filter((s) => s > b.min && s <= b.max).length,
    color: b.color,
  }));

  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#37415144" />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 9, fill: "#6B7280" }} />
        <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 9, fill: "#6B7280" }} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "#37415133" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            return (
              <div className="rounded border px-2 py-1 text-xs" style={{ background: "#374151", borderColor: "#4B5563", color: "#F9FAFB" }}>
                {payload[0].value} articles
              </div>
            );
          }}
        />
        <ReferenceLine x={mean > -0.4 ? (mean > 0.4 ? ">0.4" : mean > 0.2 ? "0.2−0.4" : mean > 0 ? "0−0.2" : mean > -0.2 ? "−0.2−0" : "−0.4−0.2") : "<−0.4"} stroke="#10B981" strokeDasharray="3 3" label={{ value: `μ ${mean.toFixed(2)}`, fontSize: 9, fill: "#10B981" }} />
        <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={40}>
          {data.map((d, i) => <Cell key={i} fill={d.color} fillOpacity={0.85} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
