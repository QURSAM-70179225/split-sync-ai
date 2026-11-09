# TASK.md: Work Tracker

Legend: ✅ done · 🟡 in progress · ⬜ to do · 🔑 needs your keys

## 🚀 Submission (see SUBMISSION.md)
- [x] Create the public GitHub repo and push
- [x] Deploy to Render: https://split-sync-ai.onrender.com
- [x] Demo video: https://youtu.be/J7Zn1pr2FkE
- [ ] Tick sponsor tools: **PayPal**, **Render**
- [ ] Invite teammates and confirm they accepted

## 🔑 Before the demo (you, at the end)
- [ ] Get a **Gemini API key**: https://aistudio.google.com/app/apikey
- [ ] Get **PayPal Sandbox** keys: developer.paypal.com → Apps & Credentials → **Sandbox** → Create App → copy the Client ID and Secret
- [ ] Open `backend/.env` (`notepad .env`) and fill in:
  ```
  GEMINI_API_KEY=AIza...your-key
  PAYPAL_CLIENT_ID=...your-client-id
  PAYPAL_CLIENT_SECRET=...your-secret
  AI_OFFLINE_MODE=false
  ```
  (No spaces around `=`, no quotes. Save, then restart the backend.)
- [ ] Check the sidebar: **AI parser → Gemini**, **PayPal → Sandbox**
- [ ] Note the sandbox *Personal* buyer login: Testing Tools → Sandbox Accounts
- [ ] Rehearse `DESIGN.md` §8 (3-minute demo script) twice
- [ ] Have a real paper receipt ready for the 📷 scan

## v1: MVP ✅
- ✅ FastAPI + SQLite models (User, Group, GroupMember, Expense, ExpenseSplit)
- ✅ Gemini structured-output parsing (`ParsedExpense`)
- ✅ PayPal OAuth2 + Orders v2 create
- ✅ Balances with greedy debt simplification
- ✅ React dashboard: chat, ledger, balances, Settle via PayPal

## v2: Hackathon edition ✅
- ✅ Settlement capture flow + `Settlement` table + idempotent capture
- ✅ Simulated checkout when PayPal isn't configured (`PAYPAL_MODE=auto|sandbox|demo`)
- ✅ 🎙️ Voice logging (Web Speech API)
- ✅ 📷 Receipt scanning with Gemini Vision + itemized split + proportional tax and tip
- ✅ Auto-categorization (AI + keyword fallback) + category filters
- ✅ 📊 Insights: KPIs, highlights, category bars, paid vs. share, daily spend
- ✅ ✨ Copilot: "Ask your ledger" (Gemini + offline answers)
- ✅ 🔔 AI nudges (3 tones, copy, WhatsApp share)
- ✅ 🔴 Live sync via Server-Sent Events
- ✅ ⚡ Smart-settlement banner ("N payments instead of M")
- ✅ 🌴 One-click demo trip
- ✅ 🧭 Guided tour: spotlight walkthrough, auto-starts on first visit, keyboard nav, phone layout, replay from ❔ Tour
- ✅ CSV export, ledger search
- ✅ Automatic Gemini → offline fallback when the API errors
- ✅ Placeholder keys in `.env` treated as unset (zero-config start)
- ✅ Additive DB migrations for existing `splitsync.db`
- ✅ Request-ID logging middleware + safe 500 handler
- ✅ 16 backend tests (pytest) + ruff
- ✅ Docker (backend + nginx frontend) + docker-compose
- ✅ GitHub Actions CI (lint, test, build)
- ✅ Windows one-click `setup.bat` / `start.bat`, `Makefile` for macOS/Linux
- ✅ Single-image Dockerfile (FastAPI serves the SPA) + `render.yaml` one-click deploy + `DEPLOY.md`
- ✅ MIT LICENSE, interactive README (badges, Deploy button, mermaid diagrams, screenshots), `SUBMISSION.md`
- ✅ Docs: README, ARCHITECTURE, PRODUCT_REQUIREMENTS, DESIGN, SCHEMA, CLAUDE, TASK

## Not yet verified
- ⬜ 🔑 Real Gemini calls (text, receipt vision, copilot, nudge). The code paths exist, but every run so far was offline
- ⬜ 🔑 Real PayPal Sandbox create → approve → capture. Tested only against a mocked client and demo mode
- ⬜ `setup.bat` / `start.bat` on a real Windows machine (written for PowerShell 5.1, not executed yet)
- ✅ Root `Dockerfile` built and run locally (healthy, serves the SPA + API, seeds the demo)
- ⬜ `docker compose up` (two-container variant, not built yet)
- ✅ Deployed to Render: https://split-sync-ai.onrender.com

## v3: Roadmap ⬜
- ⬜ Auth + invite links (magic link). Replace "Acting as" with the real identity
- ⬜ PayPal webhooks (`CHECKOUT.ORDER.APPROVED` / `PAYMENT.CAPTURE.COMPLETED`) as a capture backup
- ⬜ Payouts to the creditor's PayPal account instead of the app merchant account
- ⬜ Multi-currency with live FX and a "settle in my currency" option
- ⬜ Recurring expenses (rent, subscriptions)
- ⬜ Edit expense (re-split) + undo toast
- ⬜ Postgres + Alembic, Redis pub/sub for multi-instance SSE
- ⬜ PWA install + offline queue
- ⬜ Frontend tests (Vitest + Testing Library) and Playwright E2E in CI
