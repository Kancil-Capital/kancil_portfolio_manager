"use client";

import { Activity } from "lucide-react";
import { SentimentBars } from "@/components/charts/SentimentBars";
import { formatSentiment } from "@/lib/formatters";
import { sentimentColor } from "@/lib/formatters";
import type { SentimentData } from "@/lib/types";

interface Props {
  sentiment: SentimentData;
}

function StatPill({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
        {label}
      </span>
      <span className="font-mono text-sm font-medium" style={{ color: valueColor ?? "#F9FAFB" }}>
        {value}
      </span>
    </div>
  );
}

export function SentimentPanel({ sentiment }: Props) {
  const { daily, stats } = sentiment;

  return (
    <div
      className="rounded-lg border p-5"
      style={{ background: "#1F2937", borderColor: "#374151" }}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={12} style={{ color: "#6B7280" }} />
          <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
            Sentiment Trend
          </span>
        </div>
        <span className="text-xs" style={{ color: "#4B5563" }}>
          {daily.length}d history
        </span>
      </div>

      {/* Stats row */}
      <div
        className="mb-4 grid grid-cols-4 gap-3 rounded-lg p-3"
        style={{ background: "#111827" }}
      >
        <StatPill
          label="30d Mean"
          value={formatSentiment(stats.mean_30d)}
          valueColor={sentimentColor(stats.mean_30d)}
        />
        <StatPill
          label="Net Sentiment"
          value={formatSentiment(stats.net_sentiment)}
          valueColor={sentimentColor(stats.net_sentiment)}
        />
        <StatPill
          label="Bull Ratio"
          value={`${Math.round(stats.sentiment_ratio * 100)}%`}
          valueColor={stats.sentiment_ratio >= 0.5 ? "#10B981" : "#EF4444"}
        />
        <StatPill
          label="Articles"
          value={stats.total_articles.toString()}
        />
      </div>

      {/* Bar chart */}
      <SentimentBars data={daily} />

      {/* Best lag note */}
      {stats.best_lag > 0 && (
        <div className="mt-3 text-xs" style={{ color: "#6B7280" }}>
          Best predictive lag:{" "}
          <span className="font-mono font-medium" style={{ color: "#9CA3AF" }}>
            {stats.best_lag}d
          </span>
          {" "}(r ={" "}
          <span
            className="font-mono"
            style={{
              color: stats.best_lag_correlation >= 0 ? "#10B981" : "#EF4444",
            }}
          >
            {stats.best_lag_correlation >= 0 ? "+" : ""}
            {stats.best_lag_correlation.toFixed(3)}
          </span>
          )
        </div>
      )}
    </div>
  );
}
