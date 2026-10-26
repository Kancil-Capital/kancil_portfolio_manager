BACKEND_DIR = backend
FRONTEND_DIR = frontend
SUPABASE = cd $(BACKEND_DIR) && supabase

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
	generate lint check db-start db-stop db-reset db-diff db-new db-status db-env use-prod

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-13s %s\n", $$1, $$2}'

# First-time setup lives in README.md; these targets are for everyday work.

install: install-backend install-frontend ## Install/update backend and frontend dependencies (after pulling)

install-backend:
	cd $(BACKEND_DIR) && uv sync --group dev

install-frontend:
	cd $(FRONTEND_DIR) && bun install

# ── Run ────────────────────────────────────────────────────────────────────────

dev: ## Run backend (:8000) and frontend (:3000); starts local Supabase if the app uses it
	@if [ -f $(BACKEND_DIR)/.env.local ] && grep -q '^SUPABASE_URL=http://127.0.0.1' $(BACKEND_DIR)/.env.local; then \
		echo "Using local Supabase…"; $(SUPABASE) start >/dev/null || exit 1; \
	else echo "Using production Supabase (.env)"; fi
	@$(MAKE) dev-backend & $(MAKE) dev-frontend

dev-backend:
	cd $(BACKEND_DIR) && uv run fastapi dev main.py

dev-frontend:
	cd $(FRONTEND_DIR) && bun run dev

# ── Code ───────────────────────────────────────────────────────────────────────

generate: ## Regenerate frontend API types/hooks from the backend (no server needed)
	cd $(FRONTEND_DIR) && bun run generate

lint: ## Lint backend (ruff) and frontend (eslint)
	cd $(BACKEND_DIR) && uv run ruff check .
	cd $(FRONTEND_DIR) && bun run lint

check: lint ## Lint + type-check + production build, before pushing
	cd $(FRONTEND_DIR) && bunx tsc --noEmit && bun run build

# ── Database (local Supabase; needs Docker) ───────────────────────────────────

db-start: ## Start local Supabase (Studio at http://localhost:54323)
	$(SUPABASE) start >/dev/null
	@echo "Local Supabase running. Studio: http://localhost:54323"

db-stop: ## Stop local Supabase
	$(SUPABASE) stop

db-reset: ## Rebuild local DB from migrations + seed (run after switching branches)
	$(SUPABASE) db reset

db-diff: ## Write a migration from your local Studio changes: make db-diff name=add_x
	@test -n "$(name)" || { echo "usage: make db-diff name=what_changed"; exit 1; }
	@before=$$(ls $(BACKEND_DIR)/supabase/migrations | wc -l); \
	(cd $(BACKEND_DIR) && supabase db diff --schema public -f $(name)) || exit 1; \
	if [ $$(ls $(BACKEND_DIR)/supabase/migrations | wc -l) -gt $$before ]; then \
		echo "Created $$(ls -t $(BACKEND_DIR)/supabase/migrations/*.sql | head -1)"; \
		echo "Read it (renames show up as drop + add, rewrite them as RENAME), then: make db-reset"; \
	else echo "No changes found: nothing was created."; fi

db-new: ## Create an empty migration to write by hand: make db-new name=add_x
	@test -n "$(name)" || { echo "usage: make db-new name=what_changed"; exit 1; }
	$(SUPABASE) migration new $(name)

db-status: ## Show whether the app points at local or production, and pending migrations
	@if [ -f $(BACKEND_DIR)/.env.local ] && grep -q '^SUPABASE_URL=http://127.0.0.1' $(BACKEND_DIR)/.env.local; \
		then echo "App uses: local Supabase"; else echo "App uses: production Supabase"; fi
	$(SUPABASE) migration list --linked

db-env: ## Point the app at local Supabase (writes the .env.local files)
	cd $(BACKEND_DIR) && uv run python scripts/local_env.py on

use-prod: ## Point the app back at production Supabase
	cd $(BACKEND_DIR) && uv run python scripts/local_env.py off
