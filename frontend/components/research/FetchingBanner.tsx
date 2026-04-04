"use client";

import { Loader2 } from "lucide-react";
import type { SentimentStatus } from "@/lib/types";
import type { ScrapeStreamEvent } from "@/hooks/useScrapeStream";
import { sentimentColor, formatSentiment } from "@/lib/formatters";

interface Props {
  ticker: string;
  // Polling fallback — used when the WS is not streaming
  status: SentimentStatus | undefined;
  // Live stream from WebSocket
  streamEvents?: ScrapeStreamEvent[];
  isStreaming?: boolean;
}

// ── Live stream view ───────────────────────────────────────────────────────────

function StreamRow({ event }: { event: ScrapeStreamEvent }) {
  const score = event.sentiment;
  const color = score != null ? sentimentColor(score) : "#6B7280";
  const label = score != null ? formatSentiment(score) : "—";

  return (
    <div className="flex items-center gap-3 py-1.5 animate-fade-up">
      <span
        className="shrink-0 w-1.5 h-1.5 rounded-full"
        style={{ background: color }}
      />
      <span
        className="flex-1 truncate text-xs"
        style={{ color: "#D1D5DB" }}
        title={event.article_title ?? ""}
      >
        {event.article_title ?? "—"}
      </span>
      <span
        className="shrink-0 font-mono text-xs tabular-nums"
        style={{ color }}
      >
        {label}
      </span>
    </div>
  );
}

function StreamingBanner({
  ticker,
  events,
  articlesAnalyzed,
  isStreaming,
}: {
  ticker: string;
  events: ScrapeStreamEvent[];
  articlesAnalyzed: number;
  isStreaming: boolean;
}) {
  // Show the 5 most recent events
  const visible = events.slice(-5);

  return (
    <div
      className="rounded-lg border px-5 py-4"
      style={{ background: "#1E3A8A18", borderColor: "#3B82F630" }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <Loader2
          size={13}
          className={isStreaming ? "shrink-0 animate-spin" : "shrink-0 opacity-40"}
          style={{ color: "#3B82F6" }}
        />
        <span className="text-sm font-medium" style={{ color: "#93C5FD" }}>
          {isStreaming
            ? `Analyzing ${ticker} sentiment…`
            : `${ticker} sentiment analysis complete`}
        </span>
        <span className="ml-auto shrink-0 font-mono text-xs tabular-nums" style={{ color: "#6B7280" }}>
          {articlesAnalyzed} article{articlesAnalyzed !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Article feed */}
      {visible.length > 0 && (
        <div
          className="border-t"
          style={{ borderColor: "#3B82F620" }}
        >
          {visible.map((ev, i) => (
            <StreamRow key={`${i}-${ev.article_title}`} event={ev} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Polling fallback view ──────────────────────────────────────────────────────

function PollingBanner({ ticker, status }: { ticker: string; status: SentimentStatus | undefined }) {
  const count = status?.article_count ?? 0;
  const eta = status?.estimated_seconds_remaining;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-5 py-3"
      style={{ background: "#1E3A8A18", borderColor: "#3B82F630" }}
    >
      <Loader2 size={14} className="shrink-0 animate-spin" style={{ color: "#3B82F6" }} />
      <div className="flex-1">
        <span className="text-sm font-medium" style={{ color: "#93C5FD" }}>
          Fetching sentiment data for {ticker}…
        </span>
        <span className="ml-2 text-xs" style={{ color: "#6B7280" }}>
          {count > 0 ? `${count} article${count !== 1 ? "s" : ""} indexed` : "Scraping news…"}
          {eta != null && eta > 0 ? ` · ~${eta}s remaining` : ""}
        </span>
      </div>
      <span className="shrink-0 text-xs" style={{ color: "#4B5563" }}>
        Price data is ready below ↓
      </span>
    </div>
  );
}

// ── Exported component ─────────────────────────────────────────────────────────

export function FetchingBanner({ ticker, status, streamEvents, isStreaming }: Props) {
  const hasStreamActivity = (streamEvents?.length ?? 0) > 0 || isStreaming;
  const articlesAnalyzed = streamEvents?.at(-1)?.articles_done ?? 0;

  if (hasStreamActivity) {
    return (
      <StreamingBanner
        ticker={ticker}
        events={streamEvents ?? []}
        articlesAnalyzed={articlesAnalyzed}
        isStreaming={isStreaming ?? false}
      />
    );
  }

  return <PollingBanner ticker={ticker} status={status} />;
}
