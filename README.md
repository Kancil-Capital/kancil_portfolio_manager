# Kancil Portfolio Manager

Research platform for Kancil Capital: ticker deep-dives (price, news sentiment, earnings-drift signals), an earnings calendar and a news feed. Next.js frontend, FastAPI backend, Supabase database.

## Setup

### 1. Install the tools

| Tool | What it's for | Install (macOS) |
| --- | --- | --- |
| [bun](https://bun.sh) | Frontend packages and scripts | `brew install oven-sh/bun/bun` |
| [uv](https://docs.astral.sh/uv/) | Python and backend packages | `brew install uv` |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the local database | Download and open it |
| [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) | Local database and migrations | `brew install supabase/tap/supabase` |

Use `bun` and `uv` for everything in this repo, never npm or pip, even if an AI suggests it.

### 2. Clone and install

```bash
git clone git@github.com:Kancil-Capital/kancil_portfolio_manager.git
cd kancil_portfolio_manager
make install
```

`make install` creates the backend's Python environment (`backend/.venv`) and installs the frontend's packages.

Then download the FinBERT sentiment model (about 440 MB) into `models/finbert/`:

```bash
cd backend && uv run hf download ProsusAI/finbert \
  --include "*.json" --include "*.txt" --include "pytorch_model.bin" \
  --local-dir ../models/finbert && cd ..
```

The backend loads it at startup, so it won't start without it. The other model the backend uses, `models/pead_model.joblib` (earnings-drift signals), is already in the repo; `backend/scripts/train_pead_model.py` rebuilds it.

### 3. Start a local database

With Docker Desktop running:

```bash
cd backend && supabase start && cd ..
```

This runs Supabase on your laptop, built from the repo's migrations and filled with fake data from `backend/supabase/seed.sql`. The first run downloads Docker images and takes a few minutes.

### 4. Create the env files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
make db-env
```

- `.env` holds production settings. For local work the only value you need is `ALPHA_VANTAGE_API_KEY` in `backend/.env`: get your own free key at <https://www.alphavantage.co/support/#api-key>. Don't share keys. The free tier allows 25 calls a day per key, and every `make db-reset` empties your local earnings cache, so a shared key runs out fast. The production Supabase values are only needed for `make use-prod`; ask the tech lead if you need them.
- `make db-env` writes `.env.local` files that point both apps at your local database instead. Never commit env files, and never paste their contents into an AI chat.

### 5. Run it

```bash
make dev
```

Open <http://localhost:3000> and log in as `analyst@kancil.test` or `admin@kancil.test`. The password is in `backend/supabase/seed.sql`.

| URL | What's there |
| --- | --- |
| <http://localhost:3000> | The app |
| <http://localhost:8000/docs> | Every API endpoint, live |
| <http://localhost:54323> | Your local database (Supabase Studio) |

### Optional: link to production

Day-to-day work never needs this: the local database, `make db-reset` and `make db-diff` all run without it, and migrations reach production through CI. Linking only lets you compare your migrations with production's history (`make db-status`). It needs a Supabase account with access to the project.

```bash
cd backend
supabase login
supabase link --project-ref sepdqxndqkimiprsfipb
cd ..
```

## Everyday commands

`make help` lists them all:

| Command | What it does |
| --- | --- |
| `make dev` | Run both apps (starts local Supabase too, if the app is using it) |
| `make install` | Update dependencies after pulling |
| `make generate` | Regenerate frontend API types after backend changes |
| `make lint` / `make check` | Lint / lint + type-check + build before pushing |
| `make db-reset` | Rebuild the local database (after switching branches) |
| `make db-diff name=…` | Turn local schema changes into a migration |
| `make db-env` / `make use-prod` | Use the local / production database |

## Docs

- [`docs/database_workflow.md`](docs/database_workflow.md): how to change the database schema
- [`CLAUDE.md`](CLAUDE.md): conventions and gotchas (also read by AI coding tools)
- [`docs/`](docs/): original design spec, roadmap and UI design language
