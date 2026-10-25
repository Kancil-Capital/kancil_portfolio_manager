"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Rss, ExternalLink, ChevronLeft, ChevronRight, ChevronDown, ArrowUpDown } from "lucide-react";

import { useGetNews } from "@/lib/generated/news/news";
import { useGetTrackedSymbols } from "@/lib/generated/tickers/tickers";
import { SentimentBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  formatRelativeTime,
  formatSentiment,
  sentimentColor,
} from "@/lib/formatters";
import type { ArticleWithTickers } from "@/lib/generated/kancilPortfolioManagerAPI.schemas";

const PAGE_SIZE = 20;
const SOURCES = ["CNBC", "Finviz", "Yahoo Finance"];

// ── Sentiment filter options ───────────────────────────────────────────────────

type SentimentFilter = "all" | "positive" | "neutral" | "negative";
type SortBy = "recent" | "oldest" | "positive" | "negative" | "impact_desc" | "impact_asc";

const SORT_OPTIONS: { label: string; value: SortBy }[] = [
  { label: "Newest", value: "recent" },
  { label: "Oldest", value: "oldest" },
  { label: "Most Positive", value: "positive" },
  { label: "Most Negative", value: "negative" },
  { label: "Highest Impact", value: "impact_desc" },
  { label: "Lowest Impact", value: "impact_asc" },
];

const SENTIMENT_OPTIONS: { label: string; value: SentimentFilter }[] = [
  { label: "All", value: "all" },
  { label: "Positive", value: "positive" },
  { label: "Neutral", value: "neutral" },
  { label: "Negative", value: "negative" },
];

const SENTIMENT_COLORS: Record<SentimentFilter, string> = {
  all: "#9CA3AF",
  positive: "#10B981",
  neutral: "#F59E0B",
  negative: "#EF4444",
};

// ── Confidence bar ─────────────────────────────────────────────────────────────

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-12 overflow-hidden rounded-full" style={{ background: "#374151" }}>
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.round(value * 100)}%`, background: "#3B82F6" }}
        />
      </div>
      <span className="font-mono text-[10px]" style={{ color: "#6B7280" }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

// ── Article card ───────────────────────────────────────────────────────────────

function ArticleCard({ article }: { article: ArticleWithTickers }) {
  const color = sentimentColor(article.sentiment);

  return (
    <div
      className="group border-b px-5 py-4 transition-colors hover:bg-[#374151]/20"
      style={{ borderColor: "#374151" }}
    >
      <div className="flex items-start gap-3">
        {/* Sentiment accent bar */}
        <div
          className="mt-1 h-full w-0.5 shrink-0 self-stretch rounded-full"
          style={{ background: color, minHeight: 40 }}
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
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
              size={12}
              className="mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-40"
              style={{ color: "#9CA3AF" }}
            />
          </div>

          {/* Meta row */}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium" style={{ color: "#3B82F6" }}>
              {article.source}
            </span>
            <span style={{ color: "#374151" }}>·</span>
            <span className="text-[11px]" style={{ color: "#6B7280" }}>
              {formatRelativeTime(article.timestamp)}
            </span>
            <span style={{ color: "#374151" }}>·</span>
            <SentimentBadge value={article.sentiment} />
            <span className="font-mono text-[11px]" style={{ color }}>
              {formatSentiment(article.sentiment)}
            </span>
            <ConfidenceBar value={article.confidence} />

            {/* Ticker chips */}
            {article.tickers.length > 0 && (
              <>
                <span style={{ color: "#374151" }}>·</span>
                <div className="flex flex-wrap gap-1">
                  {article.tickers.map((t) => (
                    <Link
                      key={t}
                      href={`/research/${t}`}
                      className="rounded px-1.5 py-0.5 font-mono text-[10px] font-medium transition-colors hover:border-[#3B82F6] hover:text-[#93C5FD]"
                      style={{
                        background: "#1E3A8A",
                        color: "#93C5FD",
                        border: "1px solid #1E3A8A",
                      }}
                    >
                      {t}
                    </Link>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Skeleton rows ──────────────────────────────────────────────────────────────

function SkeletonArticles() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="border-b px-5 py-4" style={{ borderColor: "#374151" }}>
          <div className="flex items-start gap-3">
            <div className="mt-1 h-10 w-0.5 rounded-full" style={{ background: "#374151" }} />
            <div className="flex-1">
              <Skeleton className="mb-2 h-4 w-full" />
              <Skeleton className="mb-3 h-3 w-3/4" />
              <div className="flex gap-2">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-4 w-16 rounded-full" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </>
  );
}

// ── Pagination ─────────────────────────────────────────────────────────────────

function Pagination({
  page,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div
      className="flex items-center justify-between border-t px-5 py-3"
      style={{ borderColor: "#374151" }}
    >
      <span className="text-xs" style={{ color: "#6B7280" }}>
        {start}–{end} of {total} articles
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page === 1}
          className="flex h-7 w-7 items-center justify-center rounded transition-colors disabled:opacity-30"
          style={{ color: "#9CA3AF" }}
          onMouseEnter={(e) => { if (page > 1) (e.currentTarget as HTMLButtonElement).style.background = "#374151"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
        >
          <ChevronLeft size={14} />
        </button>
        {Array.from({ length: Math.min(totalPages, 7) }).map((_, i) => {
          // Show first, last, and pages around current
          let pg: number | null = null;
          if (totalPages <= 7) {
            pg = i + 1;
          } else if (i === 0) {
            pg = 1;
          } else if (i === 6) {
            pg = totalPages;
          } else if (page <= 4) {
            pg = i + 1;
          } else if (page >= totalPages - 3) {
            pg = totalPages - 6 + i;
          } else {
            pg = page - 2 + i;
          }

          if (pg === null) return null;
          const isActive = pg === page;

          return (
            <button
              key={i}
              onClick={() => pg && onPage(pg)}
              className="flex h-7 w-7 items-center justify-center rounded text-xs font-medium transition-colors"
              style={{
                color: isActive ? "#F9FAFB" : "#6B7280",
                background: isActive ? "#374151" : "transparent",
              }}
            >
              {pg}
            </button>
          );
        })}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page === totalPages}
          className="flex h-7 w-7 items-center justify-center rounded transition-colors disabled:opacity-30"
          style={{ color: "#9CA3AF" }}
          onMouseEnter={(e) => { if (page < totalPages) (e.currentTarget as HTMLButtonElement).style.background = "#374151"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function NewsPage() {
  const [page, setPage] = useState(1);
  const [ticker, setTicker] = useState<string>("");
  const [sentiment, setSentiment] = useState<SentimentFilter>("all");
  const [source, setSource] = useState<string>("");
  const [minConfidence, setMinConfidence] = useState(0);
  const [sortBy, setSortBy] = useState<SortBy>("recent");

  const { data: symbolsRes } = useGetTrackedSymbols();
  const trackedSymbols = symbolsRes?.status === 200 ? symbolsRes.data : [];

  const offset = (page - 1) * PAGE_SIZE;

  const { data: res, isLoading } = useGetNews({
    ticker: ticker || undefined,
    sentiment: sentiment === "all" ? undefined : sentiment,
    source: source || undefined,
    min_confidence: minConfidence > 0 ? minConfidence : undefined,
    sort_by: sortBy,
    limit: PAGE_SIZE,
    offset,
  });

  const articles = res?.status === 200 ? res.data.articles : [];
  const total = res?.status === 200 ? res.data.total : 0;

  const resetPage = useCallback(() => setPage(1), []);

  function handleTickerChange(val: string) { setTicker(val); resetPage(); }
  function handleSentimentChange(val: SentimentFilter) { setSentiment(val); resetPage(); }
  function handleSourceChange(val: string) { setSource(val); resetPage(); }
  function handleSortChange(val: SortBy) { setSortBy(val); resetPage(); }
  function handleConfidenceChange(val: number) { setMinConfidence(val); resetPage(); }

  const hasFilters = !!ticker || sentiment !== "all" || !!source || minConfidence > 0 || sortBy !== "recent";

  return (
    <div className="flex flex-col gap-4 animate-fade-up">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "#F9FAFB" }}>
          News Feed
        </h1>
        <p className="mt-0.5 text-xs" style={{ color: "#6B7280" }}>
          Sentiment-scored articles from tracked tickers
        </p>
      </div>

      {/* Filter bar */}
      <div
        className="flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3"
        style={{ background: "#1F2937", borderColor: "#374151" }}
      >
        {/* Ticker dropdown */}
        <div className="relative flex items-center">
          <select
            value={ticker}
            onChange={(e) => handleTickerChange(e.target.value)}
            className="h-8 appearance-none rounded border pl-2.5 pr-7 font-mono text-xs outline-none transition-colors focus:border-[#3B82F6]"
            style={{ background: "#111827", borderColor: "#374151", color: ticker ? "#F9FAFB" : "#6B7280" }}
          >
            <option value="">All tickers</option>
            {trackedSymbols.map((sym) => (
              <option key={sym} value={sym}>{sym}</option>
            ))}
          </select>
          <ChevronDown size={10} className="pointer-events-none absolute right-2" style={{ color: "#6B7280" }} />
        </div>

        {/* Source dropdown */}
        <div className="relative flex items-center">
          <select
            value={source}
            onChange={(e) => handleSourceChange(e.target.value)}
            className="h-8 appearance-none rounded border pl-2.5 pr-7 text-xs outline-none transition-colors focus:border-[#3B82F6]"
            style={{ background: "#111827", borderColor: "#374151", color: source ? "#F9FAFB" : "#6B7280" }}
          >
            <option value="">All sources</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <ChevronDown size={10} className="pointer-events-none absolute right-2" style={{ color: "#6B7280" }} />
        </div>

        {/* Divider */}
        <div className="h-5 w-px" style={{ background: "#374151" }} />

        {/* Sentiment toggle */}
        <div
          className="flex items-center rounded-lg border p-0.5"
          style={{ borderColor: "#374151", background: "#111827" }}
        >
          {SENTIMENT_OPTIONS.map(({ label, value }) => {
            const isActive = sentiment === value;
            const color = SENTIMENT_COLORS[value];
            return (
              <button
                key={value}
                onClick={() => handleSentimentChange(value)}
                className="rounded px-2.5 py-1 text-xs font-medium transition-all"
                style={{
                  color: isActive ? "#F9FAFB" : "#6B7280",
                  background: isActive ? "#374151" : "transparent",
                  ...(isActive && value !== "all" ? { color } : {}),
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Divider */}
        <div className="h-5 w-px" style={{ background: "#374151" }} />

        {/* Sort dropdown */}
        <div className="relative flex items-center gap-1.5">
          <ArrowUpDown size={10} style={{ color: "#6B7280" }} />
          <select
            value={sortBy}
            onChange={(e) => handleSortChange(e.target.value as SortBy)}
            className="h-8 appearance-none rounded border pl-2 pr-7 text-xs outline-none transition-colors focus:border-[#3B82F6]"
            style={{ background: "#111827", borderColor: "#374151", color: "#F9FAFB" }}
          >
            {SORT_OPTIONS.map(({ label, value }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <ChevronDown size={10} className="pointer-events-none absolute right-2" style={{ color: "#6B7280" }} />
        </div>

        {/* Divider */}
        <div className="h-5 w-px" style={{ background: "#374151" }} />

        {/* Confidence slider */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider" style={{ color: "#6B7280" }}>
            Conf ≥
          </span>
          <span className="w-7 font-mono text-[11px]" style={{ color: "#3B82F6" }}>
            {Math.round(minConfidence * 100)}%
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minConfidence}
            onChange={(e) => handleConfidenceChange(parseFloat(e.target.value))}
            className="w-24 accent-blue-500"
            style={{ height: 4 }}
          />
        </div>

        {/* Clear all */}
        {hasFilters && (
          <button
            onClick={() => {
              setTicker(""); setSentiment("all"); setSource("");
              setMinConfidence(0); setSortBy("recent"); setPage(1);
            }}
            className="ml-auto text-xs transition-colors hover:text-[#F9FAFB]"
            style={{ color: "#6B7280" }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Article list */}
      <div
        className="overflow-hidden rounded-lg border"
        style={{ background: "#1F2937", borderColor: "#374151" }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-5 py-3"
          style={{ borderColor: "#374151" }}
        >
          <div className="flex items-center gap-2">
            <Rss size={12} style={{ color: "#6B7280" }} />
            <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#6B7280" }}>
              Articles
            </span>
          </div>
          {!isLoading && (
            <span className="text-xs" style={{ color: "#4B5563" }}>
              {total.toLocaleString()} total
            </span>
          )}
        </div>

        {/* Content */}
        {isLoading ? (
          <SkeletonArticles />
        ) : articles.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16" style={{ color: "#4B5563" }}>
            <Rss size={24} />
            <p className="text-sm">No articles found</p>
            {hasFilters && (
              <p className="text-xs">Try adjusting your filters</p>
            )}
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "#374151" }}>
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        )}

        {/* Pagination */}
        <Pagination
          page={page}
          total={total}
          pageSize={PAGE_SIZE}
          onPage={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); }}
        />
      </div>
    </div>
  );
}
