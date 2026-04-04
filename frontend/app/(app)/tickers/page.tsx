"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Trash2, CheckCircle, Clock, ExternalLink, ChevronDown } from "lucide-react";
import { mutate } from "swr";

import { supabase } from "@/lib/supabaseClient";
import {
  useListTickers,
  getListTickersKey,
  updateTickerStatus,
  deleteTicker,
} from "@/lib/generated/tickers/tickers";
import type { TrackedTicker } from "@/lib/types";
import { formatRelativeTime } from "@/lib/formatters";

// ── Status badge + dropdown ────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  held:      { bg: "#10B98118", color: "#10B981" },
  tracking:  { bg: "#3B82F618", color: "#3B82F6" },
  untracked: { bg: "#37415180", color: "#6B7280" },
  new:       { bg: "#3B82F618", color: "#3B82F6" },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_COLORS[status] ?? STATUS_COLORS.tracking;
  return (
    <span
      className="rounded px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider"
      style={{ background: s.bg, color: s.color }}
    >
      {status === "new" ? "tracking" : status}
    </span>
  );
}

function StatusDropdown({
  ticker,
  value,
  canEdit,
  onUpdated,
}: {
  ticker: string;
  value: string;
  canEdit: boolean;
  onUpdated: (next: string) => void;
}) {
  const [current, setCurrent] = useState(value === "new" ? "tracking" : value);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!canEdit) return <StatusBadge status={current} />;

  async function handleSelect(next: string) {
    setOpen(false);
    if (next === current) return;
    setSaving(true);
    try {
      await updateTickerStatus(ticker, { status: next as "held" | "tracking" | "untracked" });
      setCurrent(next);
      onUpdated(next);
    } finally {
      setSaving(false);
    }
  }

  const s = STATUS_COLORS[current] ?? STATUS_COLORS.tracking;

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={saving}
        className="flex items-center gap-1 rounded px-2 py-0.5 transition-opacity disabled:opacity-50"
        style={{ background: s.bg }}
      >
        <span
          className="text-[11px] font-medium uppercase tracking-wider"
          style={{ color: s.color }}
        >
          {current}
        </span>
        <ChevronDown size={9} style={{ color: s.color }} />
      </button>

      {open && (
        <div
          className="absolute left-0 top-full z-20 mt-1 min-w-[100px] rounded border py-1 shadow-lg"
          style={{ background: "#1F2937", borderColor: "#374151" }}
        >
          {(["tracking", "held", "untracked"] as const).map((opt) => {
            const os = STATUS_COLORS[opt];
            return (
              <button
                key={opt}
                onClick={() => handleSelect(opt)}
                className="flex w-full items-center px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider transition-colors hover:bg-[#374151]"
                style={{ color: opt === current ? os.color : "#9CA3AF" }}
              >
                {opt}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Delete button ──────────────────────────────────────────────────────────────

function DeleteButton({
  ticker,
  canDelete,
  onDeleted,
}: {
  ticker: string;
  canDelete: boolean;
  onDeleted: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!confirm) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setConfirm(false);
        setError(null);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [confirm]);

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteTicker(ticker);
      onDeleted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div ref={ref} className="relative inline-flex justify-end">
      <button
        onClick={() => canDelete && setConfirm(true)}
        disabled={!canDelete}
        title={canDelete ? "Delete ticker" : "You can only delete tickers you added"}
        className="flex h-7 w-7 items-center justify-center rounded transition-colors"
        style={{
          color: canDelete ? "#6B7280" : "#374151",
          cursor: canDelete ? "pointer" : "not-allowed",
        }}
        onMouseEnter={(e) => canDelete && ((e.currentTarget as HTMLButtonElement).style.background = "#7F1D1D40")}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "transparent")}
      >
        <Trash2 size={13} />
      </button>

      {confirm && (
        <div
          className="absolute right-0 top-full z-20 mt-1 rounded border p-3 shadow-lg"
          style={{ background: "#1F2937", borderColor: "#374151", minWidth: "130px" }}
        >
          <p className="mb-2.5 text-[11px] text-white">
            Remove <span style={{ fontFamily: "var(--font-jetbrains-mono)" }}>{ticker}</span>?
          </p>
          <div className="flex gap-1.5">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 rounded py-1 text-[11px] font-medium transition-colors disabled:opacity-50"
              style={{ background: "#EF444420", color: "#EF4444" }}
            >
              {deleting ? "…" : "remove"}
            </button>
            <button
              onClick={() => { setConfirm(false); setError(null); }}
              className="flex-1 rounded py-1 text-[11px] transition-colors"
              style={{ background: "#37415180", color: "#9CA3AF" }}
            >
              cancel
            </button>
          </div>
          {error && (
            <p className="mt-1.5 text-[10px]" style={{ color: "#EF4444" }}>{error}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Table row ──────────────────────────────────────────────────────────────────

function TickerRow({
  ticker,
  canAct,
  onStatusChange,
  onDeleted,
}: {
  ticker: TrackedTicker;
  canAct: boolean;
  onStatusChange: (ticker: string, next: string) => void;
  onDeleted: (ticker: string) => void;
}) {
  const router = useRouter();

  return (
    <tr className="border-b" style={{ borderColor: "#1F2937" }}>
      {/* Ticker + link */}
      <td className="py-3 pl-4 pr-2">
        <button
          onClick={() => router.push(`/research/${ticker.ticker}`)}
          className="flex items-center gap-1.5 group"
        >
          <span
            className="text-sm font-semibold tracking-wide text-white group-hover:text-blue-400 transition-colors"
            style={{ fontFamily: "var(--font-jetbrains-mono)" }}
          >
            {ticker.ticker}
          </span>
          <ExternalLink
            size={10}
            className="opacity-0 group-hover:opacity-50 transition-opacity"
            style={{ color: "#3B82F6" }}
          />
        </button>
      </td>

      {/* Company name */}
      <td className="py-3 px-2">
        <span className="text-sm text-white truncate block">{ticker.name}</span>
      </td>

      {/* Status dropdown */}
      <td className="py-3 px-2">
        <StatusDropdown
          ticker={ticker.ticker}
          value={ticker.status}
          canEdit={canAct}
          onUpdated={(next) => onStatusChange(ticker.ticker, next)}
        />
      </td>

      {/* Sentiment */}
      <td className="py-3 px-2">
        {ticker.sentiment_ready ? (
          <div className="flex items-center gap-1.5">
            <CheckCircle size={11} style={{ color: "#10B981" }} />
            <span className="text-[11px]" style={{ color: "#6B7280" }}>Ready</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <Clock size={11} style={{ color: "#F59E0B" }} />
            <span className="text-[11px]" style={{ color: "#6B7280" }}>Pending</span>
          </div>
        )}
      </td>

      {/* Added by */}
      <td className="py-3 px-2">
        <span
          className="text-[11px] truncate block"
          style={{ color: "#6B7280" }}
          title={ticker.added_by ?? undefined}
        >
          {ticker.added_by ?? <span style={{ color: "#374151" }}>—</span>}
        </span>
      </td>

      {/* Added at */}
      <td className="py-3 px-2">
        <span className="text-[11px]" style={{ color: "#6B7280" }}>
          {ticker.added_at ? formatRelativeTime(ticker.added_at) : "—"}
        </span>
      </td>

      {/* Last scraped */}
      <td className="py-3 px-2">
        <span className="text-[11px]" style={{ color: "#6B7280" }}>
          {ticker.last_scraped ? formatRelativeTime(ticker.last_scraped) : "—"}
        </span>
      </td>

      {/* Actions */}
      <td className="py-3 pl-2 pr-4">
        <div className="flex justify-end">
          <DeleteButton
            ticker={ticker.ticker}
            canDelete={canAct}
            onDeleted={() => onDeleted(ticker.ticker)}
          />
        </div>
      </td>
    </tr>
  );
}

// ── Skeleton row ───────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr className="border-b" style={{ borderColor: "#1F2937" }}>
      {[96, 192, 80, 80, 140, 96, 96, 28].map((w, i) => (
        <td key={i} className="py-3 px-2 first:pl-4 last:pr-4">
          <div
            className="h-3.5 animate-pulse rounded"
            style={{ background: "#374151", width: `${w}px` }}
          />
        </td>
      ))}
    </tr>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

const STATUS_ORDER: Record<string, number> = { held: 0, tracking: 1, new: 1, untracked: 2 };

export default function TickersPage() {
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) =>
      setUserEmail(data.user?.email ?? null)
    );
  }, []);

  const { data: raw, isLoading } = useListTickers();
  const tickers = (raw as { data: TrackedTicker[] } | undefined)?.data ?? [];

  const sorted = [...tickers].sort(
    (a, b) => (STATUS_ORDER[a.status] ?? 1) - (STATUS_ORDER[b.status] ?? 1)
  );

  const activeCount = tickers.filter((t) => t.status !== "untracked").length;

  function handleDeleted(ticker: string) {
    // Optimistically remove from cache, then revalidate
    mutate(
      getListTickersKey(),
      (current: unknown) => {
        if (!current) return current;
        const c = current as { data: TrackedTicker[]; status: number; headers: Headers };
        return { ...c, data: c.data.filter((t) => t.ticker !== ticker) };
      },
      { revalidate: true }
    );
  }

  function handleStatusChange(ticker: string, next: string) {
    mutate(
      getListTickersKey(),
      (current: unknown) => {
        if (!current) return current;
        const c = current as { data: TrackedTicker[]; status: number; headers: Headers };
        return {
          ...c,
          data: c.data.map((t) => (t.ticker === ticker ? { ...t, status: next } : t)),
        };
      },
      { revalidate: false }
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-end gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Tracked Tickers</h1>
          <p className="mt-1 text-sm" style={{ color: "#9CA3AF" }}>
            Manage the analyst watchlist — update status or remove tickers you added.
          </p>
        </div>
        {!isLoading && (
          <span
            className="mb-0.5 rounded px-2 py-0.5 text-xs font-medium"
            style={{ background: "#1F2937", color: "#6B7280" }}
          >
            {activeCount} active
          </span>
        )}
      </div>

      {/* Table */}
      <style>{`
        .tickers-table tbody tr:last-child td:first-child { border-radius: 0 0 0 8px; }
        .tickers-table tbody tr:last-child td:last-child  { border-radius: 0 0 8px 0; }
      `}</style>
      <div
        className="rounded-lg border"
        style={{ borderColor: "#374151" }}
      >
        <table className="tickers-table w-full table-fixed" style={{ borderCollapse: "separate", borderSpacing: 0 }}>
          <colgroup>
            <col style={{ width: "96px" }} />
            <col style={{ width: "180px" }} />
            <col style={{ width: "110px" }} />
            <col style={{ width: "88px" }} />
            <col style={{ width: "160px" }} />
            <col style={{ width: "104px" }} />
            <col style={{ width: "104px" }} />
            <col style={{ width: "52px" }} />
          </colgroup>
          <thead>
            <tr style={{ background: "#1F2937" }}>
              {["Ticker", "Company", "Status", "Sentiment", "Added By", "Added", "Last Scraped", ""].map(
                (h, i, arr) => (
                  <th
                    key={i}
                    className="py-2.5 px-2 text-left text-[10px] font-medium uppercase tracking-widest first:pl-4 last:pr-4"
                    style={{
                      color: "#6B7280",
                      borderRadius: i === 0 ? "8px 0 0 0" : i === arr.length - 1 ? "0 8px 0 0" : undefined,
                    }}
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody style={{ background: "#111827" }}>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
            ) : sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="py-12 text-center text-sm"
                  style={{ color: "#4B5563" }}
                >
                  No tickers tracked yet — search a ticker in Research to add one.
                </td>
              </tr>
            ) : (
              sorted.map((t) => (
                <TickerRow
                  key={t.ticker}
                  ticker={t}
                  canAct={!!userEmail && userEmail === t.added_by}
                  onStatusChange={handleStatusChange}
                  onDeleted={handleDeleted}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
