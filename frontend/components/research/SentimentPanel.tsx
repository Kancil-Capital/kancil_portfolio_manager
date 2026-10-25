"use client";

import { Activity } from "lucide-react";
import { SentimentBars } from "@/components/charts/SentimentBars";
import { SentimentHistogram } from "@/components/charts/SentimentHistogram";
import { SentimentBreakdown } from "@/components/charts/SentimentBreakdown";
import { formatSentiment, sentimentColor } from "@/lib/formatters";
import type { SentimentData } from "@/lib/types";

interface Props {
  sentiment: SentimentData;
  minConfidence: number;
  onMinConfidenceChange: (v: number) => void;
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

export function SentimentPanel({ sentiment, minConfidence, onMinConfidenceChange }: Props) {
  const { daily, stats, scores } = sentiment;
  const { positive_count, neutral_count, negative_count, total_articles } = stats;

  const posW = total_articles > 0 ? (positive_count / total_articles) * 100 : 0;
  const neuW = total_articles > 0 ? (neutral_count / total_articles) * 100 : 0;
  const negW = total_articles > 0 ? (negative_count / total_articles) * 100 : 0;

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
            Sentiment
          </span>
        </div>
        <span className="text-xs" style={{ color: "#4B5563" }}>
          {daily.length}d history · {total_articles} articles
        </span>
      </div>

      {/* Confidence filter */}
      <div
        className="mb-4 rounded-lg px-3 py-2.5"
        style={{ background: "#111827" }}
      >
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
            Confidence Filter
          </span>
          <span className="font-mono text-[11px]" style={{ color: "#3B82F6" }}>
            ≥ {Math.round(minConfidence * 100)}%
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={minConfidence}
          onChange={(e) => onMinConfidenceChange(parseFloat(e.target.value))}
          className="w-full accent-blue-500"
          style={{ height: 4 }}
        />
        <p className="mt-1 text-[9px]" style={{ color: "#4B5563" }}>
          Filter out low-confidence predictions
        </p>
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
          label="30d Median"
          value={formatSentiment(stats.median_30d)}
          valueColor={sentimentColor(stats.median_30d)}
        />
        <StatPill
          label="Net Sentiment"
          value={formatSentiment(stats.net_sentiment)}
          valueColor={sentimentColor(stats.net_sentiment)}
        />
        <StatPill
          label="Articles"
          value={total_articles.toString()}
        />
      </div>

      {/* Pos / Neu / Neg breakdown bar */}
      <div className="mb-4">
        <div className="mb-1 flex overflow-hidden rounded-full" style={{ height: 6 }}>
          <div style={{ width: `${negW}%`, background: "#EF4444" }} />
          <div style={{ width: `${neuW}%`, background: "#6B7280" }} />
          <div style={{ width: `${posW}%`, background: "#10B981" }} />
        </div>
        <div className="flex justify-between text-[10px]" style={{ color: "#6B7280" }}>
          <span style={{ color: "#EF4444" }}>−{negative_count} negative</span>
          <span>{neutral_count} neutral</span>
          <span style={{ color: "#10B981" }}>+{positive_count} positive</span>
        </div>
      </div>

      {/* Trend bars */}
      <div className="mb-4">
        <p className="mb-2 text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
          Daily Mean
        </p>
        <SentimentBars data={daily} />
      </div>

      {/* Breakdown stacked bars */}
      <div className="mb-4">
        <p className="mb-2 text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
          Daily Breakdown
        </p>
        <SentimentBreakdown daily={daily} />
      </div>

      {/* Score distribution histogram */}
      {scores.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
            Score Distribution
          </p>
          <SentimentHistogram scores={scores} />
        </div>
      )}

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
            style={{ color: stats.best_lag_correlation >= 0 ? "#10B981" : "#EF4444" }}
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
