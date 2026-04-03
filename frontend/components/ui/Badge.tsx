import { sentimentColor, sentimentLabel } from "@/lib/formatters";

// ── Sentiment badge (▲/◆/▼ coloured pill) ─────────────────────────────────────

interface SentimentBadgeProps {
  value: number;
  className?: string;
}

export function SentimentBadge({ value, className = "" }: SentimentBadgeProps) {
  const label = sentimentLabel(value);
  const color = sentimentColor(value);
  const icon = label === "positive" ? "▲" : label === "negative" ? "▼" : "◆";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium ${className}`}
      style={{
        color,
        background: `${color}18`,
        border: `1px solid ${color}30`,
      }}
    >
      <span style={{ fontSize: 8 }}>{icon}</span>
      {label}
    </span>
  );
}

// ── Return badge (▲/▼ with percentage) ────────────────────────────────────────

interface ReturnBadgeProps {
  value: number;
  digits?: number;
  className?: string;
}

export function ReturnBadge({ value, digits = 2, className = "" }: ReturnBadgeProps) {
  const isPos = value >= 0;
  const color = isPos ? "#10B981" : "#EF4444";
  const arrow = isPos ? "▲" : "▼";
  const pct = `${Math.abs(value * 100).toFixed(digits)}%`;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium font-mono ${className}`}
      style={{
        color,
        background: `${color}18`,
        border: `1px solid ${color}30`,
      }}
    >
      <span style={{ fontSize: 8 }}>{arrow}</span>
      {isPos ? "+" : ""}
      {pct}
    </span>
  );
}

// ── Status badge ───────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  held:      { color: "#3B82F6", bg: "#3B82F618", label: "Holding" },
  tracking:  { color: "#F59E0B", bg: "#F59E0B18", label: "Tracking" },
  new:       { color: "#8B5CF6", bg: "#8B5CF618", label: "New" },
  untracked: { color: "#6B7280", bg: "#6B728018", label: "Untracked" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.untracked;
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider ${className}`}
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.color}30` }}
    >
      {s.label}
    </span>
  );
}
