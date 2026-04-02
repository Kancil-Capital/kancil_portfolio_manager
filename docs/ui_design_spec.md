# Kancil Capital Platform — UI Design Specification

*Date: 2026-04-02 | Based on: kancilcapital.com website + 2025 Annual Report*

---

## 1. Design Language

The platform follows Kancil's existing visual identity: **dark, institutional, tech-forward**. The website uses a full dark theme with an animated VANTA globe and bright blue accents. The annual report pairs deep navy fills with white text and clean section structure. The platform merges both — dark surfaces for a professional terminal feel, blue/white brand anchoring throughout.

Reference pages studied:
- `kancilcapital.com/index.html` — dark theme, animated globe, bar chart, blue primary
- `kancilcapital.com/about.html` — structure, values, team org
- `kancilcapital.com/research.html` — report cards, clean section hierarchy
- `kancilcapital.com/team.html` — bootcamp/member portal feel
- Annual Report 2025 — deep navy headers, white body, city skyline motif

---

## 2. Color Palette

### Core

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-base` | `#111827` | Page background (matches website) |
| `--bg-surface` | `#1F2937` | Cards, panels, sidebars |
| `--bg-elevated` | `#374151` | Dropdowns, tooltips, hover states |
| `--border` | `#374151` | Dividers, input borders |

### Brand

| Token | Hex | Usage |
|-------|-----|-------|
| `--blue-primary` | `#3B82F6` | Primary buttons, links, active nav, chart lines (matches website) |
| `--blue-dark` | `#1D4ED8` | Hover on primary buttons |
| `--blue-navy` | `#1E3A8A` | Section headers, badges, annual report anchor color |
| `--blue-muted` | `#1E40AF` | Secondary buttons, pill backgrounds |
| `--white` | `#FFFFFF` | Primary text on dark backgrounds |

### Semantic (Financial)

| Token | Hex | Usage |
|-------|-----|-------|
| `--positive` | `#10B981` | Positive returns, positive sentiment, beats (matches website green) |
| `--positive-muted` | `#064E3B` | Positive badge background |
| `--negative` | `#EF4444` | Negative returns, negative sentiment, misses |
| `--negative-muted` | `#7F1D1D` | Negative badge background |
| `--neutral` | `#F59E0B` | Neutral sentiment, warnings, caution |
| `--neutral-muted` | `#78350F` | Neutral badge background |

### Text

| Token | Hex | Usage |
|-------|-----|-------|
| `--text-primary` | `#F9FAFB` | Body text, headings |
| `--text-secondary` | `#9CA3AF` | Labels, metadata, timestamps |
| `--text-muted` | `#6B7280` | Disabled, placeholder text |

---

## 3. Typography

**Primary font:** `Inter` (Google Fonts) — clean, professional, widely used in fintech dashboards

**Fallback:** `system-ui, -apple-system, sans-serif`

| Style | Size | Weight | Usage |
|-------|------|--------|-------|
| Display | 2rem (32px) | 700 | Page titles |
| Heading 1 | 1.5rem (24px) | 600 | Section headers |
| Heading 2 | 1.25rem (20px) | 600 | Card titles |
| Heading 3 | 1rem (16px) | 600 | Sub-section labels |
| Body | 0.875rem (14px) | 400 | Default text |
| Small | 0.75rem (12px) | 400 | Timestamps, metadata |
| Mono | `JetBrains Mono` / `monospace` | 400 | Numbers, prices, percentages |

> Use monospace for all financial figures (prices, returns, percentages) — prevents column jitter when numbers update.

---

## 4. Component Patterns

### Sentiment Badge
Three-state pill for positive / neutral / negative:

```
Positive:  [ ▲ +0.72 ]  bg: --positive-muted   text: --positive
Neutral:   [ ◆  0.02 ]  bg: --neutral-muted    text: --neutral
Negative:  [ ▼ -0.45 ]  bg: --negative-muted   text: --negative
```

### Return Badge
Same three-state, applied to price returns and portfolio P&L.

### Ticker Chip
```
[ NVDA ]  — rounded pill, bg: --blue-navy, text: --white, hover: --blue-primary border
```

### Cards
- Background: `--bg-surface`
- Border: 1px solid `--border`
- Border-radius: 8px
- Padding: 16px 20px
- No drop shadows (flat, matches website aesthetic)

### Tables
- Header row: `--bg-elevated`, text `--text-secondary`, uppercase, 0.7rem
- Row hover: `--bg-elevated`
- Borders: horizontal only (1px `--border`)
- Number columns: right-aligned, monospace

### Charts (Recharts / Plotly)
- Background: `--bg-surface`
- Grid lines: `--border` at 0.5 opacity
- Primary line/bar: `--blue-primary`
- Positive fill: `--positive` at 0.3 opacity
- Negative fill: `--negative` at 0.3 opacity
- Tooltip: `--bg-elevated`, border `--border`, text `--text-primary`
- No chart borders — blend into card background

### Navigation (Sidebar)
- Background: `--bg-surface`
- Active item: left border 2px `--blue-primary`, text `--white`, bg `--bg-elevated`
- Inactive item: text `--text-secondary`, hover text `--white`
- Logo: white wordmark on `--bg-surface`

---

## 5. Layout

**Structure:** Fixed left sidebar (240px) + scrollable main content area

```
┌──────────────┬────────────────────────────────────────────┐
│              │  Topbar: search + user                     │
│   Sidebar    ├────────────────────────────────────────────┤
│   240px      │                                            │
│              │  Main content area                         │
│  [Logo]      │  (scrollable)                              │
│              │                                            │
│  Navigation  │                                            │
│  ──────────  │                                            │
│  Research    │                                            │
│  Calendar    │                                            │
│  News        │                                            │
│  Portfolio   │                                            │
│  Risk        │                                            │
│              │                                            │
│  ──────────  │                                            │
│  [User]      │                                            │
└──────────────┴────────────────────────────────────────────┘
```

**Content max-width:** 1280px, centered with 24px horizontal padding

**Grid:** 12-column grid; cards typically span 4, 6, or 12 columns

---

## 6. Page-Specific Layouts

### Research — Ticker Deep-Dive

```
┌─ Ticker Header ──────────────────────────────────────────┐
│  NVDA  NVIDIA Corporation    $875.40  ▲ +1.2%  Holding  │
└──────────────────────────────────────────────────────────┘

┌─ Price Chart (8 col) ──────────┐  ┌─ PEAD Signal (4 col) ──────┐
│  Candlestick + sentiment line  │  │  Outperform prob: 62%      │
│                                │  │  Next earnings: 14d        │
│                                │  │  SUE: +1.8  Beat streak: 3 │
└────────────────────────────────┘  └────────────────────────────┘

┌─ Sentiment Trend (6 col) ──────┐  ┌─ Lag Correlation (6 col) ──┐
│  Daily mean sentiment bar      │  │  Heatmap 0–7 day lags      │
└────────────────────────────────┘  └────────────────────────────┘

┌─ News Feed (8 col) ────────────┐  ┌─ Keyword Cloud (4 col) ────┐
│  Sentiment-tagged articles     │  │                            │
└────────────────────────────────┘  └────────────────────────────┘
```

### Earnings Calendar

Full-width sortable table. Columns: Ticker | Company | Earnings Date | Days | Sentiment | SUE | PEAD Prob | Beat Rate. Click row → opens ticker deep-dive.

### News Feed

Two-column card grid. Each card: headline, source badge, sentiment badge, ticker chips, timestamp.

---

## 7. Iconography

Use **Feather Icons** (already used on the website — `feather.replace()`). Clean, consistent 1.5px stroke weight, 24px default.

Key icons:
- `trending-up` / `trending-down` — returns
- `calendar` — earnings calendar
- `rss` — news feed
- `bar-chart-2` — research terminal
- `shield` — risk dashboard (v3)
- `briefcase` — portfolio (v2)
- `search` — ticker search

---

## 8. Loading & Empty States

**Loading:** Skeleton loaders (pulsing `--bg-elevated` blocks) — never spinners on content areas. Charts show a pulsing placeholder at full height.

**On-demand first fetch message (new ticker):**
```
┌─────────────────────────────────────────────┐
│  ⟳  Fetching sentiment data for AAPL...     │
│     This takes ~20s for new tickers.        │
│     Price data is ready now ↓               │
└─────────────────────────────────────────────┘
```

**Empty state (no articles):** Centered icon + short message, never a blank panel.

---

## 9. Brand Anchor — Kancil Visual Motifs

The annual report uses a **city skyline silhouette** (Kuala Lumpur / Manchester) as a footer motif. The website uses a **3D animated globe** as the hero background.

For the platform:
- Use the city skyline as a subtle SVG pattern in empty states or the login/landing page
- Keep the animated globe for the login/splash screen only — too distracting in a data-heavy interface
- Kancil logo (white version) in the sidebar top

---

## 10. Dark Theme Justification

A dark theme is the right call for a financial research tool:
- Matches the existing website identity
- Reduces eye strain during long research sessions
- Makes chart colors pop (green/red sentiment, price lines)
- Standard in professional terminal UIs (Bloomberg, FactSet use dark or high-contrast themes)
- Differentiates the platform from generic light-theme dashboards
