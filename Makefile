BACKEND_DIR = backend
FRONTEND_DIR = frontend

.PHONY: install install-backend install-frontend dev dev-backend dev-frontend

install: install-backend install-frontend

install-backend:
	cd $(BACKEND_DIR) && uv sync --group dev

install-frontend:
	cd $(FRONTEND_DIR) && bun install

dev:
	@echo "Starting backend and frontend…"
	@$(MAKE) dev-backend & $(MAKE) dev-frontend

dev-backend:
	cd $(BACKEND_DIR) && uv run fastapi dev main.py

dev-frontend:
	cd $(FRONTEND_DIR) && bun run dev
