# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

Foundation is set up. Both `frontend/` and `backend/` are scaffolded and running. The platform is a unified web app for Kancil Capital (student investment fund, University of Manchester) that adapts three existing Python research tools into a single Next.js + FastAPI web platform.

## Monorepo Structure

```
kancil_portfolio_manager/
├── frontend/          # Next.js 16 + TypeScript + Tailwind v4  (bun)
├── backend/           # FastAPI + Python 3.12  (uv)
│   ├── routers/       # API route handlers
│   ├── services/      # Business logic
│   ├── workers/       # Background jobs (APScheduler, runs in-process with FastAPI)
│   ├── db/            # Supabase client + Pydantic models
│   ├── core/          # Config, FinBERT inference
│   └── supabase/      # Supabase CLI project: config.toml, migrations/, seed.sql
├── docs/              # All spec documents
└── models/            # Trained ML artifacts (pead_model.joblib)
```

## Commands

**Frontend** (package manager: `bun`):
```bash
cd frontend
bun install
bun run dev        # dev server  → http://localhost:3000
bun run build      # production build
bun run lint       # ESLint
```

**Backend** (package manager: `uv`, run from `backend/` dir):
```bash
cd backend
uv sync --group dev          # install all deps including dev
uv run uvicorn main:app --reload --port 8000   # dev server
uv run pytest                                  # run all tests
uv run pytest tests/test_services.py -k "test_pead"
uv run ruff check .                            # lint
```

> **Note on imports:** The uv project root is `backend/`, so imports are relative to that dir — e.g. `from core.config import settings`, not `from backend.core.config`. Uvicorn is run as `uvicorn main:app`, not `uvicorn backend.main:app`.

**Both together:**
```bash
make dev           # starts both frontend and backend in parallel
make install       # installs deps for both
```

**Database** (Supabase CLI, run from `backend/`; needs Docker running):
```bash
cd backend
supabase start                     # local Postgres + Auth + Studio (http://localhost:54323)
supabase status -o env             # local URL + keys to put in backend/.env and frontend/.env.local
supabase db diff --schema public -f <name>   # turn local schema changes into supabase/migrations/<ts>_<name>.sql
supabase migration new <name>      # or write a migration by hand
supabase db reset                  # rebuild local DB from all migrations + supabase/seed.sql
supabase stop
```

### Database workflow

Full step-by-step guide: `docs/database_workflow.md`.

- Preferred way to make a schema change: change the local DB in Studio (http://localhost:54323), then `supabase db diff --schema public -f <name>`, read the generated SQL (renames come out as drop + add — rewrite them as `RENAME`), and verify with `supabase db reset`. Always pass `--schema public`, or the diff includes Supabase-internal noise such as `drop extension "pg_net"`. Hand-written migrations (`supabase migration new`) are for renames, data backfills, and anything the diff gets wrong.
- Schema lives in `backend/supabase/migrations/` (timestamped `.sql` files); every schema change is a new migration, reviewed in a PR. Never edit a migration that has already been applied, and never change the production schema through the Supabase dashboard.
- Develop against the local stack (`supabase start`), not production. `supabase/seed.sql` holds small fake data and two test logins (`admin@kancil.test`, `analyst@kancil.test`; password in the file) and only runs locally.
- Env files, same layout in `backend/` and `frontend/`: `.env` holds production/shared values; an optional `.env.local` overrides the Supabase URL and keys to point at the local stack (values from `supabase status -o env`). Delete or rename `.env.local` to go back to production. Local auth uses `localhost:3000` as its redirect URL.
- CI (`.github/workflows/`): `db-check.yml` runs on PRs touching `backend/supabase/` — applies all migrations + seed to a fresh DB and dry-runs `db push` against production. `db-deploy.yml` runs `supabase db push` on merge to `main`. Both authenticate with the `SUPABASE_ACCESS_TOKEN` repo secret only (no DB password needed).
- The first migration (`*_remote_schema.sql`) is a baseline pulled from production; it replaced the old hand-applied `docs/migrations/001_v1_schema.sql`.

## Architecture

### Data Flow

```
Next.js Frontend (SWR hooks)
    ↕ HTTP JSON + Supabase JWT auth
    ↕ /api/* → proxied to FastAPI via next.config.ts rewrites
FastAPI Backend  (localhost:8000)
    ├── On-demand: price/technicals (yfinance), PEAD features (math), ML inference
    │   (PEAD signals cached in memory for 12h — not stored in the DB)
    └── Cached: EPS/SUE (Alpha Vantage, ~90-day TTL), news sentiment (FinBERT, stored)
        ↕
Supabase PostgreSQL
    ↑ Background workers (APScheduler, in-process)
    └── sentiment_pipeline.py — 07:00 UTC daily
```

### Key Backend Services

- **`sentiment_service.py`** — wraps Supabase queries + FinBERT inference (adapted from SentimentPulse)
- **`pead_service.py`** — computes 28 features + XGBoost inference for earnings outperformance probability
- **`market_service.py`** — yfinance wrapper for OHLCV, technicals (RSI-14, MA20/MA50, ATR)
- **`eps_service.py`** — Alpha Vantage wrapper with strict cache: never re-fetches unless >90 days stale; log every API call

### Tracked Ticker Lifecycle

`new` → (first search triggers scrape + FinBERT) → `tracking` → (analyst marks position) → `held` → (coverage dropped) → `untracked`

New ticker API flow: return `status: "new"`, `sentiment_ready: false` immediately, trigger background job, frontend polls `/api/research/{ticker}/sentiment-status` every 5s.

### Database Tables

**Existing (from SentimentPulse):** `articles`, `sentiments`

**New for v1:**
- `tracked_tickers` — ticker lifecycle management (`ticker`, `status`, `sentiment_ready`, `last_scraped`)
- `eps_cache` — Alpha Vantage EPS/SUE cache with `fetched_at` for TTL enforcement

### Authentication

Supabase Auth with JWT custom claims. Roles: `admin` (CIO), `analyst`, `readonly`. Next.js middleware checks JWT on every route; FastAPI verifies via Supabase public key.

### Frontend Data Fetching

SWR hooks for all endpoints (`useTickerData`, `useCalendar`, `useNews`). Skeleton loaders (not spinners) for all loading states. `lib/api.ts` is the typed HTTP client; `lib/types.ts` holds shared interfaces.

## Key API Endpoints

| Endpoint | Notes |
|----------|-------|
| `GET /api/health` | Health check — `{ status, version }` |
| `GET /api/research/{ticker}` | Aggregated deep-dive: price, sentiment, PEAD signals, articles |
| `GET /api/research/{ticker}/sentiment-status` | Polling endpoint: `{ ready, article_count, estimated_seconds_remaining }` |
| `GET /api/calendar?days_ahead=30` | Earnings calendar with PEAD signals (computed on demand, cached 12h) |
| `GET /api/news?ticker=&sentiment=&source=&limit=20&offset=0` | Paginated sentiment feed |
| `GET/POST/PATCH /api/tickers` | Tracked ticker management |

## Environment Variables

Backend (`backend/.env`; `.env.local` overrides it for local Supabase):
```
SUPABASE_URL
SUPABASE_SECRET_KEY
SUPABASE_JWT_SECRET
ALPHA_VANTAGE_API_KEY
CORS_ORIGINS=["http://localhost:3000"]
```

Frontend (`frontend/.env`; `.env.local` overrides it for local Supabase):
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
```

## Design System

Dark institutional theme. Key tokens:
- Backgrounds: `#111827` / `#1F2937` / `#374151`
- Brand: `#3B82F6` (primary blue), `#1E3A8A` (navy)
- Semantic: `#10B981` (positive), `#EF4444` (negative), `#F59E0B` (neutral/amber)
- Font: Inter; **monospace for all financial figures** (prices, returns %) to prevent column jitter
- Layout: fixed 240px left sidebar + scrollable main (max 1280px, 12-col grid)
- Charts: `lightweight-charts` (TradingView) for candlesticks; Recharts for others

## Existing Tools Being Adapted

Three Python research tools are being ported — their logic is adapted, but they are **not imported as dependencies**:

| Original | New Location | Status |
|----------|-------------|--------|
| SentimentPulse scrapers + FinBERT pipeline | `backend/workers/sentiment_pipeline.py` + `backend/core/sentiment.py` | Rewritten async |
| SentimentPulse Dash app | Retired | Replaced by Next.js frontend |
| PEAD feature engineering + XGBoost | `backend/services/pead_service.py` | Rewritten with Pydantic I/O |
| PEAD notebooks + CSV outputs | Retired | Data lives in Supabase |
| Earnings Prediction feature set | Merged into `pead_service.py` | Best 28 features selected |

## Implementation Phases

0. Foundation — project setup, DB schema, auth ✅
1. Backend services — all routers, services, background workers
2. Research Terminal — ticker deep-dive page (`/research/[ticker]`)
3. Calendar + News — `/calendar` and `/news` pages
4. Pipeline + Streaming — producer-consumer sentiment pipeline, WebSocket scrape-stream for new ticker UX
5. Polish + Deploy — Vercel (frontend), Railway/Render (backend + workers)

## Spec Documents

- `docs/technical_spec.md` — repository structure, DB schema, API contract, component architecture
- `docs/platform_vision_draft.md` — roadmap, design decisions, open questions
- `docs/ui_design_spec.md` — full design language, component patterns, iconography
- `docs/tools_audit.md` — detailed audit of the three existing Python tools
