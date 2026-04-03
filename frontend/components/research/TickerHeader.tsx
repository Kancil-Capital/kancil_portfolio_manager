"use client";

import { TrendingUp, TrendingDown } from "lucide-react";
import { ReturnBadge, StatusBadge } from "@/components/ui/Badge";
import { formatPrice } from "@/lib/formatters";
import type { TickerDeepDive } from "@/lib/types";

interface Props {
  data: TickerDeepDive;
}

export function TickerHeader({ data }: Props) {
  const { ticker, name, sector, status, price } = data;
  const isPos = price.change_pct >= 0;

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-4 rounded-lg border px-6 py-4"
      style={{ background: "#1F2937", borderColor: "#374151" }}
    >
      {/* Left: ticker + name + sector */}
      <div className="flex items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span
              className="text-2xl font-bold tracking-tight text-white font-mono"
            >
              {ticker}
            </span>
            <StatusBadge status={status} />
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <span className="text-sm" style={{ color: "#9CA3AF" }}>
              {name}
            </span>
            {sector && (
              <>
                <span style={{ color: "#374151" }}>·</span>
                <span
                  className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider"
                  style={{ background: "#1E3A8A", color: "#93C5FD" }}
                >
                  {sector}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Right: price + change */}
      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className="flex items-baseline gap-2">
            <span
              className="text-2xl font-semibold font-mono"
              style={{ color: "#F9FAFB" }}
            >
              ${formatPrice(price.current)}
            </span>
            <ReturnBadge value={price.change_pct} />
          </div>
          <div className="mt-0.5 flex items-center justify-end gap-1 text-xs" style={{ color: "#6B7280" }}>
            {isPos ? (
              <TrendingUp size={11} style={{ color: "#10B981" }} />
            ) : (
              <TrendingDown size={11} style={{ color: "#EF4444" }} />
            )}
            <span>vs prev close</span>
          </div>
        </div>
      </div>
    </div>
  );
}
