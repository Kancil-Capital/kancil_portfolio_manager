"use client";

import { Loader2 } from "lucide-react";
import type { SentimentStatus } from "@/lib/types";

interface Props {
  ticker: string;
  status: SentimentStatus | undefined;
}

export function FetchingBanner({ ticker, status }: Props) {
  const count = status?.article_count ?? 0;
  const eta = status?.estimated_seconds_remaining;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-5 py-3"
      style={{
        background: "#1E3A8A18",
        borderColor: "#3B82F630",
      }}
    >
      <Loader2
        size={14}
        className="shrink-0 animate-spin"
        style={{ color: "#3B82F6" }}
      />
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
