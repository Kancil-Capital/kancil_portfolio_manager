import { format, formatDistanceToNow, parseISO } from "date-fns";

// ── Numbers ────────────────────────────────────────────────────────────────────

export function formatPrice(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatPct(value: number, { signed = false } = {}): string {
  const formatted = Math.abs(value).toFixed(2) + "%";
  if (!signed) return formatted;
  return value >= 0 ? `+${formatted}` : `-${formatted}`;
}

export function formatSentiment(value: number): string {
  return (value >= 0 ? "+" : "") + value.toFixed(3);
}

export function formatProb(value: number): string {
  return Math.round(value * 100) + "%";
}

export function formatSue(value: number): string {
  return (value >= 0 ? "+" : "") + value.toFixed(2);
}

export function formatVolume(value: number): string {
  if (value >= 1_000_000_000) return (value / 1_000_000_000).toFixed(1) + "B";
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
  if (value >= 1_000) return (value / 1_000).toFixed(1) + "K";
  return value.toString();
}

// ── Dates ──────────────────────────────────────────────────────────────────────

export function formatDate(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy");
}

export function formatDateShort(iso: string): string {
  return format(parseISO(iso), "MMM d");
}

export function formatRelativeTime(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true });
}

export function formatEarningsDate(iso: string, daysTo: number): string {
  const label = format(parseISO(iso), "MMM d");
  if (daysTo === 0) return `${label} (today)`;
  if (daysTo === 1) return `${label} (tomorrow)`;
  return `${label} (${daysTo}d)`;
}

// ── Sentiment colour ───────────────────────────────────────────────────────────

export function sentimentColor(value: number): string {
  if (value > 0.1) return "#10B981";   // positive green
  if (value < -0.1) return "#EF4444";  // negative red
  return "#F59E0B";                     // neutral amber
}

export function sentimentLabel(value: number): "positive" | "neutral" | "negative" {
  if (value > 0.1) return "positive";
  if (value < -0.1) return "negative";
  return "neutral";
}
