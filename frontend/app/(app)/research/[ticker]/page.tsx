"use client";

import { use, useEffect, useState } from "react";
import { AlertCircle, BarChart2 } from "lucide-react";

import { useTickerData } from "@/hooks/useTickerData";
import { useSentimentStatus } from "@/hooks/useSentimentStatus";
import { useScrapeStream } from "@/hooks/useScrapeStream";
import { useSentimentData } from "@/hooks/useSentimentData";

import { TickerHeader } from "@/components/research/TickerHeader";
import { FetchingBanner } from "@/components/research/FetchingBanner";
import { PeadPanel } from "@/components/research/PeadPanel";
import { SentimentPanel } from "@/components/research/SentimentPanel";
import { NewsPanel } from "@/components/research/NewsPanel";
import { PriceChart } from "@/components/charts/PriceChart";
import { LagHeatmap } from "@/components/charts/LagHeatmap";
import { LagScatter } from "@/components/charts/LagScatter";
import { KeywordCloud } from "@/components/charts/KeywordCloud";
import { Skeleton, SkeletonCard, SkeletonChart } from "@/components/ui/Skeleton";
import { formatPct } from "@/lib/formatters";

// ── Page entry (resolves async params) ────────────────────────────────────────

export default function ResearchTickerPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = use(params);
  return <ResearchContent ticker={ticker.toUpperCase()} />;
}

// ── Skeleton layout ────────────────────────────────────────────────────────────

function ResearchSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      {/* Header skeleton */}
      <div
        className="flex items-center justify-between rounded-lg border px-6 py-4"
        style={{ background: "#1F2937", borderColor: "#374151" }}
      >
        <div className="flex flex-col gap-2">
          <Skeleton className="h-7 w-24" />
          <Skeleton className="h-3 w-40" />
        </div>
        <div className="flex flex-col items-end gap-2">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-16" />
        </div>
      </div>
      {/* Grid skeleton */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-8"><SkeletonChart /></div>
        <div className="col-span-4"><SkeletonCard /></div>
        <div className="col-span-12"><SkeletonCard /></div>
      </div>
    </div>
  );
}

// ── Error state ────────────────────────────────────────────────────────────────

function ErrorState({ ticker, message }: { ticker: string; message: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-20" style={{ color: "#6B7280" }}>
      <AlertCircle size={32} style={{ color: "#EF4444" }} />
      <div className="text-center">
        <p className="font-medium" style={{ color: "#F9FAFB" }}>
          Could not load {ticker}
        </p>
        <p className="mt-1 text-sm">{message}</p>
      </div>
    </div>
  );
}

// ── Technicals row ─────────────────────────────────────────────────────────────

function TechnicalPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div
      className="flex items-center gap-1.5 rounded px-2.5 py-1"
      style={{ background: "#111827" }}
    >
      <span className="text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
        {label}
      </span>
      <span className="font-mono text-xs font-medium" style={{ color: color ?? "#F9FAFB" }}>
        {value}
      </span>
    </div>
  );
}

// ── Main content ───────────────────────────────────────────────────────────────

function ResearchContent({ ticker }: { ticker: string }) {
  const [minConfidence, setMinConfidence] = useState(0);
  const { data, error, isLoading, mutate } = useTickerData(ticker);

  // Re-fetch just sentiment when confidence filter changes
  const { data: filteredSentiment } = useSentimentData(ticker, minConfidence);

  // WebSocket live stream — active whenever sentiment isn't ready yet
  const { events: streamEvents, isStreaming } = useScrapeStream(
    ticker,
    !!data && !data.sentiment_ready,
    () => mutate(),
  );

  // Polling fallback — only runs when WS is not streaming
  const shouldPoll = !!data && !data.sentiment_ready && !isStreaming;
  const { data: statusData } = useSentimentStatus(ticker, shouldPoll);

  // Polling catches the case where WS finished before we connected
  useEffect(() => {
    if (statusData?.ready && data && !data.sentiment_ready) {
      mutate();
    }
  }, [statusData?.ready]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) return <ResearchSkeleton />;
  if (error) {
    const msg = error instanceof Error ? error.message : "Unknown error";
    return <ErrorState ticker={ticker} message={msg} />;
  }
  if (!data) return null;

  const { price, pead, articles } = data;
  // Use filtered sentiment if confidence filter is active, otherwise use embedded data
  const sentiment = minConfidence > 0 ? (filteredSentiment ?? data.sentiment) : data.sentiment;
  const t = price.technicals;

  return (
    <div className="flex flex-col gap-4 animate-fade-up">
      {/* ── Ticker header ──────────────────────────────────────────────────── */}
      <TickerHeader data={data} />

      {/* ── Fetching banner (new ticker) ───────────────────────────────────── */}
      {!data.sentiment_ready && (
        <FetchingBanner
          ticker={ticker}
          status={statusData}
          streamEvents={streamEvents}
          isStreaming={isStreaming}
        />
      )}

      {/* ── Main grid ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">

        {/* Price chart card — 8 cols */}
        <div className="col-span-8">
          <div
            className="rounded-lg border p-5"
            style={{ background: "#1F2937", borderColor: "#374151" }}
          >
            {/* Card header */}
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BarChart2 size={12} style={{ color: "#6B7280" }} />
                <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
                  Price History
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="flex items-center gap-1 text-[10px]" style={{ color: "#6B7280" }}>
                  <span className="inline-block h-0.5 w-3 rounded" style={{ background: "#3B82F6" }} /> MA20
                </span>
                <span className="flex items-center gap-1 text-[10px]" style={{ color: "#6B7280" }}>
                  <span className="inline-block h-0.5 w-3 rounded" style={{ background: "#F59E0B" }} /> MA50
                </span>
              </div>
            </div>

            {/* Chart */}
            <PriceChart ohlcv={price.ohlcv} />

            {/* Technicals row */}
            <div className="mt-3 flex flex-wrap gap-2">
              <TechnicalPill
                label="RSI 14"
                value={t.rsi_14.toFixed(1)}
                color={t.rsi_14 >= 70 ? "#EF4444" : t.rsi_14 <= 30 ? "#10B981" : "#F9FAFB"}
              />
              <TechnicalPill
                label="vs MA20"
                value={formatPct(t.pct_above_ma20, { signed: true })}
                color={t.pct_above_ma20 >= 0 ? "#10B981" : "#EF4444"}
              />
              <TechnicalPill
                label="vs MA50"
                value={formatPct(t.pct_above_ma50, { signed: true })}
                color={t.pct_above_ma50 >= 0 ? "#10B981" : "#EF4444"}
              />
              <TechnicalPill
                label="ATR%"
                value={formatPct(t.atr_pct)}
              />
            </div>
          </div>
        </div>

        {/* PEAD panel — 4 cols */}
        <div className="col-span-4">
          <PeadPanel pead={pead} />
        </div>

        {/* Sentiment panels — only when ready */}
        {sentiment && (
          <>
            {/* Sentiment panel — 7 cols */}
            <div className="col-span-7">
              <SentimentPanel
                sentiment={sentiment}
                minConfidence={minConfidence}
                onMinConfidenceChange={setMinConfidence}
              />
            </div>

            {/* Lag analysis — 5 cols */}
            <div className="col-span-5 flex flex-col gap-4">
              {/* Lag heatmap */}
              <div
                className="rounded-lg border p-5"
                style={{ background: "#1F2937", borderColor: "#374151" }}
              >
                <div className="mb-4 flex items-center gap-2">
                  <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
                    Lag Correlation
                  </span>
                </div>
                <LagHeatmap correlations={sentiment.lag_correlations} />
              </div>

              {/* Lag scatter */}
              {sentiment.scatter_points.length >= 5 && (
                <div
                  className="rounded-lg border p-5"
                  style={{ background: "#1F2937", borderColor: "#374151" }}
                >
                  <div className="mb-3 flex items-center gap-2">
                    <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
                      Sentiment vs Next-Day Return
                    </span>
                  </div>
                  <LagScatter points={sentiment.scatter_points} />
                </div>
              )}
            </div>
          </>
        )}

        {/* News panel — 8 cols */}
        <div className={sentiment ? "col-span-8" : "col-span-12"}>
          <NewsPanel articles={articles} />
        </div>

        {/* Keyword cloud — 4 cols (only if sentiment available) */}
        {sentiment && sentiment.keywords.length > 0 && (
          <div className="col-span-4">
            <div
              className="rounded-lg border p-5 h-full"
              style={{ background: "#1F2937", borderColor: "#374151" }}
            >
              <div className="mb-4 flex items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
                  Top Keywords
                </span>
              </div>
              <KeywordCloud keywords={sentiment.keywords} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
