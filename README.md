# 💸 SplitSync AI

Conversational group expense tracking with autonomous settlement.
Type *"I paid $60 for dinner, split between me, Alex, and Sarah"*. **Google Gemini** turns it into a structured expense, SplitSync works out who owes whom, and **PayPal Sandbox** settles each debt in one click.

```
split-sync-ai/
├── backend/                FastAPI + SQLAlchemy (SQLite)
│   ├── main.py             API routes, split math, debt simplification
│   ├── database.py         engine / session / get_db dependency
│   ├── models.py           User, Group, GroupMember, Expense, ExpenseSplit, Settlement
│   ├── schemas.py          Pydantic API + ParsedExpense (Gemini structured output)
│   ├── ai_parser.py        Gemini parsing (+ offline regex fallback)
│   ├── paypal_client.py    OAuth2 token + Orders v2 create/capture
│   ├── config.py           pydantic-settings (.env)
│   └── requirements.txt
└── frontend/               React 19 + Vite + Tailwind CSS v4
    └── src/
        ├── App.jsx
        ├── components/     Sidebar, ChatPanel, Ledger, BalancesPanel, CreateGroupModal, ui
        └── services/       api.js, format.js
```

## 1. Get your keys

| Key | Where |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | https://developer.paypal.com → **Apps & Credentials** → toggle **Sandbox** → *Create App* |
| Sandbox buyer login | developer.paypal.com → **Testing Tools → Sandbox Accounts** (use the *Personal* account's email and password at checkout) |

## 2. Backend (Python 3.10+)

```bash
cd split-sync-ai/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in your keys
uvicorn main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

> **No Gemini key yet?** Set `AI_OFFLINE_MODE=true`, or leave the key empty. A built-in regex parser handles simple sentences so you can still demo the app.

## 3. Frontend (Node 18+)

```bash
cd split-sync-ai/frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `localhost:8000`, so you don't need to set anything for CORS in development.

## 4. Demo script

1. **Create a group** with the members You, Alex and Sarah.
2. In the chat, type:
   - `I paid $60 for dinner, split between me, Alex, and Sarah`
   - `Alex covered the $30 Uber, split with me`
   - `Sarah paid 45 for groceries for everyone`
   - `I paid $100 for concert tickets: Alex owes 60, I owe 40` (custom split)
3. **Balances** reduces the debts to the fewest payments. Switch **Acting as** to *Alex* and click **Settle via PayPal**.
4. Log in with the sandbox *Personal* account and approve. PayPal redirects back, and the app **captures** the order. The debt disappears, the related splits are marked `paid`, and a settlement entry appears in the ledger.

## API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/groups` | Create a group `{name, members:[{name,email?}]}` |
| `GET` | `/api/groups` · `/api/groups/{id}` | List groups / get one group |
| `POST` | `/api/groups/{id}/members` | Add a member |
| `POST` | `/api/groups/{id}/expenses/parse` | `{text, sender_id?}` → Gemini → saves the expense and its splits |
| `GET` | `/api/groups/{id}/expenses` | Ledger |
| `DELETE` | `/api/expenses/{id}` | Delete an expense |
| `GET` | `/api/groups/{id}/balances` | Net balances and simplified debts |
| `POST` | `/api/settlements/pay` | `{group_id, from_user_id, to_user_id, amount}` → PayPal order → `approval_url` |
| `POST` | `/api/settlements/{id}/capture` | Captures the approved order and marks the debt settled |
| `POST` | `/api/settlements/{id}/cancel` | Buyer cancelled at PayPal |
| `GET` | `/api/health` | AI mode and PayPal configuration status |

## How it works

- **AI parsing.** `ai_parser.py` calls `client.models.generate_content` with `response_schema=ParsedExpense` and `response_mime_type="application/json"`, so Gemini must return schema-valid JSON. The prompt includes the group's member names and the sender's name, which resolves "I" and "me".
- **Splits.** An equal split is calculated in whole cents, so the shares always add up to the total. A custom split checks that the shares add up to the total. Names the AI returns are matched to existing members (case-insensitive, first name). Anyone not in the group is added automatically.
- **Balances.** Each member's net balance = what others owe them − what they owe + settlements they paid. A greedy algorithm pairs the largest debtor with the largest creditor, which keeps the number of payments low.
- **Settlement.** The app creates a PayPal Orders v2 order (`intent: CAPTURE`) with `return_url` and `cancel_url` that point back to the frontend. On return, the app captures the order. The capture is idempotent, so refreshing the page is safe.
- **Payee.** By default, sandbox payments go to the merchant account of your sandbox app. Set `PAYPAL_USE_PAYEE_EMAIL=true` to route each payment to the creditor's email instead. Those emails must be PayPal sandbox accounts.
