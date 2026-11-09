# Architecture

## 1. System overview

```
                         ┌──────────────────────────── Browser (React 19 + Vite + Tailwind) ───────────────────────────┐
                         │  ChatPanel (text · 🎙️ voice · 📷 receipt)   BalancesPanel   Ledger   InsightsPanel + Copilot      │
                         │        │                         │               │             │                              │
                         │        └──────── services/api.js (fetch) ────────┴─────────────┘   hooks/useGroupEvents (SSE) │
                         └────────────────────────────────────┬──────────────────────────────────────▲──────────────────────┘
                                            REST /api/*       │                                      │ text/event-stream
                         ┌────────────────────────────────────▼──────────────────────────────────────┴──────────────────────┐
                         │ FastAPI (main.py) ─ request-id/timing middleware ─ CORS ─ error handlers                       │
                         │   ├─ ai_parser.py ── Gemini (structured JSON / vision) ── offline fallbacks                     │
                         │   ├─ ledger.py ───── splits · balances · debt simplification                                   │
                         │   ├─ insights.py ─── analytics · copilot context                                               │
                         │   ├─ events.py ───── in-process pub/sub broker → SSE                                           │
                         │   ├─ paypal_client ─ OAuth2 + Orders v2 (create / capture)  │  demo checkout                    │
                         │   └─ SQLAlchemy ──── SQLite (WAL)                                                               │
                         └──────────────┬──────────────────────────────┬──────────────────────────────┬──────────────────┘
                                        ▼                              ▼                              ▼
                              Google Gemini API            PayPal REST (sandbox)              splitsync.db
```

## 2. Backend modules

| Module | Responsibility | Depends on |
|---|---|---|
| `main.py` | HTTP layer only: routing, validation, status codes, publishing events | everything below |
| `config.py` | Typed settings from `.env` (pydantic-settings). Treats placeholder keys as unset. Resolves `effective_paypal_mode` | — |
| `database.py` | Engine, session, SQLite pragmas (FKs, WAL), additive migrations on startup | config |
| `models.py` | ORM: User, Group, GroupMember, Expense, ExpenseSplit, Settlement | database |
| `schemas.py` | The API contract plus the **AI output schemas** (`ParsedExpense`, `ParsedReceipt`) | — |
| `ai_parser.py` | All prompts, provider switch (Groq or Gemini), schema validation. Every feature except receipts has a deterministic fallback | config, schemas, groq_client |
| `groq_client.py` | Groq chat completions over HTTPS: model discovery, retired-model rollover, JSON mode, timeouts | config |
| `ledger.py` | Pure money logic: name resolution, cent-exact splits, balances, simplification, marking splits paid | models |
| `insights.py` | Aggregations, highlights, compact JSON context for the copilot | ledger |
| `events.py` | Thread-safe pub/sub broker feeding SSE streams | — |
| `paypal_client.py` | Token cache, create order, capture order (handles "already captured") | config |
| `demo_data.py` | Seeds the "Bali Trip" demo | ledger |

## 3. Key flows

### 3.1 Conversational expense
```
User text ─► POST /api/groups/{id}/expenses/parse {text, sender_id, source}
   ├─ ai_parser.parse_expense_prompt(text, members, sender)
   │     Gemini: response_schema=ParsedExpense, temperature=0
   │     on error ─► _offline_parse (regex)            ── no key ─► _offline_parse
   ├─ _finalize: amount > 0, currency upper-case, category fallback
   ├─ _save_expense: resolve/create members ─► equal (cent-exact) | custom (sum check)
   ├─ commit ─► broker.publish("expense.created")  ─► every open client refetches
   └─ 201 {expense, parsed, new_members, ai_mode, notes}
```

### 3.2 Receipt scan (itemized)
`multipart(file, note, sender_id)` → type and size check → `asyncio.to_thread(parse_receipt)`. Gemini Vision returns `ParsedReceipt` (items, `assigned_to`, `tax_and_tip`, `custom_shares`). `_save_expense(scale_custom=True)` scales the shares proportionally to the printed total, which spreads tax and tip by subtotal. Line items are stored in `items_json`.

### 3.3 Balances and smart settlement
1. `net[currency][user]`: the payer is credited with every other person's split. Completed settlements are added back.
2. Pairwise count ("naive"): the number of distinct debtor→creditor pairs after netting each pair.
3. Greedy: sort debtors and creditors by size and repeatedly match the largest with the largest. This guarantees **≤ N−1 transfers** per currency.
4. The UI shows `naive − simplified` as "payments saved".

### 3.4 Settlement (PayPal Orders v2)
```
[Settle] ─► POST /api/settlements/pay ─► check amount ≤ outstanding debt
            ├─ mode=sandbox: OAuth2 token (cached) ─► POST /v2/checkout/orders (intent CAPTURE,
            │                 experience_context.return_url=/?paypal=success&settlement_id=N)
            │                 ─► approval_url (rel=payer-action) ─► browser redirect to PayPal
            │                 ◄─ PayPal returns ?token=ORDER_ID&PayerID=…
            └─ mode=demo:    DEMO-xxxx order id ─► in-app simulated approval modal
   POST /api/settlements/{id}/capture {order_id}
            ├─ order id must match the settlement
            ├─ sandbox: POST /v2/checkout/orders/{id}/capture (ORDER_ALREADY_CAPTURED counts as success)
            ├─ status=completed, mark_splits_paid (oldest first)
            └─ broker.publish("settlement.completed")
```

### 3.5 Live sync
`GET /api/groups/{id}/events` is an SSE stream. It sends a `connected` event (with the listener count), then domain events, with `: keep-alive` every 15 s. Route handlers run in a threadpool, so `Broker.publish` uses `loop.call_soon_threadsafe`. Each subscriber queue is bounded at 100 and drops the oldest event if full. The client uses `EventSource`, which reconnects automatically, and refetches when an event arrives. Events triggered by your own actions don't show a toast.

## 4. Design decisions

| Decision | Why | Trade-off |
|---|---|---|
| **Structured output via a Pydantic schema** | The LLM can't return invalid shapes. One schema serves both the prompt contract and validation | Ties us to providers that support schemas |
| **Offline fallbacks** | The demo never breaks. Works without keys | The regex parser handles fewer phrasings |
| **Floats rounded to cents, with cent-integer split math** | Simple SQLite storage. Split logic works in integer cents | Postgres `NUMERIC` is better at scale (roadmap) |
| **Balances computed on read** | Always consistent, no stored balances to drift | O(splits) per request, fine below ~10⁵ splits per group |
| **SSE rather than WebSockets** | One-way updates are enough. Works through proxies. Built-in reconnect | One process only (see scaling) |
| **SQLite with WAL** | Zero setup for judges and local dev | Swap `DATABASE_URL` for Postgres |
| **Simulated checkout when PayPal isn't configured** | Shows the full flow with no keys, clearly labelled DEMO | Must never run when real keys exist (guarded in capture) |

## 5. Scaling path
1. `DATABASE_URL=postgresql+psycopg://…`. The models are database-agnostic. Add Alembic for migrations.
2. Several workers or replicas: replace `events.Broker` with Redis pub/sub (same `publish` and `subscribe` interface).
3. Move AI calls to a task queue if latency matters. Cache copilot context per ledger version.
4. Use PayPal webhooks as the source of truth for capture. Keep the return-URL capture as the fast path.

## 6. Security
- Secrets stay server-side (`.env`, git-ignored). The browser never sees API keys.
- CORS is limited to `CORS_ORIGINS`. Uploads are limited to image types and ≤ `MAX_RECEIPT_MB`.
- Settlement integrity: the amount must be ≤ the outstanding debt, the order ID must match, capture is idempotent, and demo capture is refused when real PayPal is configured.
- Unhandled exceptions return a generic 500 and full details are logged with a request ID.
- **Known gap:** there is no authentication. Anyone who can reach the API can act as any member. Auth is the top roadmap item before any public deployment.

## 7. Deployment
- **Hosted (recommended):** the root `Dockerfile` builds the React app and copies it into the Python image. FastAPI serves it from `STATIC_DIR` with an SPA fallback, so there's **one service on one URL** with no CORS. `render.yaml` gives one-click Render deploys. The PayPal return URL comes from `RENDER_EXTERNAL_URL`. `SEED_DEMO_ON_START` seeds the demo trip for judges. See [DEPLOY.md](DEPLOY.md).
- **Local:** `setup.bat` / `start.bat` (Windows) or `make setup && make dev`.
- **Docker (two containers):** `docker compose up --build`. nginx serves the SPA and proxies `/api` (SSE unbuffered). The backend runs as a non-root user with a healthcheck, and SQLite is on a named volume.
- **CI:** GitHub Actions runs ruff and pytest (backend) and `npm ci && npm run build` (frontend).
