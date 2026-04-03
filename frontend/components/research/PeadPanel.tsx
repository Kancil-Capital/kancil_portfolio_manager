"use client";

import { Calendar, TrendingUp } from "lucide-react";
import { formatProb, formatSue, formatPct, formatDate } from "@/lib/formatters";
import type { PeadSignal } from "@/lib/types";

interface Props {
  pead: PeadSignal | null;
}

function ProbGauge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.6 ? "#10B981" : value >= 0.45 ? "#F59E0B" : "#EF4444";
  const circumference = 2 * Math.PI * 34;
  const dash = circumference * value;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <svg width={88} height={88} className="-rotate-90">
          {/* Track */}
          <circle
            cx={44} cy={44} r={34}
            fill="none"
            stroke="#374151"
            strokeWidth={6}
          />
          {/* Fill */}
          <circle
            cx={44} cy={44} r={34}
            fill="none"
            stroke={color}
            strokeWidth={6}
            strokeDasharray={`${dash} ${circumference}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-xl font-bold" style={{ color }}>
            {pct}%
          </span>
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs font-medium" style={{ color: "#9CA3AF" }}>
          outperform probability
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1.5">
      <span className="text-xs" style={{ color: "#6B7280" }}>{label}</span>
      <span
        className={`text-xs font-medium ${mono ? "font-mono" : ""}`}
        style={{ color: "#F9FAFB" }}
      >
        {value}
      </span>
    </div>
  );
}

export function PeadPanel({ pead }: Props) {
  const CARD = "rounded-lg border p-5 h-full";
  const CARD_STYLE = { background: "#1F2937", borderColor: "#374151" };

  if (!pead) {
    return (
      <div className={CARD} style={CARD_STYLE}>
        <div className="mb-4 flex items-center gap-2">
          <TrendingUp size={12} style={{ color: "#6B7280" }} />
          <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
            PEAD Signal
          </span>
        </div>
        <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "#4B5563" }}>
          <Calendar size={24} />
          <p className="text-xs text-center">No upcoming earnings date found</p>
        </div>
      </div>
    );
  }

  const { earnings_date, days_to_earnings, outperform_prob_5d, outperform_prob_10d, outperform_prob_20d, best_horizon, features, earnings_history } = pead;
  const bestProb = best_horizon === 5 ? outperform_prob_5d : best_horizon === 10 ? outperform_prob_10d : outperform_prob_20d;

  return (
    <div className={CARD} style={CARD_STYLE}>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp size={12} style={{ color: "#6B7280" }} />
          <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
            PEAD Signal
          </span>
        </div>
        <span
          className="rounded px-2 py-0.5 text-[10px] font-medium font-mono"
          style={{ background: "#3B82F618", color: "#93C5FD", border: "1px solid #3B82F630" }}
        >
          {best_horizon}d horizon
        </span>
      </div>

      {/* Gauge */}
      <div className="mb-4 flex justify-center">
        <ProbGauge value={bestProb} />
      </div>

      {/* Horizon comparison */}
      <div
        className="mb-4 grid grid-cols-3 gap-1 rounded p-2 text-center"
        style={{ background: "#111827" }}
      >
        {[
          { label: "5d", value: outperform_prob_5d },
          { label: "10d", value: outperform_prob_10d },
          { label: "20d", value: outperform_prob_20d },
        ].map(({ label, value }) => (
          <div key={label} className="flex flex-col gap-0.5">
            <span className="text-[10px]" style={{ color: "#6B7280" }}>{label}</span>
            <span
              className="font-mono text-xs font-medium"
              style={{
                color: label === `${best_horizon}d` ? "#F9FAFB" : "#9CA3AF",
                fontWeight: label === `${best_horizon}d` ? 600 : 400,
              }}
            >
              {formatProb(value)}
            </span>
          </div>
        ))}
      </div>

      {/* Divider */}
      <div className="mb-2" style={{ height: 1, background: "#374151" }} />

      {/* Earnings date */}
      <div className="mb-2 flex items-center gap-2 rounded px-2 py-1.5" style={{ background: "#111827" }}>
        <Calendar size={12} style={{ color: "#3B82F6" }} />
        <span className="text-xs font-mono font-medium" style={{ color: "#93C5FD" }}>
          {formatDate(earnings_date)}
        </span>
        <span className="ml-auto text-[10px]" style={{ color: "#6B7280" }}>
          {days_to_earnings}d away
        </span>
      </div>

      {/* Key features */}
      <div className="divide-y" style={{ borderColor: "#37415155" }}>
        {features.sue != null && (
          <Metric label="SUE" value={formatSue(features.sue)} mono />
        )}
        {features.eps_surprise != null && (
          <Metric label="EPS Surprise" value={formatSue(features.eps_surprise)} mono />
        )}
        {features.hist_beat_rate != null && (
          <Metric label="Beat Rate (4Q)" value={formatPct(features.hist_beat_rate)} mono />
        )}
        {features.beat_streak != null && (
          <Metric label="Beat Streak" value={`${features.beat_streak}Q`} mono />
        )}
        {features.ret_20d_pre != null && (
          <Metric
            label="20d Pre-Earn Return"
            value={
              <span style={{ color: features.ret_20d_pre >= 0 ? "#10B981" : "#EF4444" }}>
                {features.ret_20d_pre >= 0 ? "+" : ""}
                {formatPct(features.ret_20d_pre)}
              </span>
            }
          />
        )}
        {features.vix != null && (
          <Metric label="VIX" value={features.vix.toFixed(1)} mono />
        )}
      </div>

      {/* Earnings history */}
      {earnings_history.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
            Earnings History
          </div>
          <div className="flex flex-col gap-0.5">
            {earnings_history.slice(0, 4).map((item) => (
              <div
                key={item.date}
                className="flex items-center justify-between rounded px-2 py-1 text-[11px]"
                style={{ background: "#111827" }}
              >
                <span className="font-mono" style={{ color: "#9CA3AF" }}>
                  {item.date.slice(0, 7)}
                </span>
                <span
                  className="font-mono font-medium"
                  style={{
                    color: item.beat ? "#10B981" : "#EF4444",
                  }}
                >
                  {item.beat ? "BEAT" : "MISS"}
                </span>
                {item.sue != null && (
                  <span className="font-mono" style={{ color: "#9CA3AF" }}>
                    {formatSue(item.sue)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
