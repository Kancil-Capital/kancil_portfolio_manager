"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { formatDateShort } from "@/lib/formatters";
import type { SentimentDay } from "@/lib/types";

interface Props {
  daily: SentimentDay[];
}

export function SentimentBreakdown({ daily }: Props) {
  if (!daily.length) return null;

  const data = daily.slice(-30);

  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }} barCategoryGap="8%">
        <CartesianGrid vertical={false} stroke="#37415144" />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 9, fill: "#6B7280" }}
          tickFormatter={(v) => formatDateShort(v)}
          interval={Math.max(0, Math.floor(data.length / 5) - 1)}
        />
        <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 9, fill: "#6B7280" }} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "#37415133" }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            return (
              <div className="rounded border px-2 py-1.5 text-xs" style={{ background: "#374151", borderColor: "#4B5563", color: "#F9FAFB" }}>
                <div className="mb-1 text-[10px]" style={{ color: "#9CA3AF" }}>{label}</div>
                {payload.map((p) => (
                  <div key={p.name} style={{ color: p.fill }}>
                    {p.name}: {p.value}
                  </div>
                ))}
              </div>
            );
          }}
        />
        <Bar dataKey="positive" stackId="a" fill="#10B981" fillOpacity={0.85} />
        <Bar dataKey="neutral" stackId="a" fill="#6B7280" fillOpacity={0.7} />
        <Bar dataKey="negative" stackId="a" fill="#EF4444" fillOpacity={0.85} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
