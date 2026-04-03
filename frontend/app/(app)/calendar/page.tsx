"use client";

import { useState } from "react";
import Link from "next/link";
import { Calendar, TrendingUp, ChevronRight } from "lucide-react";

import { useGetCalendar } from "@/lib/generated/calendar/calendar";
import { StatusBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  formatSue,
  formatPct,
  formatEarningsDate,
  sentimentColor,
  formatSentiment,
} from "@/lib/formatters";
import type { CalendarEvent } from "@/lib/generated/kancilPortfolioManagerAPI.schemas";

// ── Days-ahead toggle ──────────────────────────────────────────────────────────

const DAYS_OPTIONS = [
  { label: "30d", value: 30 },
  { label: "60d", value: 60 },
  { label: "90d", value: 90 },
  { label: "180d", value: 180 },
];

// ── Null display helper ────────────────────────────────────────────────────────

function Dash() {
  return <span style={{ color: "#4B5563" }}>—</span>;
}

// ── Outperform probability cell ────────────────────────────────────────────────

function ProbCell({ value }: { value: number | null }) {
  if (value === null) return <Dash />;
  const pct = Math.round(value * 100);
  const color = value >= 0.6 ? "#10B981" : value >= 0.45 ? "#F59E0B" : "#EF4444";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full" style={{ background: "#374151" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono text-xs font-medium" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

// ── Table row ──────────────────────────────────────────────────────────────────

function CalendarRow({ event }: { event: CalendarEvent }) {
  const sentColor = event.sentiment_score !== null ? sentimentColor(event.sentiment_score) : "#6B7280";
  const urgency = event.days_to_earnings <= 7
    ? { color: "#EF4444", bg: "#EF444418" }
    : event.days_to_earnings <= 14
    ? { color: "#F59E0B", bg: "#F59E0B18" }
    : { color: "#9CA3AF", bg: "transparent" };

  return (
    <tr className="border-b transition-colors hover:bg-[#374151]/20" style={{ borderColor: "#374151" }}>
      {/* Ticker + Name */}
      <td className="py-3 pl-5 pr-4">
        <Link
          href={`/research/${event.ticker}`}
          className="group flex items-center gap-2"
        >
          <div>
            <div className="flex items-center gap-1.5">
              <span
                className="font-mono text-sm font-semibold transition-colors group-hover:text-[#93C5FD]"
                style={{ color: "#F9FAFB" }}
              >
                {event.ticker}
              </span>
              <ChevronRight
                size={11}
                className="opacity-0 transition-opacity group-hover:opacity-60"
                style={{ color: "#9CA3AF" }}
              />
            </div>
            <span className="text-[11px] line-clamp-1" style={{ color: "#6B7280" }}>
              {event.name}
            </span>
          </div>
        </Link>
      </td>

      {/* Sector */}
      <td className="px-4 py-3">
        <span className="text-xs" style={{ color: "#9CA3AF" }}>
          {event.sector || "—"}
        </span>
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <StatusBadge status={event.status} />
      </td>

      {/* Earnings Date */}
      <td className="px-4 py-3">
        <div
          className="inline-flex items-center gap-1.5 rounded px-2 py-1 font-mono text-xs"
          style={{ color: urgency.color, background: urgency.bg }}
        >
          <Calendar size={10} />
          {formatEarningsDate(event.earnings_date, event.days_to_earnings)}
        </div>
      </td>

      {/* Sentiment */}
      <td className="px-4 py-3">
        {event.sentiment_score !== null ? (
          <span className="font-mono text-xs font-medium" style={{ color: sentColor }}>
            {formatSentiment(event.sentiment_score)}
          </span>
        ) : (
          <Dash />
        )}
      </td>

      {/* SUE */}
      <td className="px-4 py-3">
        {event.sue !== null ? (
          <span
            className="font-mono text-xs font-medium"
            style={{ color: event.sue >= 0 ? "#10B981" : "#EF4444" }}
          >
            {formatSue(event.sue)}
          </span>
        ) : (
          <Dash />
        )}
      </td>

      {/* Outperform Prob */}
      <td className="px-4 py-3">
        <ProbCell value={event.outperform_prob} />
      </td>

      {/* Hist Beat Rate */}
      <td className="px-4 py-3">
        {event.hist_beat_rate !== null ? (
          <span className="font-mono text-xs" style={{ color: "#9CA3AF" }}>
            {formatPct(event.hist_beat_rate * 100)}
          </span>
        ) : (
          <Dash />
        )}
      </td>

      {/* 5d Pre Return */}
      <td className="px-4 py-3 pr-5">
        {event.ret_5d_pre !== null ? (
          <span
            className="font-mono text-xs font-medium"
            style={{ color: event.ret_5d_pre >= 0 ? "#10B981" : "#EF4444" }}
          >
            {formatPct(event.ret_5d_pre * 100, { signed: true })}
          </span>
        ) : (
          <Dash />
        )}
      </td>
    </tr>
  );
}

// ── Skeleton rows ──────────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} className="border-b" style={{ borderColor: "#374151" }}>
          {[5, 4, 3, 5, 3, 3, 4, 3, 3].map((w, j) => (
            <td key={j} className="px-4 py-3.5">
              <Skeleton className={`h-3 w-${w * 4}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [daysAhead, setDaysAhead] = useState(30);

  const { data: res, isLoading } = useGetCalendar({ days_ahead: daysAhead });
  const events = res?.status === 200 ? res.data.events : [];

  const HEADERS = [
    { label: "Ticker", width: "w-44" },
    { label: "Sector", width: "w-32" },
    { label: "Status", width: "w-24" },
    { label: "Earnings Date", width: "w-44" },
    { label: "Sentiment", width: "w-28" },
    { label: "SUE", width: "w-20" },
    { label: "Outperform", width: "w-36" },
    { label: "Beat Rate", width: "w-24" },
    { label: "5d Pre", width: "w-20" },
  ];

  return (
    <div className="flex flex-col gap-4 animate-fade-up">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "#F9FAFB" }}>
            Earnings Calendar
          </h1>
          <p className="mt-0.5 text-xs" style={{ color: "#6B7280" }}>
            Upcoming earnings for tracked tickers with PEAD signals
          </p>
        </div>

        {/* Days ahead toggle */}
        <div
          className="flex items-center rounded-lg border p-0.5"
          style={{ background: "#1F2937", borderColor: "#374151" }}
        >
          {DAYS_OPTIONS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setDaysAhead(value)}
              className="rounded px-3 py-1.5 text-xs font-medium transition-colors"
              style={{
                color: daysAhead === value ? "#F9FAFB" : "#6B7280",
                background: daysAhead === value ? "#374151" : "transparent",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div
        className="overflow-hidden rounded-lg border"
        style={{ background: "#1F2937", borderColor: "#374151" }}
      >
        {/* Table header */}
        <div className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: "#374151" }}>
          <div className="flex items-center gap-2">
            <TrendingUp size={12} style={{ color: "#6B7280" }} />
            <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
              Upcoming Earnings
            </span>
          </div>
          {!isLoading && (
            <span className="text-xs" style={{ color: "#4B5563" }}>
              {events.length} event{events.length !== 1 ? "s" : ""} in next {daysAhead}d
            </span>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b" style={{ borderColor: "#374151" }}>
                {HEADERS.map(({ label, width }) => (
                  <th
                    key={label}
                    className={`${width} px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-widest first:pl-5 last:pr-5`}
                    style={{ color: "#4B5563" }}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <SkeletonRows />
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={HEADERS.length} className="py-16 text-center">
                    <div className="flex flex-col items-center gap-2" style={{ color: "#4B5563" }}>
                      <Calendar size={24} />
                      <p className="text-sm">No earnings in the next {daysAhead} days</p>
                      <p className="text-xs">Add tickers in Research to see upcoming events</p>
                    </div>
                  </td>
                </tr>
              ) : (
                events.map((event) => (
                  <CalendarRow key={event.ticker} event={event} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
