"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, TrendingUp } from "lucide-react";

// Skeleton card for "Recently Tracked" placeholder
function TickerSkeletonCard() {
  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: "#1f2937", borderColor: "#374151" }}
    >
      {/* Ticker + status row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="h-4 w-16 animate-pulse rounded" style={{ background: "#374151" }} />
        <div className="h-5 w-14 animate-pulse rounded" style={{ background: "#374151" }} />
      </div>
      {/* Company name */}
      <div className="mb-3 h-3 w-28 animate-pulse rounded" style={{ background: "#374151" }} />
      {/* Metrics row */}
      <div className="flex gap-3">
        <div className="h-3 w-20 animate-pulse rounded" style={{ background: "#374151" }} />
        <div className="h-3 w-16 animate-pulse rounded" style={{ background: "#374151" }} />
      </div>
    </div>
  );
}

export default function ResearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

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
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <TickerSkeletonCard />
          <TickerSkeletonCard />
          <TickerSkeletonCard />
          <TickerSkeletonCard />
        </div>
      </section>
    </div>
  );
}
