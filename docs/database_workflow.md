# Database workflow

How to change the database schema (tables, columns, indexes, policies, functions) safely.

**The short version:** make the change in your *local* Supabase Studio, let `supabase db diff` write the migration, test it with `supabase db reset`, and open a PR. CI checks it; merging applies it to production.

Every schema change is a migration file in `backend/supabase/migrations/`. Production only ever changes by applying those files, in order, from CI. Never change the production schema by hand in the Supabase dashboard.

All `supabase` commands run from `backend/` and need Docker running.

## One-time setup

1. Install the Supabase CLI (`brew install supabase/tap/supabase`) and Docker Desktop.
2. `supabase start` — starts a local Supabase on your laptop. First run downloads images and takes a few minutes.
3. Point the app at it: copy `backend/.env.local.example` to `backend/.env.local` and `frontend/.env.local.example` to `frontend/.env.local`, and fill them in from `supabase status -o env`. Delete or rename the `.env.local` files to go back to production.
4. Log in at <http://localhost:3000/login> as `admin@kancil.test` or `analyst@kancil.test` (password in `supabase/seed.sql`). Both are created by the seed, so they come back after every `supabase db reset`.

## Making a schema change

### 1. Branch

```bash
git switch main && git pull
git switch -c <short-description>
supabase db reset
```

Always `supabase db reset` after switching or pulling branches. Your local database keeps whatever the *last* branch's migrations did, while `supabase/migrations/` now holds this branch's files. If they disagree, step 3's diff "undoes" the other branch's changes — for example, after testing a branch that drops a table, a diff on `main` would generate a migration dropping it again.

### 2. Make the change in local Studio

Open <http://localhost:54323> and use the Table Editor (add a table, a column, an index) or the SQL Editor. You are changing your laptop's database only, so experiment freely.

### 3. Generate the migration

```bash
supabase db diff --schema public -f <what_changed>
```

This compares your local database with what the existing migrations produce and writes the difference to `supabase/migrations/<timestamp>_<what_changed>.sql`. If the file contains changes you didn't make, your local database is out of sync with this branch: delete the file, `supabase db reset`, redo your change, and diff again.

Always pass `--schema public`. Without it, the diff also picks up harmless differences in Supabase's own setup (for example a `drop extension "pg_net"` line) that do not belong in a migration.

### 4. Read the generated SQL

The diff only knows *before* and *after*, not *how* you got there. Check for:

- **Renames.** Renaming a column or table in Studio comes out as **drop + add**, which **deletes the data** in production. Replace those lines with `ALTER TABLE … RENAME COLUMN old TO new;` by hand.
- **Any `drop`.** Make sure every drop is intended. Drops are permanent in production.
- **Data changes.** The diff covers schema only. Backfills (`UPDATE …`) and data fixes are not captured; add them to the migration by hand. Fake data for local development goes in `supabase/seed.sql`, not in a migration.

Writing the SQL directly with `supabase migration new <name>` is also fine, and is the better choice for renames, backfills, and anything the diff gets wrong.

### 5. Test it from scratch

```bash
supabase db reset
```

Rebuilds the local database from every migration plus `seed.sql`. If it fails, the migration would fail in CI too. It also wipes local data, including any users you made by hand; the seeded test users come back automatically.

Then run the app (`make dev`) against the local database and click through whatever the change affects.

### 6. Update the code, then commit

Change the backend (`db/models.py`, `db/supabase.py`, services) and, if the API changed, regenerate the frontend client (`bun run generate` in `frontend/`). Commit the migration and the code together.

### 7. Open a PR

The **Database migrations — check** workflow runs automatically. It:

- builds a fresh database from all migrations + seed, proving they apply cleanly;
- dry-runs against production and lists exactly which migrations merging would apply.

### 8. Merge

Merging is the moment production changes. The **Database migrations — deploy** workflow runs `supabase db push`, which applies only the migrations production has not recorded yet.

## Rules

- **Reset after switching branches.** `supabase db reset` whenever you switch or pull, so your local database matches the branch's migrations.
- **Never edit a migration that has been merged.** Production has already run it; write a new migration instead.
- **Never change the production schema in the dashboard.** It creates drift the migrations don't know about.
- **Code before drops.** Once the backend is deployed, code that stops reading a column or table must be live before the migration that drops it. Ship them as two PRs: first the code change, then the drop.
- **Renames are two-step in production.** Add the new column → switch the code over → drop the old one in a later migration. Never rename something running code still reads.
- **One logical change per migration**, named for what it does (`add_coverage_table`, not `update`).

## Useful commands

| Command | What it does |
| --- | --- |
| `supabase start` / `supabase stop` | Start / stop the local stack |
| `supabase status -o env` | Local URLs and keys |
| `supabase db diff --schema public -f <name>` | Write a migration from your local changes |
| `supabase migration new <name>` | Create an empty migration to write by hand |
| `supabase db reset` | Rebuild the local DB from migrations + seed |
| `supabase migration list` | Compare local migrations with production's history |
| `supabase db push --linked --dry-run` | Show what would be applied to production (needs `supabase link`) |
