# SplitSync AI — developer commands (macOS / Linux / WSL). Windows: use setup.bat / start.bat
PY ?= python3
VENV = backend/.venv
BIN = $(VENV)/bin

.PHONY: help setup backend frontend dev test lint build docker clean

help:            ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:           ## Install backend + frontend dependencies, create .env
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q -r backend/requirements-dev.txt
	test -f backend/.env || cp backend/.env.example backend/.env
	cd frontend && npm install

backend:         ## Run the API on :8000 (auto-reload)
	cd backend && .venv/bin/uvicorn main:app --reload --port 8000

frontend:        ## Run the web app on :5173
	cd frontend && npm run dev

dev:             ## Run backend and frontend together
	$(MAKE) -j2 backend frontend

test:            ## Backend tests
	cd backend && .venv/bin/python -m pytest -q

lint:            ## Lint backend
	cd backend && .venv/bin/ruff check .

build:           ## Production frontend build
	cd frontend && npm run build

docker:          ## Build and run everything with Docker (http://localhost:8080)
	docker compose up --build

clean:           ## Remove build artifacts and local DB
	rm -rf frontend/dist backend/__pycache__ backend/.pytest_cache backend/splitsync.db*
