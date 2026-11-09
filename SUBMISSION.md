# 🏆 Hackathon Submission Kit

Everything you need for the submission form, in one place. Copy, paste, done.

## ✅ Requirements checklist

| # | Requirement | Status | Where |
|---|---|---|---|
| 1 | Project **meaningfully uses PayPal** (sandbox OK) **and AI** | ✅ | PayPal Orders v2 create, approve, capture for every settle-up. Gemini for text, receipt-vision, copilot and nudges. See [How PayPal is used](#how-paypal-is-used) and [How AI is used](#how-ai-is-used) |
| 2 | **Judges can run it**: hosted URL or run instructions | ✅ | Run instructions: [README → Run it](README.md#-run-it-locally). Hosted: deploy with the Render button in [DEPLOY.md](DEPLOY.md), then paste the URL below |
| 3 | **Public repo** with README and an **open-source license** | ✅ | [README.md](README.md) · [LICENSE](LICENSE) (MIT). Make sure the repo is **Public** |
| 4 | **Public YouTube video under 3 minutes** | 🔲 *you* | Use the [video shot list](#-video-shot-list-under-3-min) below. Set visibility to **Public** |
| 5 | **Sponsor tools selected** on the form | 🔲 *you* | Select **PayPal** and **Google Gemini** (plus any other sponsors you used) |
| 6 | **Teammates invited and accepted** | 🔲 *you* | Invite them on the hackathon platform and make sure each one **accepts** before the deadline |

### Before you hit submit
- [ ] Repo is **Public**: GitHub → Settings → General → Danger Zone → Change visibility
- [ ] Render URL opens. Open it once first to wake the free instance
- [ ] Keys added on Render (Environment tab), and the sidebar shows **Gemini** and **Sandbox**
- [ ] Test one PayPal Sandbox payment end to end on the hosted URL
- [ ] YouTube video is **Public**, not Unlisted or Private, and **< 3:00**
- [ ] README "Live demo" and "Video" links updated
- [ ] Sponsor tools ticked, teammates accepted

---

## 📝 Form copy (paste-ready)

**Project name**
> SplitSync AI

**Tagline / one-liner (≤ 100 chars)**
> Split group expenses by just talking. AI does the math, PayPal settles it in one tap.

**Short description (~50 words)**
> SplitSync AI turns group expenses into a conversation. Type, say, or photograph a receipt. Google Gemini turns it into an exact, itemized split. Debts are simplified to the fewest payments, and each one settles in one tap with PayPal. Every friend's screen updates live.

**Full description**
> **The problem.** Splitting costs on a trip or in a shared house means tedious forms, a tangle of IOUs, and "I'll pay you later" money that never arrives.
>
> **What we built.** SplitSync AI is a conversational expense ledger with autonomous settlement:
> - **Talk:** log expenses in plain English ("I paid $60 for dinner with Alex and Sarah"), by voice, or by snapping a receipt. Gemini Vision reads the line items, and a note like "Alex had the steak" assigns items to people, with tax and tip spread proportionally.
> - **Split:** splits are exact to the cent, expenses are auto-categorized, and a debt-simplification algorithm reduces N people's IOUs to at most N−1 payments ("3 payments instead of 6").
> - **Settle:** each debt has a **Settle via PayPal** button. We create a PayPal order, the debtor approves in PayPal checkout, and we capture it. The ledger marks the splits paid and every member's screen updates in real time over Server-Sent Events.
> - **Understand:** an AI copilot answers questions about the group's money ("How much did we spend on food?"), an insights dashboard shows where the money went, and AI-written nudges (friendly, funny or formal) chase debts politely.
>
> **Built for real use:** 16 automated tests, CI, Docker, one-click Render deploy, a guided onboarding tour, and graceful fallbacks so the app keeps working even if an API is down.

### How PayPal is used
> PayPal is the settlement layer. When a member clicks **Settle via PayPal**, the backend authenticates with OAuth2 client credentials (token cached) and calls **Orders v2 `POST /v2/checkout/orders`** with `intent: CAPTURE`. It sets an `experience_context` with `return_url` and `cancel_url` that point back to the app, `user_action: PAY_NOW` and `shipping_preference: NO_SHIPPING`. The debtor approves on PayPal's checkout page. On return, the app calls **`POST /v2/checkout/orders/{id}/capture`**. Capture is idempotent (`ORDER_ALREADY_CAPTURED` counts as success) and is only accepted when the order ID matches the settlement and the amount doesn't exceed the outstanding debt. A successful capture marks the debtor's splits as paid and broadcasts a live update to the whole group. Optional `payee.email_address` routing can send each payment straight to the creditor's PayPal account.

### How AI is used
> Google Gemini (`gemini-3.8-flash` via the `google-genai` SDK) powers four features:
> 1. **Conversational parsing.** Free text goes through `response_schema=ParsedExpense` (Pydantic) to strict JSON: payer, total, currency, participants, equal or custom shares, category. Pronouns resolve to the sender, and nicknames map to member names.
> 2. **Receipt vision.** A photo plus an optional note goes through `ParsedReceipt`: merchant, line items, per-item assignees, tax and tip, and per-person shares.
> 3. **Ledger copilot.** Natural-language questions are answered from a compact JSON snapshot of the ledger.
> 4. **Nudges.** Tone-controlled payment reminders.
>
> Every AI result is validated server-side (cent-exact sums, positive amounts) before it touches money. Each feature also has a deterministic fallback, so the app keeps working when there's no key or the API errors.

**Built with**
> Python, FastAPI, SQLAlchemy, SQLite, Pydantic, Google Gemini (google-genai), PayPal REST Orders v2, React 19, Vite, Tailwind CSS v4, Server-Sent Events, Web Speech API, Docker, Render, GitHub Actions, pytest

**Sponsor tools to select:** PayPal · Google Gemini *(add any other sponsor tools you used)*

**Links**
> - Repo: https://github.com/QURSAM-70179225/split-sync-ai
> - Live demo: https://split-sync-ai.onrender.com
> - Video: `https://youtu.be/<id>` *(after uploading)*

**Challenges we ran into**
> Making LLM output safe enough to move money: strict schemas plus server-side validation and cent-exact math. Live sync from synchronous request handlers, done with a thread-safe broker into an async SSE stream. Keeping the demo bulletproof, with offline fallbacks for every AI feature and a clearly labelled simulated checkout when sandbox keys are missing.

**Accomplishments we're proud of**
> One sentence goes from words to an exact split to a PayPal capture to a live update on every phone. Receipt items get assigned from a casual note, with tax and tip spread correctly.

**What's next**
> Auth and invite links, PayPal webhooks as a capture backup, payouts directly to creditors, multi-currency with live FX, recurring expenses.

---

## 🎬 Video shot list (under 3 min)

Record at 1080p with the browser zoomed to 110%. Use the hosted URL with keys set. Keep each shot short.

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | Title card or the app's empty state | "Splitting bills shouldn't need a spreadsheet. SplitSync AI lets your group just *talk*, and settles up with PayPal." |
| 0:15–0:30 | Guided tour → **Load demo & start**, two or three steps, then Esc | "New users get a guided tour. Here's a 4-person trip to Bali." |
| 0:30–0:55 | Type *"I paid $60 for dinner, split between me, Alex and Sarah"* | "Gemini turns plain English into a structured, exact split, with category, payer and shares." |
| 0:55–1:10 | 🎙️ say *"Alex paid 24 dollars for the Uber with me"* | "Or just say it." |
| 1:10–1:35 | 📷 receipt with the note *"Alex had the burger"* | "Snap a receipt. Gemini Vision reads every line and splits items per person, with tax and tip spread fairly." |
| 1:35–1:50 | Balances: the ⚡ banner | "We simplify the group's debts. Three payments instead of six." |
| 1:50–2:25 | **Settle via PayPal** → PayPal Sandbox login → Pay → back in the app with the debt gone. Second window shows the 🔴 Live toast | "One tap opens PayPal checkout. We create the order, capture it on return, and every friend's screen updates live." |
| 2:25–2:45 | 🔔 Nudge (Funny) → Insights → ask *"How much did we spend on food?"* | "AI nudges chase debts politely, and the copilot answers questions about your money." |
| 2:45–2:58 | README / architecture diagram | "FastAPI, React, Gemini and PayPal Orders v2. Tested, Dockerized, open source. SplitSync AI: talk, split, settle." |

**Tips:** close other tabs, turn on Do Not Disturb, log in to the sandbox buyer account in advance (Testing Tools → Sandbox Accounts → *Personal*), and wake the Render instance before recording.
