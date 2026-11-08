# 💸 SplitSync AI

**Talk. Split. Settle.** Conversational group expenses powered by **Google Gemini**, with one-tap settlement through **PayPal**.

> *"I paid $60 for dinner, split between me, Alex, and Sarah"*: logged, split to the cent, and settled with PayPal. Every friend's screen updates live.

## ✨ Features

| | |
|---|---|
| 🗣️ **Conversational logging** | Type an expense in plain English. Gemini returns schema-validated JSON |
| 🎙️ **Voice** | Tap the mic and say it |
| 📷 **Receipt scanning** | Gemini Vision reads the line items. Add a note like *"Alex had the steak"* to assign items. Tax and tip are spread proportionally |
| ⚡ **Smart settlement** | Debts reduced to the fewest payments, e.g. "3 payments instead of 6" |
| 💳 **PayPal settle-up** | Orders v2 create, approve, capture. Idempotent, with overpayment protection |
| 🔴 **Live sync** | Server-Sent Events: changes show up on every device instantly |
| ✨ **Ask your ledger** | "How much did we spend on food?" "Who owes me?" |
| 🔔 **AI nudges** | Friendly, funny or formal reminders. Copy or share to WhatsApp |
| 📊 **Insights** | Category breakdown, paid vs. fair share, daily spend, AI highlights |
| 🌴 **Demo trip** | A realistic 4-person trip loaded in one click |
| 🛡️ **Works without keys** | Offline parser and simulated checkout until you add keys |

## 🚀 Quick start

### Windows (easiest)
1. Install **Python 3.12 or 3.13** (python.org, tick *Add python.exe to PATH*) and **Node.js LTS** (nodejs.org).
2. Double-click **`setup.bat`** (one time).
3. Double-click **`start.bat`**. Two windows open, then your browser opens at http://localhost:5173.

### macOS / Linux
```bash
make setup
```
```bash
make dev
```

### Docker
```bash
docker compose up --build
```
Then open http://localhost:8080.

### Manual (any OS)
```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt && cp .env.example .env
```
```bash
.venv/bin/python -m uvicorn main:app --reload --port 8000
```
```bash
cd frontend && npm install && npm run dev
```
On Windows, use `.venv\Scripts\python` in place of `.venv/bin/python`.

## 🔑 Keys (optional; the app runs without them)

Edit `backend/.env`:

| Variable | Get it from | Without it |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey | Offline regex parser. Receipt scanning disabled |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | developer.paypal.com → Apps & Credentials → **Sandbox** → Create App | Simulated checkout (labelled DEMO) |

Restart the backend after editing. The sidebar shows which modes are active. For the sandbox buyer login, see developer.paypal.com → Testing Tools → Sandbox Accounts (*Personal* account).

## 🧪 Quality
```bash
cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check .
```
- 15 backend tests: cent-exact splits, balance invariants, demo settlement, insights, copilot, nudges, CSV, receipt validation.
- CI (GitHub Actions) runs lint, tests and the frontend build on every push.

## 📚 Docs

| Doc | What's inside |
|---|---|
| [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) | Problem, personas, features, metrics, roadmap |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagram, modules, flows, decisions, scaling, security |
| [SCHEMA.md](SCHEMA.md) | ERD, tables, invariants, AI schemas, full REST API |
| [DESIGN.md](DESIGN.md) | Design system, layout, components, accessibility, **3-minute demo script** |
| [CLAUDE.md](CLAUDE.md) | House rules for AI agents and contributors |
| [TASK.md](TASK.md) | Done / to do, and the **pre-demo key checklist** |

## 🗂️ Structure
```
split-sync-ai/
├── backend/            FastAPI · SQLAlchemy · Gemini · PayPal
│   ├── main.py         routes        ├── ledger.py     money math
│   ├── ai_parser.py    all AI        ├── insights.py   analytics
│   ├── events.py       live sync     ├── paypal_client.py
│   ├── models.py · schemas.py · config.py · database.py · demo_data.py
│   └── tests/
├── frontend/           React 19 · Vite · Tailwind v4
│   └── src/  App.jsx · components/ · hooks/ · services/
├── scripts/            Windows setup/start (PowerShell)
├── setup.bat · start.bat · Makefile · docker-compose.yml
└── *.md                docs
```
