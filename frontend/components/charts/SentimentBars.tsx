"use client";

import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { sentimentColor, formatDateShort } from "@/lib/formatters";
import type { SentimentDay } from "@/lib/types";

interface Props {
  data: SentimentDay[];
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as SentimentDay;
  return (
    <div
      className="rounded border px-3 py-2 text-xs"
      style={{ background: "#374151", borderColor: "#4B5563", color: "#F9FAFB" }}
    >
      <div className="mb-1 font-medium" style={{ color: "#9CA3AF" }}>
        {label}
      </div>
      <div className="font-mono" style={{ color: sentimentColor(d.mean) }}>
        {d.mean >= 0 ? "+" : ""}
        {d.mean.toFixed(3)}
      </div>
      <div className="mt-1 flex gap-2" style={{ color: "#9CA3AF" }}>
        <span style={{ color: "#10B981" }}>▲ {d.positive}</span>
        <span style={{ color: "#F59E0B" }}>◆ {d.neutral}</span>
        <span style={{ color: "#EF4444" }}>▼ {d.negative}</span>
      </div>
    </div>
  );
}

export function SentimentBars({ data }: Props) {
  // Sample every N bars if too many to avoid clutter
  const step = data.length > 60 ? Math.ceil(data.length / 60) : 1;
  const sampled = data.filter((_, i) => i % step === 0 || i === data.length - 1);

  // Show tick every ~2 weeks
  const tickInterval = Math.max(1, Math.floor(sampled.length / 6));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart
        data={sampled}
        margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
        barCategoryGap="8%"
      >
        <CartesianGrid vertical={false} stroke="#37415144" />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10, fill: "#6B7280", fontFamily: "var(--font-jetbrains-mono)" }}
          tickFormatter={(v) => formatDateShort(v)}
          interval={tickInterval - 1}
        />
        <YAxis
          domain={[-1, 1]}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10, fill: "#6B7280", fontFamily: "var(--font-jetbrains-mono)" }}
          tickFormatter={(v) => v.toFixed(1)}
          ticks={[-1, -0.5, 0, 0.5, 1]}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "#37415133" }} />
        <ReferenceLine y={0} stroke="#4B5563" strokeWidth={1} />
        <Bar dataKey="mean" radius={[2, 2, 0, 0]} maxBarSize={12}>
          {sampled.map((entry, i) => (
            <Cell key={i} fill={sentimentColor(entry.mean)} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
