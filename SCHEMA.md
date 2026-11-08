# Data and API Schema

## 1. Entity relationships

```
┌──────────┐       ┌───────────────┐       ┌──────────┐
│  users   │1─────*│ group_members │*─────1│  groups  │
└────┬─────┘       └───────────────┘       └────┬─────┘
     │1                                          │1
     │                                           │*
     │ payer_id                            ┌─────┴──────┐
     ├────────────────────────────────────*│  expenses  │
     │                                     └─────┬──────┘
     │ user_id                                   │1
     ├──────────────────────────────────────────*│ expense_splits
     │                                           
     │ from_user_id / to_user_id           ┌─────────────┐
     └────────────────────────────────────*│ settlements │*───1 groups
                                           └─────────────┘
```

## 2. Tables

### `users`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(100) | Display name. Unique within a group (enforced in the API) |
| email | VARCHAR(255) NULL | Optional. Used as the PayPal payee when `PAYPAL_USE_PAYEE_EMAIL=true` |

### `groups`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(120) | |
| created_at | DATETIME(tz) | UTC |

### `group_members`
| Column | Type | Notes |
|---|---|---|
| group_id | FK → groups.id, PK | `ON DELETE CASCADE` |
| user_id | FK → users.id, PK | `ON DELETE CASCADE` |

### `expenses`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| group_id | FK → groups.id, indexed | cascade |
| payer_id | FK → users.id | |
| amount | FLOAT | Rounded to cents |
| currency | CHAR(3) | ISO 4217 |
| description | VARCHAR(255) | AI-generated, Title Case |
| category | VARCHAR(30) | `food, groceries, transport, lodging, entertainment, shopping, utilities, travel, health, other` *(v2)* |
| source | VARCHAR(10) | `chat, voice, receipt, demo` *(v2)* |
| raw_text | TEXT | The original message, or a receipt summary |
| items_json | TEXT NULL | Receipt line items `[{name, price, assigned_to[]}]` *(v2)* |
| created_at | DATETIME(tz) | |

### `expense_splits`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| expense_id | FK → expenses.id, indexed | cascade |
| user_id | FK → users.id | |
| owed_amount | FLOAT | This person's share. All shares for an expense add up to `amount` exactly |
| status | VARCHAR(10) | `pending` or `paid`. The payer's own share is created as `paid` |

### `settlements`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| group_id | FK → groups.id, indexed | cascade |
| from_user_id / to_user_id | FK → users.id | Debtor → creditor |
| amount, currency | FLOAT, CHAR(3) | |
| status | VARCHAR(12) | `created → completed`, or `cancelled` / `failed` |
| paypal_order_id | VARCHAR(64), indexed | Real PayPal order ID, or `DEMO-…` |
| created_at, completed_at | DATETIME(tz) | |

**Invariants**
1. For every expense, `Σ splits.owed_amount = expenses.amount` (cent-exact).
2. For every group and currency, `Σ net = 0`.
3. A settlement only reaches `completed` through capture, and capture is idempotent.

**Migrations:** `database._migrate()` adds v2 columns to older databases (`ALTER TABLE … ADD COLUMN`). Use Alembic once on Postgres.

## 3. AI output schemas (Gemini `response_schema`)

```python
class ParsedExpense(BaseModel):
    total_amount: float
    currency: str = "USD"
    description: str
    payer_name: str
    split_type: Literal["equal", "custom"]
    participants: list[str]
    custom_shares: list[CustomShare] = []      # {name, amount} when split_type == "custom"
    category: Category = "other"

class ParsedReceipt(ParsedExpense):
    merchant: str = ""
    items: list[ReceiptItem] = []              # {name, price, assigned_to: list[str]}
    tax_and_tip: float = 0.0
```

## 4. REST API

The base path is `/api`. Interactive docs are at `http://localhost:8000/docs`.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, version, ai_mode, paypal_mode, paypal_configured}` |
| POST | `/demo/seed` | — | `GroupOut` (201) |
| POST | `/groups` | `{name, members:[{name, email?}]}` | `GroupOut` (201) |
| GET | `/groups` · `/groups/{id}` | — | `GroupOut[]` · `GroupOut` |
| POST | `/groups/{id}/members` | `{name, email?}` | `UserOut` (201) · 409 if the name is taken |
| DELETE | `/groups/{id}` | — | 204 |
| POST | `/groups/{id}/expenses/parse` | `{text, sender_id?, source?: chat\|voice}` | `ExpenseParseResponse` (201) · 422 |
| POST | `/groups/{id}/expenses/receipt` | multipart `file, note?, sender_id?` | `ExpenseParseResponse` (201) · 413/415/422 |
| GET | `/groups/{id}/expenses` | — | `ExpenseOut[]` (newest first) |
| DELETE | `/expenses/{id}` | — | 204 |
| GET | `/groups/{id}/export.csv` | — | `text/csv` |
| GET | `/groups/{id}/balances` | — | `{currency, members:[{user, net}], debts:[{from_user, to_user, amount, currency}], naive_transfer_count}` |
| GET | `/groups/{id}/insights` | — | `InsightsOut` |
| POST | `/groups/{id}/ask` | `{question, sender_id?}` | `{answer, ai_mode}` |
| POST | `/groups/{id}/nudge` | `{from_user_id, to_user_id, amount, currency?, tone}` | `{message, ai_mode}` |
| GET | `/groups/{id}/events` | — | SSE: `connected`, `expense.created`, `expense.deleted`, `member.added`, `settlement.completed`, `group.deleted` |
| POST | `/settlements/pay` | `{group_id, from_user_id, to_user_id, amount, currency?}` | `{settlement, approval_url, mode}` (201) |
| POST | `/settlements/{id}/capture` | `{order_id?}` | `SettlementOut` |
| POST | `/settlements/{id}/cancel` | — | `SettlementOut` |
| GET | `/groups/{id}/settlements` | — | `SettlementOut[]` |

Errors always look like `{"detail": "human-readable message"}`. PayPal errors also include a `paypal` field with PayPal's own response.
