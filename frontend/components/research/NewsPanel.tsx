"use client";

import { Rss, ExternalLink } from "lucide-react";
import { SentimentBadge } from "@/components/ui/Badge";
import { formatRelativeTime, formatSentiment } from "@/lib/formatters";
import { sentimentColor } from "@/lib/formatters";
import type { ArticleSummary } from "@/lib/types";

interface Props {
  articles: ArticleSummary[];
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-12 overflow-hidden rounded-full" style={{ background: "#374151" }}>
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.round(value * 100)}%`,
            background: "#3B82F6",
          }}
        />
      </div>
      <span className="font-mono text-[10px]" style={{ color: "#6B7280" }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

export function NewsPanel({ articles }: Props) {
  return (
    <div
      className="rounded-lg border"
      style={{ background: "#1F2937", borderColor: "#374151" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b px-5 py-3.5" style={{ borderColor: "#374151" }}>
        <div className="flex items-center gap-2">
          <Rss size={12} style={{ color: "#6B7280" }} />
          <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
            Latest News
          </span>
        </div>
        <span className="text-xs" style={{ color: "#4B5563" }}>
          {articles.length} articles
        </span>
      </div>

      {/* Article list */}
      {articles.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10" style={{ color: "#4B5563" }}>
          <Rss size={20} />
          <p className="text-xs">No articles indexed yet</p>
        </div>
      ) : (
        <div className="divide-y" style={{ borderColor: "#374151" }}>
          {articles.map((article) => (
            <div
              key={article.id}
              className="group px-5 py-3 transition-colors hover:bg-[#374151]/30"
            >
              <div className="flex items-start gap-3">
                {/* Sentiment accent bar */}
                <div
                  className="mt-1.5 h-full w-0.5 shrink-0 self-stretch rounded-full"
                  style={{
                    background: sentimentColor(article.sentiment),
                    minHeight: 36,
                  }}
                />

                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="line-clamp-2 text-sm font-medium leading-snug transition-colors hover:text-[#93C5FD]"
                      style={{ color: "#F9FAFB" }}
                    >
                      {article.title}
                    </a>
                    <ExternalLink
                      size={11}
                      className="mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-40"
                      style={{ color: "#9CA3AF" }}
                    />
                  </div>

                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <span className="text-[11px] font-medium" style={{ color: "#3B82F6" }}>
                      {article.source}
                    </span>
                    <span style={{ color: "#374151" }}>·</span>
                    <span className="text-[11px]" style={{ color: "#6B7280" }}>
                      {formatRelativeTime(article.timestamp)}
                    </span>
                    <span style={{ color: "#374151" }}>·</span>
                    <SentimentBadge value={article.sentiment} />
                    <span
                      className="font-mono text-[11px]"
                      style={{ color: sentimentColor(article.sentiment) }}
                    >
                      {formatSentiment(article.sentiment)}
                    </span>
                    <ConfidenceBar value={article.confidence} />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
