"use client";

import type { Keyword } from "@/lib/types";

interface Props {
  keywords: Keyword[];
}

export function KeywordCloud({ keywords }: Props) {
  if (!keywords.length) {
    return (
      <div className="flex items-center justify-center text-xs" style={{ color: "#6B7280", height: 120 }}>
        No keywords
      </div>
    );
  }

  const maxCount = Math.max(...keywords.map((k) => k.count));
  const minCount = Math.min(...keywords.map((k) => k.count));
  const range = Math.max(maxCount - minCount, 1);

  function sizeFor(count: number): number {
    const t = (count - minCount) / range;
    return 11 + t * 10; // 11px → 21px
  }

  function opacityFor(count: number): number {
    const t = (count - minCount) / range;
    return 0.45 + t * 0.55; // 45% → 100%
  }

  // Blue shades based on frequency
  const colors = ["#93C5FD", "#60A5FA", "#3B82F6", "#2563EB", "#1D4ED8"];
  function colorFor(count: number): string {
    const t = (count - minCount) / range;
    const idx = Math.round(t * (colors.length - 1));
    return colors[idx];
  }

  return (
    <div className="flex flex-wrap gap-2">
      {keywords.slice(0, 25).map(({ word, count }) => (
        <span
          key={word}
          className="rounded-full px-2.5 py-1 font-medium leading-none transition-opacity hover:opacity-100"
          style={{
            fontSize: sizeFor(count),
            color: colorFor(count),
            opacity: opacityFor(count),
            background: `${colorFor(count)}15`,
            border: `1px solid ${colorFor(count)}25`,
            cursor: "default",
          }}
          title={`${count} mention${count !== 1 ? "s" : ""}`}
        >
          {word}
        </span>
      ))}
    </div>
  );
}
