# Database workflow

How to change the database schema (tables, columns, indexes, policies, functions) safely.

**The short version:** make the change in your *local* Supabase Studio, let `make db-diff name=…` write the migration, test it with `make db-reset`, and open a PR. CI checks it; merging applies it to production.

Every schema change is a migration file in `backend/supabase/migrations/`. Production only ever changes by applying those files, in order, from CI. Never change the production schema by hand in the Supabase dashboard.

All commands below are `make` targets run from the repo root (`make help` lists them). The database ones need Docker running.

## One-time setup

1. Install the Supabase CLI (`brew install supabase/tap/supabase`) and Docker Desktop.
2. `make setup` installs dependencies, starts a local Supabase on your laptop, and points the app at it. The first run downloads Docker images and takes a few minutes.
3. Add `ALPHA_VANTAGE_API_KEY` to `backend/.env`, then `make dev`.
4. Log in at <http://localhost:3000/login> as `admin@kancil.test` or `analyst@kancil.test` (password in `backend/supabase/seed.sql`). Both are created by the seed, so they come back after every `make db-reset`.

`make use-prod` points the app at production data instead, and `make db-env` points it back at local. `make db-status` shows which one is active.

## Making a schema change

### 1. Branch

```bash
git switch main && git pull
git switch -c <short-description>
make db-reset
```

Always `make db-reset` after switching or pulling branches. Your local database keeps whatever the *last* branch's migrations did, while `supabase/migrations/` now holds this branch's files. If they disagree, step 3's diff "undoes" the other branch's changes — for example, after testing a branch that drops a table, a diff on `main` would generate a migration dropping it again.

### 2. Make the change in local Studio

Open <http://localhost:54323> and use the Table Editor (add a table, a column, an index) or the SQL Editor. You are changing your laptop's database only, so experiment freely.

### 3. Generate the migration

```bash
make db-diff name=<what_changed>
```

This runs `supabase db diff --schema public`, which compares your local database with what the existing migrations produce and writes the difference to `supabase/migrations/<timestamp>_<what_changed>.sql`. If the file contains changes you didn't make, your local database is out of sync with this branch: delete the file, `make db-reset`, redo your change, and diff again.

`make db-diff` always passes `--schema public`. Without it, the diff also picks up harmless differences in Supabase's own setup (for example a `drop extension "pg_net"` line) that do not belong in a migration.

### 4. Read the generated SQL

The diff only knows *before* and *after*, not *how* you got there. Check for:

- **Renames.** Renaming a column or table in Studio comes out as **drop + add**, which **deletes the data** in production. Replace those lines with `ALTER TABLE … RENAME COLUMN old TO new;` by hand.
- **Any `drop`.** Make sure every drop is intended. Drops are permanent in production.
- **Data changes.** The diff covers schema only. Backfills (`UPDATE …`) and data fixes are not captured; add them to the migration by hand. Fake data for local development goes in `supabase/seed.sql`, not in a migration.

Writing the SQL directly with `make db-new name=<name>` is also fine, and is the better choice for renames, backfills, and anything the diff gets wrong.

### 5. Test it from scratch

```bash
make db-reset
```

Rebuilds the local database from every migration plus `seed.sql`. If it fails, the migration would fail in CI too. It also wipes local data, including any users you made by hand; the seeded test users come back automatically.

Then run the app (`make dev`) against the local database and click through whatever the change affects.

### 6. Update the code, then commit

Change the backend (`db/models.py`, `db/supabase.py`, services) and, if the API changed, regenerate the frontend client (`make generate`). Run `make check` (lint, type-check, build), then commit the migration and the code together.

### 7. Open a PR

The **Database migrations — check** workflow runs automatically. It:

- builds a fresh database from all migrations + seed, proving they apply cleanly;
- dry-runs against production and lists exactly which migrations merging would apply.

### 8. Merge

Merging is the moment production changes. The **Database migrations — deploy** workflow runs `supabase db push`, which applies only the migrations production has not recorded yet.

## Rules

- **Reset after switching branches.** `make db-reset` whenever you switch or pull, so your local database matches the branch's migrations.
- **Never edit a migration that has been merged.** Production has already run it; write a new migration instead.
- **Never change the production schema in the dashboard.** It creates drift the migrations don't know about.
- **Code before drops.** Once the backend is deployed, code that stops reading a column or table must be live before the migration that drops it. Ship them as two PRs: first the code change, then the drop.
- **Renames are two-step in production.** Add the new column → switch the code over → drop the old one in a later migration. Never rename something running code still reads.
- **One logical change per migration**, named for what it does (`add_coverage_table`, not `update`).

## Useful commands

| Command | What it does |
| --- | --- |
| `make setup` | First-time setup: install, start local Supabase, point the app at it |
| `make dev` | Run both apps; starts local Supabase too if the app uses it |
| `make db-start` / `make db-stop` | Start / stop the local stack (Studio at <http://localhost:54323>) |
| `make db-diff name=<name>` | Write a migration from your local changes |
| `make db-new name=<name>` | Create an empty migration to write by hand |
| `make db-reset` | Rebuild the local DB from migrations + seed |
| `make db-env` / `make use-prod` | Point the app at local / production Supabase |
| `make db-status` | Which database the app uses, and local vs production migration history |
| `make generate` / `make check` | Regenerate API types; lint + type-check + build |

Under the hood these are Supabase CLI commands run from `backend/`; `supabase db push --linked --dry-run` there shows what merging would apply to production.
