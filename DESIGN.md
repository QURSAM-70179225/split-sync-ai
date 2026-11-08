# Design System and UX

## 1. Principles
1. **Conversation first.** The chat is the main input. Forms appear only for group setup.
2. **Show the math.** Every AI result shows how it was split, the category, and the original text, so users can trust it.
3. **One tap to settle.** The settle-up action (PayPal) sits next to each debt.
4. **Never a dead end.** Missing keys, AI errors or a flaky PayPal sandbox fall back gracefully, and each fallback is labelled.
5. **Live by default.** Changes from other devices appear without a refresh, marked by a 🔴 LIVE indicator.

## 2. Visual language
| Token | Value | Use |
|---|---|---|
| Background | `gray-950` + a faint indigo radial glow at the top | App canvas |
| Surface | `gray-900/60`, `border-gray-800`, `rounded-2xl`, `shadow-black/20` | Cards (`<Card>`) |
| Primary | `indigo-600` (hover `indigo-500`) | Primary buttons, user chat bubbles, active tab |
| Positive | `emerald-300/500` | Owed to you, settled, success toasts |
| Negative | `rose-300/500` | You owe, errors |
| Warning | `amber-300/500` | Pending, demo or offline badges |
| PayPal | `#ffc439` button with `#003087` text | **Settle via PayPal** only (follows PayPal's button guidance) |
| Type | Inter / system UI. Money is in `font-mono` | Amounts line up across rows |
| Radius | `rounded-xl` controls, `rounded-2xl` cards, `rounded-full` badges | |
| Motion | `animate-fade-up` (220 ms ease-out) | New chat messages, modals, toasts |

Avatar colours are picked deterministically from user ID (`avatarColor(id)`), so a person keeps the same colour everywhere.

Category colours and icons live in `frontend/src/services/categories.js`, the single source of truth.

## 3. Layout
```
┌──────────┬──────────────────────────────────────────────────────────────┐
│ Sidebar  │ Header: Group name · 🔴 LIVE · avatars · + member · Acting as ▾│
│ ─ Logo   ├──────────────────────────┬───────────────────────────────────┤
│ ─ Groups │  Expense Assistant       │ [⚖️ Balances & Activity | 📊 Insights]│
│ ─ Demo   │  (chat · 📷 · 🎙️ · send) │  Balances & Settlement             │
│ ─ Status │  sticky on xl            │   ⚡ smart-settlement banner         │
│   AI/PP  │                          │   debt rows: 🔔 Nudge · Settle      │
│          │                          │  Activity Ledger (search, filters,  │
│          │                          │   CSV export, expandable rows)      │
└──────────┴──────────────────────────┴───────────────────────────────────┘
```
- **≥ xl (1280 px):** two columns (chat is 5 of 12 columns and sticky, details are 7 of 12).
- **< xl:** everything stacks.
- **< lg:** the sidebar becomes an off-canvas drawer opened from ☰.

## 4. Components (`frontend/src/components`)
| Component | Purpose | Notes |
|---|---|---|
| `ui.jsx` | Avatar, Badge, Card, Spinner, Modal, Toasts, button and input classes | The design-system primitives. Reuse them, don't restyle |
| `Sidebar` | Group switcher, demo seed, AI and PayPal status badges | |
| `ChatPanel` | Text, voice (`useSpeech`) and receipt input. Renders `ExpenseCard` results | Enter sends, Shift+Enter adds a new line |
| `BalancesPanel` | Net tiles, smart-settlement banner, debt rows with Nudge and Settle | "You" wording follows **Acting as** |
| `Ledger` | Chronological feed of expenses and settlements, search, category filter, CSV | Rows expand to show splits and receipt items |
| `InsightsPanel` | KPI tiles, highlights, **Copilot**, category bars, paid vs. share, daily spend | Charts are plain CSS bars, no chart library |
| `NudgeModal` | AI reminder with a tone picker, copy, WhatsApp | |
| `DemoCheckoutModal` | Simulated approval when PayPal isn't configured | Neutral SplitSync branding, labelled "Simulated checkout" |
| `GuidedTour` | Spotlight onboarding: dims the page, highlights a `data-tour` target, places a step card | Steps live in `services/tourSteps.jsx`. Hidden targets are skipped. Bottom sheet on phones. ←/→/Enter/Esc |
| `CreateGroupModal` | Group name and members (with optional emails) | |

## 5. Onboarding (guided tour)
- **Auto-starts** on the first visit (`localStorage: splitsync.tourDone`). It never interrupts a PayPal return. Replay it from **❔ Tour**.
- With no groups, the first step offers **Load demo & start**, so every step has real content to point at.
- 13 steps: welcome → groups → Acting as → chat → 📷/🎙️ → balances → ⚡ smart settlement → Settle/Nudge → ledger → insights (switches tab) → 🔴 live → status → done.
- Each step can run a `before()` hook, e.g. switching tabs. A step whose target isn't visible (sidebar on a phone, or no ⚡ banner) is skipped automatically.
- Accessibility: the card is `role="dialog"` and receives focus. Keyboard: ←/→/Enter/Esc.

## 6. UX copy rules
- Speak like a friend: "Hmm, I couldn't log that: …", "🎉 Everyone is settled up."
- Use "You" for the current identity: "You owe Sarah", not "You owes Sarah".
- Error messages say what to do next: "Receipt scanning needs a Gemini API key (set GEMINI_API_KEY in backend/.env)."
- Always label demo or offline states. Never pretend a simulated payment was real.

## 7. Accessibility
- Every icon-only button has `aria-label` and `title` (📷, 🎙️, send, close, menu).
- Modals use `role="dialog" aria-modal="true"`. Tabs use `role="tab"` and `aria-selected`.
- Colour is never the only signal: amounts carry +/− signs, and statuses have text badges.
- Text meets WCAG AA contrast on `gray-950`.

## 8. Demo script (3 minutes)
1. **Hook (15 s):** "Splitting bills is a group chat argument. We made it a group *chat*."
2. Open the app in a fresh browser. The **guided tour** starts. Click **Load demo & start** and walk the first few steps, then press Esc.
3. Click **🌴 Load demo trip** if it isn't already loaded. The ⚡ banner reads "3 payments instead of 6".
4. Type: *"Jordan paid $48 for pizza with Alex and Sarah"*. It's parsed instantly.
5. Click 🎙️ and say *"I paid 30 dollars for coffee with Sarah"*.
6. 📷 Scan a real receipt with the note *"Alex had the burger"* for an itemized split (needs a Gemini key).
7. Open a **second browser window**, add an expense there, and point at the 🔴 LIVE toast in the first window.
8. On a debt row, click **🔔 Nudge**, switch to the 😂 Funny tone, and copy the message.
9. Click **Settle via PayPal**, approve on PayPal Sandbox, and watch the debt vanish and the ledger show ✓.
10. Open **📊 Insights**, ask *"Who paid the most?"*, then show the category bars.
