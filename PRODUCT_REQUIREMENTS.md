# SplitSync AI: Product Requirements Document

| | |
|---|---|
| **Product** | SplitSync AI: conversational group expense tracking with autonomous settlement |
| **Status** | v2.0, hackathon MVP (production-ready core) |
| **Integrations** | Google Gemini (structured output + vision), PayPal Orders v2 (Sandbox) |

## 1. Problem

Splitting shared costs is tedious. Existing apps use forms: pick the payer, type the amount, tick the participants, choose a split type. Groups give up halfway through a trip. At the end, the app hands back a confusing web of IOUs, and paying them back happens in another app.

**Three problems to solve:**
1. **Logging friction.** Forms are slow, so people forget to log expenses.
2. **Settlement complexity.** With N people, pairwise IOUs can need up to N(N−1)/2 payments.
3. **Settlement drop-off.** "I'll pay you later" means the money often never gets paid.

## 2. Solution

SplitSync AI lets a group **talk, split and settle**:
- **Talk.** Log an expense the way you'd text a friend: type it, say it, or photograph the receipt. Gemini turns it into a structured, validated expense.
- **Split.** Exact-cent splitting, auto-categorization, and debt simplification down to the fewest payments.
- **Settle.** One tap opens PayPal checkout. When it's captured, the ledger updates for every member in real time.

## 3. Target users

| Persona | Need |
|---|---|
| **Trip organizer** (primary) | Fronts most costs, wants to get paid back without awkward chasing |
| **Housemates** | Recurring groceries and utilities, a fair monthly settle-up |
| **Event or club treasurer** | A transparent ledger they can export for records |

## 4. Goals and success metrics

| Goal | Metric | Target |
|---|---|---|
| Effortless logging | Median time from message to logged expense | < 3 s |
| Parse accuracy | Messages parsed correctly with no edits | ≥ 95% on the demo corpus |
| Fewer payments | Payments after simplification vs. pairwise | ≤ N−1 payments for N members |
| Settlement completion | Debts settled within 7 days | ≥ 60% |
| Trust | Splits always add up to the expense total | 100% (exact cents, tested) |

## 5. Features

### 5.1 Must have (shipped ✅)
| ID | Feature | Acceptance criteria |
|---|---|---|
| F1 | Groups and members | Create a group with ≥ 1 member, names unique (case-insensitive), optional email |
| F2 | **Conversational logging** | `POST /expenses/parse` turns text into an expense with payer, total, participants and splits. "I"/"me" resolve to the sender. Unknown names are added as members automatically |
| F3 | Equal and custom splits | Equal splits are exact to the cent. Custom shares must add up to the total (±0.02) or the API returns 422 with a clear message |
| F4 | Ledger | Newest first, with payer, amount, category, split breakdown, original text and paid/pending status |
| F5 | **Balances and smart settlement** | Net per member sums to 0. Greedy simplification needs ≤ N−1 payments. Shows "X payments instead of Y" |
| F6 | **PayPal settlement** | Creates an order → approval → capture. Capture is idempotent. Overpaying is rejected. Splits are marked paid |
| F7 | Offline resilience | No Gemini key → regex parser. No PayPal keys → simulated checkout. If Gemini errors, it falls back automatically |

### 5.2 Differentiators (shipped ✅)
| ID | Feature | Why it wins |
|---|---|---|
| D1 | **🎙️ Voice logging** | Web Speech API: say "I paid 40 bucks for pizza with Alex" |
| D2 | **📷 Receipt scanning with itemized split** | Gemini Vision reads the line items. A note like "Alex had the steak" assigns items. Tax and tip are spread proportionally |
| D3 | **✨ Ask your ledger** | Plain-English questions, e.g. "How much did we spend on food?", answered from the ledger |
| D4 | **🔔 AI nudges** | Writes a reminder in a friendly, funny or formal tone, with copy and WhatsApp share |
| D5 | **🔴 Live sync** | Server-Sent Events: an expense added on one phone shows up on every other device instantly |
| D6 | **📊 Insights** | Category breakdown, paid vs. fair share, daily spend, AI highlights, settlement progress |
| D7 | **🌴 One-click demo trip** | Judges see a realistic 4-person, 9-expense trip in one click |
| D8 | CSV export | One row per split, for accounting or a spreadsheet |

### 5.3 Later (out of scope for v2)
- Authentication and invite links (magic link or OAuth). The current "Acting as" selector stands in for identity.
- Multi-currency conversion using FX rates (the ledger already keeps a currency per expense).
- Recurring expenses ("rent every month").
- PayPal webhooks (`CHECKOUT.ORDER.APPROVED`) as a backup when a user closes the tab before coming back.
- Payouts API, so the creditor receives the money directly instead of the merchant account.
- A mobile PWA with offline queueing.

## 6. User stories
1. *As a trip organizer,* I type "I paid $412 for the villa, split between everyone" and see it split four ways right away.
2. *As a diner,* I photograph the bill, add "Alex had the steak, Sarah the salad", and each person owes what they actually ate plus their share of tax.
3. *As someone who owes money,* I see "You owe Sarah $87.03" and pay with one tap through PayPal.
4. *As the creditor,* I send an AI-written friendly reminder instead of an awkward text.
5. *As a housemate,* I ask "who paid the most this month?" and get a one-line answer.

## 7. Non-functional requirements
| Area | Requirement |
|---|---|
| Correctness | Money is computed in whole cents. Balances sum to 0. Covered by tests |
| Security | Secrets live only in `.env`. API keys are never sent to the browser. Uploads are checked for type and size (≤ 8 MB) |
| Reliability | Every AI feature degrades gracefully. PayPal capture is idempotent |
| Performance | API p95 < 100 ms excluding AI calls. SSE keep-alive every 15 s |
| Observability | Request ID and timing on every request. Errors logged with stack traces, and the client gets a safe message |
| Portability | Runs on Windows, macOS, Linux and Docker |
| Accessibility | Keyboard-navigable, labelled icon buttons, dark theme with AA contrast |

## 8. Risks
| Risk | Mitigation |
|---|---|
| The LLM misreads a message | Strict schema plus server-side validation, the original text is shown, the expense can be deleted |
| Gemini quota or outage | Automatic offline fallback |
| PayPal sandbox is flaky during the live demo | `PAYPAL_MODE=demo` simulated checkout, clearly labelled |
| No auth | Scoped as a single-tenant MVP. Auth is first on the roadmap |
