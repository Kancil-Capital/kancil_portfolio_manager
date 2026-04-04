"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, TrendingUp, CheckCircle, Clock } from "lucide-react";
import { useListTickers } from "@/lib/generated/tickers/tickers";
import type { TrackedTicker } from "@/lib/types";
import { formatRelativeTime } from "@/lib/formatters";

// ── Recently tracked card ──────────────────────────────────────────────────────

function StatusChip({ status }: { status: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    held:      { bg: "#10B98118", color: "#10B981" },
    tracking:  { bg: "#3B82F618", color: "#3B82F6" },
    untracked: { bg: "#37415180", color: "#6B7280" },
  };
  const s = styles[status] ?? styles.tracking;
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider"
      style={{ background: s.bg, color: s.color }}
    >
      {status}
    </span>
  );
}

function TrackedTickerCard({ ticker }: { ticker: TrackedTicker }) {
  const router = useRouter();
  return (
    <button
      onClick={() => router.push(`/research/${ticker.ticker}`)}
      className="rounded-lg border p-4 text-left transition-colors hover:border-[#3B82F6] w-full"
      style={{ background: "#1f2937", borderColor: "#374151" }}
    >
      {/* Ticker + status */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <span
          className="text-sm font-semibold tracking-wide text-white"
          style={{ fontFamily: "var(--font-jetbrains-mono)" }}
        >
          {ticker.ticker}
        </span>
        <StatusChip status={ticker.status} />
      </div>

      {/* Sentiment indicator */}
      <div className="mb-2 flex items-center gap-1.5">
        {ticker.sentiment_ready ? (
          <>
            <CheckCircle size={11} style={{ color: "#10B981" }} />
            <span className="text-[11px]" style={{ color: "#6B7280" }}>
              Sentiment ready
            </span>
          </>
        ) : (
          <>
            <Clock size={11} style={{ color: "#F59E0B" }} />
            <span className="text-[11px]" style={{ color: "#6B7280" }}>
              Awaiting analysis
            </span>
          </>
        )}
      </div>

      {/* Last scraped */}
      <div className="text-[11px]" style={{ color: "#4B5563" }}>
        {ticker.last_scraped
          ? `Updated ${formatRelativeTime(ticker.last_scraped)}`
          : `Added ${formatRelativeTime(ticker.added_at)}`}
      </div>
    </button>
  );
}

function TickerSkeletonCard() {
  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: "#1f2937", borderColor: "#374151" }}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="h-4 w-16 animate-pulse rounded" style={{ background: "#374151" }} />
        <div className="h-5 w-14 animate-pulse rounded" style={{ background: "#374151" }} />
      </div>
      <div className="mb-3 h-3 w-28 animate-pulse rounded" style={{ background: "#374151" }} />
      <div className="h-3 w-20 animate-pulse rounded" style={{ background: "#374151" }} />
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ResearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const { data: tickerListRaw, isLoading } = useListTickers();
  const allTickers = (tickerListRaw as { data: TrackedTicker[] } | undefined)?.data ?? [];
  // Most recently added, non-untracked, up to 4
  const recentTickers = allTickers
    .filter((t) => t.status !== "untracked")
    .sort((a, b) => (b.added_at > a.added_at ? 1 : -1))
    .slice(0, 4);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const ticker = query.trim().toUpperCase();
    if (ticker) router.push(`/research/${ticker}`);
  }

  return (
    <div className="flex flex-col gap-12">
      {/* Hero search */}
      <section className="flex flex-col items-center gap-6 py-16">
        <div className="flex flex-col items-center gap-2 text-center animate-fade-up">
          <div
            className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-widest"
            style={{ color: "#3b82f6" }}
          >
            <TrendingUp size={12} />
            Research Terminal
          </div>
          <h2 className="text-3xl font-semibold tracking-tight text-white">
            What are you researching?
          </h2>
          <p className="text-sm" style={{ color: "#9ca3af" }}>
            Enter a ticker to pull price data, sentiment analysis, and PEAD signals.
          </p>
        </div>

        <form
          onSubmit={handleSearch}
          className="flex w-full max-w-xl items-center gap-0 animate-fade-up-delay-1"
        >
          <div
            className="flex flex-1 items-center gap-2 rounded-l-lg border border-r-0 px-4 py-3.5 transition-colors focus-within:border-[#3b82f6]"
            style={{ background: "#1f2937", borderColor: "#374151" }}
          >
            <span
              className="select-none text-sm font-medium"
              style={{
                fontFamily: "var(--font-jetbrains-mono)",
                color: "#3b82f6",
              }}
            >
              &gt;
            </span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value.toUpperCase())}
              placeholder="Search ticker — AAPL, MSFT, TSLA…"
              maxLength={10}
              className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-[#4b5563]"
              style={{ fontFamily: "var(--font-jetbrains-mono)" }}
              autoFocus
            />
          </div>
          <button
            type="submit"
            disabled={!query.trim()}
            className="flex h-[50px] w-14 items-center justify-center rounded-r-lg transition-colors disabled:opacity-40"
            style={{ background: "#3b82f6" }}
          >
            <ArrowRight size={16} className="text-white" />
          </button>
        </form>

        <p className="text-[11px] animate-fade-up-delay-2" style={{ color: "#4b5563" }}>
          Press Enter to search
        </p>
      </section>

      {/* Recently Tracked */}
      <section className="animate-fade-up-delay-3">
        <div className="mb-4 flex items-center gap-3">
          <h3
            className="text-xs font-medium uppercase tracking-widest"
            style={{ color: "#6b7280" }}
          >
            Recently Tracked
          </h3>
          <div className="h-px flex-1" style={{ background: "#374151" }} />
          {allTickers.length > 4 && (
            <span className="text-[11px]" style={{ color: "#4B5563" }}>
              {allTickers.filter((t) => t.status !== "untracked").length} total
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {isLoading ? (
            <>
              <TickerSkeletonCard />
              <TickerSkeletonCard />
              <TickerSkeletonCard />
              <TickerSkeletonCard />
            </>
          ) : recentTickers.length > 0 ? (
            <>
              {recentTickers.map((t) => (
                <TrackedTickerCard key={t.ticker} ticker={t} />
              ))}
              {/* Pad to 4 with skeletons if fewer than 4 tracked */}
              {Array.from({ length: Math.max(0, 4 - recentTickers.length) }).map((_, i) => (
                <div
                  key={`empty-${i}`}
                  className="rounded-lg border p-4"
                  style={{ background: "#111827", borderColor: "#1F2937" }}
                />
              ))}
            </>
          ) : (
            <div
              className="col-span-4 rounded-lg border px-6 py-8 text-center text-sm"
              style={{ background: "#111827", borderColor: "#1F2937", color: "#4B5563" }}
            >
              No tickers tracked yet — search above to get started.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
