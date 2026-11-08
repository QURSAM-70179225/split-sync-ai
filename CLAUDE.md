# CLAUDE.md: Agent House Rules

This file is for AI coding agents (Claude Code and others) and human contributors. Read it before changing anything.

## Project in one line
SplitSync AI: conversational group expenses (FastAPI + Gemini) with PayPal settlement and live sync (React 19 + Vite + Tailwind v4).

## Map
```
backend/   main.py (routes only) · ledger.py (money math) · ai_parser.py (all LLM calls)
           insights.py · events.py (SSE broker) · paypal_client.py · models.py · schemas.py
           config.py · database.py (+ additive migrations) · demo_data.py · tests/
frontend/  src/App.jsx (state + orchestration) · components/ · hooks/ · services/api.js
docs       ARCHITECTURE.md · SCHEMA.md · DESIGN.md · PRODUCT_REQUIREMENTS.md · TASK.md
```

## Commands
| Task | Command |
|---|---|
| Backend dev | `cd backend && .venv/bin/uvicorn main:app --reload --port 8000` (Windows: `.venv\Scripts\python -m uvicorn …`) |
| Frontend dev | `cd frontend && npm run dev` (proxies `/api` to :8000) |
| Tests | `cd backend && .venv/bin/python -m pytest -q` |
| Lint | `cd backend && .venv/bin/ruff check .` |
| Build | `cd frontend && npm run build` |
| Everything | `make setup && make dev` · `docker compose up --build` |

**Before saying a change is done:** `pytest` passes, `ruff check` is clean, and `npm run build` succeeds. For UI changes, run the app and look at the result.

## Golden rules
1. **Money is exact.** Every split for an expense must add up to the total, to the cent. Use `ledger.split_equal` / `scale_to_total`. Never hand-roll float division. Add a test for any new split path.
2. **Routes stay thin.** Business logic goes in `ledger.py`, `insights.py` or `ai_parser.py`. `main.py` only validates, calls those, commits and publishes events.
3. **Every AI feature needs a fallback.** New Gemini features must degrade to a deterministic offline path, or fail with a clear 422 that says which key is missing. The app must demo with **no keys at all**.
4. **The schema is the contract.** LLM output goes through a Pydantic `response_schema`, then server-side validation (`_finalize`, sum checks). Never trust raw model text for money.
5. **Publish after commit.** Any write that changes what a group sees calls `broker.publish(group_id, "<noun>.<verb>", {...})` after `db.commit()`.
6. **Keep secrets server-side.** Keys live only in `backend/.env`. Never log them, return them, or add them to the frontend bundle. `.env` is git-ignored.
7. **Schema changes are additive.** A new column means: the model, `database._ADDED_COLUMNS` (for existing DBs), `SCHEMA.md` and the Pydantic schema.
8. **Demo mode must stay honest.** Simulated payments are labelled DEMO, use `DEMO-` order IDs, and are refused when real PayPal is configured. Don't imitate PayPal's own branding in simulated UI.
9. **API changes go everywhere.** Update `services/api.js`, `SCHEMA.md` §4 and the tests together.
10. **Keep the tour in sync.** When you move or rename a UI area, keep its `data-tour="…"` attribute and update `services/tourSteps.jsx`. New headline features get a tour step.
11. **UI uses the primitives.** `Card`, `Badge`, `Avatar`, `Modal`, `btnPrimary`, `inputCls` from `components/ui.jsx`. Money is always shown with `money()` in `font-mono`. Category metadata only comes from `services/categories.js`.

## Conventions
- Python 3.10+, type hints, `from __future__ import annotations` in new modules, ruff (line length 120).
- Errors: raise `HTTPException(status, "Human sentence telling the user what to do")`.
- React: function components and hooks, no class components, no new state libraries. Keep fetching in `App.jsx` or self-contained panels.
- Tailwind v4 utilities only, no inline style except for data-driven widths and heights.
- Commits: imperative mood ("Add receipt scanning"), one logical change per commit.

## Don'ts
- Don't add an endpoint that changes money without a test.
- Don't call Gemini or PayPal in tests. Tests run with `AI_OFFLINE_MODE=true` and `PAYPAL_MODE=demo` (see `tests/conftest.py`).
- Don't commit `*.db`, `.env`, `node_modules`, `.venv` or `dist`.
- Don't make a feature depend on network access to run the demo.
