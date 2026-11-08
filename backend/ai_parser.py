"""All Gemini-powered intelligence for SplitSync AI.

* parse_expense_prompt  – free text  -> ParsedExpense   (structured output)
* parse_receipt         – photo      -> ParsedReceipt   (vision + structured output)
* answer_question       – "how much did we spend on food?" over the ledger
* write_nudge           – a friendly payment reminder

Every function except receipt scanning has a deterministic offline fallback, so the
app still demos end to end without an API key (or when the API is down / out of quota).
"""
from __future__ import annotations

import json
import logging
import re

from config import get_settings
from schemas import CATEGORIES, ParsedExpense, ParsedReceipt

log = logging.getLogger("splitsync.ai")


class ExpenseParseError(ValueError):
    """Raised when text/image can't be turned into a valid expense (maps to HTTP 422)."""


def ai_mode() -> str:
    s = get_settings()
    return f"gemini:{s.gemini_model}" if s.ai_enabled else "offline"


# ------------------------------------------------------------------ prompts
EXPENSE_PROMPT = """You are SplitSync AI, an expense-splitting assistant.
Extract a single shared expense from the user's message and return JSON only.

Rules:
- Group members: {members}. Map nicknames / casing to these exact names when possible.
  If someone not in the list is mentioned, use their name as written (Title Case).
- The person sending the message is "{sender}". Resolve "I", "me", "my", "myself" to "{sender}".
- payer_name: who paid. If unstated, assume the sender paid.
- participants: everyone who shares the cost. "split between us/everyone/all" means all group members.
  "split with X" means the payer AND X. Include the payer only if they share the cost.
- split_type "equal" unless explicit per-person amounts or percentages are given; then "custom" and
  fill custom_shares with the amount each participant owes (convert percentages to amounts;
  custom_shares must sum to total_amount).
- total_amount is a positive number. currency is an ISO 4217 code (default USD; "€" -> EUR, "£" -> GBP).
- description: 1-4 words, Title Case, e.g. "Dinner", "Uber To Airport".
- category: one of {categories}.
"""

RECEIPT_PROMPT = """You are SplitSync AI reading a photo of a receipt.
Group members: {members}. The uploader is "{sender}" and paid unless the note says otherwise.
Uploader's note (may assign items to people, may be empty): "{note}"

Return JSON only:
- merchant, items (name + price, exclude tax/tip lines), tax_and_tip (sum of tax, tip, service).
- total_amount = the final total actually paid (items + tax_and_tip).
- For each item, assigned_to = members named in the note for that item; leave empty if shared.
- If any item is assigned, split_type = "custom" and custom_shares must give each participant's
  amount: their assigned items + an equal share of unassigned items, with tax_and_tip distributed
  proportionally to each person's subtotal. custom_shares must sum to total_amount.
- Otherwise split_type = "equal" among all members (or those named in the note).
- description: merchant or what was bought (1-4 words, Title Case). currency: ISO 4217 code.
- category: one of {categories}.
"""

ASK_PROMPT = """You are SplitSync AI, a sharp, friendly finance copilot for a group of friends.
Answer the question using ONLY the ledger JSON below. Be concise (max 3 sentences), use exact
amounts with currency symbols, and name people. The person asking is "{sender}" ("I"/"me").
If the data can't answer it, say so briefly.

LEDGER:
{context}
"""

NUDGE_PROMPT = """Write a short payment reminder text message (max 2 sentences, 1 emoji max) that
{creditor} can send to {debtor}, who owes {amount} for the group "{group}".
Tone: {tone}. Never be rude or guilt-trippy. Mention it can be settled in one tap with PayPal.
Return only the message text."""


# ------------------------------------------------------------------ gemini
def _client():
    from google import genai

    return genai.Client(api_key=get_settings().gemini_api_key)


def _generate(contents, system: str, schema=None, temperature: float = 0.0):
    from google.genai import types

    cfg = types.GenerateContentConfig(system_instruction=system, temperature=temperature)
    if schema is not None:
        cfg.response_mime_type = "application/json"
        cfg.response_schema = schema
    return _client().models.generate_content(model=get_settings().gemini_model, contents=contents, config=cfg)


def _structured(response, schema):
    parsed = response.parsed
    if isinstance(parsed, schema):
        return parsed
    if not response.text:
        raise ExpenseParseError("Gemini returned an empty response")
    return schema.model_validate_json(response.text)


# ------------------------------------------------------------------ offline helpers
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "food": ("dinner", "lunch", "breakfast", "brunch", "pizza", "burger", "restaurant", "cafe", "coffee",
             "drinks", "bar", "beer", "sushi", "tacos", "food", "meal", "snack", "dessert", "takeout"),
    "groceries": ("grocer", "supermarket", "market", "costco", "walmart", "aldi", "tesco", "supplies"),
    "transport": ("uber", "lyft", "taxi", "cab", "gas", "fuel", "petrol", "parking", "train", "bus",
                  "metro", "subway", "toll", "car rental", "rental car", "scooter"),
    "lodging": ("hotel", "airbnb", "hostel", "rent", "villa", "cabin", "motel", "accommodation"),
    "entertainment": ("movie", "cinema", "concert", "tickets", "show", "museum", "game", "club",
                      "karaoke", "bowling", "netflix", "spotify", "festival", "tour", "surf", "dive"),
    "shopping": ("shopping", "gift", "clothes", "souvenir", "amazon", "mall"),
    "utilities": ("electric", "internet", "wifi", "water bill", "utility", "phone bill", "power"),
    "travel": ("flight", "airline", "plane", "visa", "luggage", "ferry", "boat"),
    "health": ("pharmacy", "doctor", "medicine", "gym", "spa", "massage"),
}


def categorize(text: str) -> str:
    t = text.lower()
    for cat, words in _CATEGORY_KEYWORDS.items():
        if any(w in t for w in words):
            return cat
    return "other"


_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
_SELF_WORDS = {"i", "me", "my", "myself"}
_STOPWORDS = {"the", "a", "an", "everyone", "everybody", "all", "us", "split", "for", "friends", "them"}
_ALL_WORDS = ("everyone", "everybody", "all of us", "the group", "us all", "between us", "among us", "for all")


def _offline_parse(text: str, members: list[str], sender: str) -> ParsedExpense:
    lowered = text.lower()
    m = re.search(
        r"([$€£₹¥])\s?(\d+(?:[.,]\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s?(usd|eur|gbp|inr|dollars?|bucks|euros?)?",
        text, re.I,
    )
    if not m:
        raise ExpenseParseError("Couldn't find an amount in that message.")
    if m.group(2):
        amount, currency = float(m.group(2).replace(",", ".")), _CURRENCY_SYMBOLS[m.group(1)]
    else:
        amount = float(m.group(3))
        code = (m.group(4) or "usd").lower()
        currency = "EUR" if code.startswith("eur") else {"gbp": "GBP", "inr": "INR"}.get(code, "USD")

    member_lookup = {n.lower(): n for n in members}
    first_names = {n.lower().split()[0]: n for n in members}
    mentioned: list[str] = []
    for w in re.findall(r"[A-Za-z][A-Za-z'-]*", text):
        lw = w.lower()
        name = sender if lw in _SELF_WORDS else member_lookup.get(lw) or first_names.get(lw)
        if name and name not in mentioned:
            mentioned.append(name)

    # Capitalized names after "with"/"and"/"," that aren't members yet (auto-added later)
    for cand in re.findall(r"(?:\bwith|\band|\bbetween|,)\s+([A-Z][a-z]{1,20})\b", text):
        if cand.lower() not in _SELF_WORDS | _STOPWORDS and cand.lower() not in member_lookup \
                and cand.lower() not in first_names and cand not in mentioned:
            mentioned.append(cand)

    payer = sender
    pm = re.search(r"\b([A-Za-z]+)\s+(?:paid|covered|bought|spent|got)\b", text, re.I) or re.search(
        r"\bpaid\s+by\s+([A-Za-z]+)", text, re.I
    )
    if pm:
        cand = pm.group(1).lower()
        payer = sender if cand in _SELF_WORDS else member_lookup.get(cand) or first_names.get(cand, payer)

    if any(w in lowered for w in _ALL_WORDS) or (len(mentioned) <= 1 and "with" not in lowered):
        participants = list(members)
    else:
        participants = mentioned
    if payer not in participants and ("with" in lowered or "and me" in lowered):
        participants.insert(0, payer)
    participants = participants or [payer]

    dm = re.search(
        r"\bfor\s+(?:the\s+|a\s+|an\s+|our\s+)?([A-Za-z][A-Za-z ]{1,30}?)(?:[,.:]|\s+(?:split|with|between|and|for)\b|$)",
        text, re.I,
    )
    if not dm:  # "the $24 Uber", "40 bucks pizza"
        dm = re.search(
            r"[$€£₹¥]?\d+(?:[.,]\d{1,2})?\s*(?:usd|eur|gbp|inr|dollars?|bucks|euros?)?\s+"
            r"(?!for\b|on\b|to\b|with\b|split\b)([A-Za-z][A-Za-z ]{1,25}?)(?:[,.:]|\s+(?:split|with|between|and|for)\b|$)",
            text, re.I,
        )
    description = dm.group(1).strip().title() if dm else "Shared Expense"

    return ParsedExpense(
        total_amount=round(amount, 2),
        currency=currency,
        description=description,
        payer_name=payer,
        split_type="equal",
        participants=participants,
        category=categorize(f"{description} {text}"),
    )


# ------------------------------------------------------------------ public API
def _finalize(parsed: ParsedExpense) -> ParsedExpense:
    if parsed.total_amount <= 0:
        raise ExpenseParseError("The expense amount must be greater than zero.")
    if not parsed.participants and not parsed.custom_shares:
        raise ExpenseParseError("Couldn't tell who should share this expense.")
    parsed.currency = (parsed.currency or "USD").upper()[:3]
    if parsed.category not in CATEGORIES or parsed.category == "other":
        parsed.category = categorize(parsed.description)
    return parsed


def parse_expense_prompt(text: str, members: list[str], sender: str | None = None) -> ParsedExpense:
    """Turn free text into a validated ParsedExpense."""
    sender = sender or (members[0] if members else "Me")
    if not get_settings().ai_enabled:
        return _finalize(_offline_parse(text, members, sender))
    try:
        resp = _generate(
            text,
            EXPENSE_PROMPT.format(members=", ".join(members) or "(none)", sender=sender,
                                  categories=", ".join(CATEGORIES)),
            ParsedExpense,
        )
        return _finalize(_structured(resp, ParsedExpense))
    except ExpenseParseError:
        raise
    except Exception as exc:
        log.warning("Gemini parse failed, using offline parser: %s", exc)
        try:
            return _finalize(_offline_parse(text, members, sender))
        except ExpenseParseError:
            raise ExpenseParseError(f"AI parsing failed: {exc}") from exc


def parse_receipt(image: bytes, mime_type: str, members: list[str], sender: str, note: str = "") -> ParsedReceipt:
    """Read a receipt photo with Gemini Vision and propose an itemized split."""
    if not get_settings().ai_enabled:
        raise ExpenseParseError("Receipt scanning needs a Gemini API key (set GEMINI_API_KEY in backend/.env).")
    from google.genai import types

    try:
        resp = _generate(
            [types.Part.from_bytes(data=image, mime_type=mime_type), "Parse this receipt."],
            RECEIPT_PROMPT.format(members=", ".join(members), sender=sender, note=note.replace('"', "'"),
                                  categories=", ".join(CATEGORIES)),
            ParsedReceipt,
        )
        parsed = _structured(resp, ParsedReceipt)
    except ExpenseParseError:
        raise
    except Exception as exc:
        log.exception("Gemini receipt parsing failed")
        raise ExpenseParseError(f"Couldn't read that receipt: {exc}") from exc
    if not parsed.participants:
        parsed.participants = list(members)
    return _finalize(parsed)  # type: ignore[return-value]


def _offline_answer(question: str, ctx: dict, sender: str) -> str:
    q = question.lower()
    cur = ctx.get("currency", "USD")
    fmt = lambda v: f"{v:,.2f} {cur}"  # noqa: E731
    for cat in CATEGORIES:
        if cat in q or any(w in q for w in _CATEGORY_KEYWORDS.get(cat, ())[:4]):
            total = sum(c["total"] for c in ctx["by_category"] if c["category"] == cat)
            return f"The group has spent {fmt(total)} on {cat}."
    if any(w in q for w in ("owe", "debt", "settle", "pay back")):
        mine = [d for d in ctx["debts"] if sender in (d["from"], d["to"])] if any(
            w in q.split() for w in ("i", "me", "my")) else ctx["debts"]
        if not mine:
            return "Nobody owes anything — the group is all square. 🎉"
        return " ".join(f"{d['from']} {'owe' if d['from'] == 'You' else 'owes'} {d['to']} {fmt(d['amount'])}."
                        for d in mine[:4])
    if any(w in q for w in ("most", "biggest", "top", "who paid")):
        top = max(ctx["by_person"], key=lambda p: p["paid"], default=None)
        if top:
            return f"{top['name']} {'have' if top['name'] == 'You' else 'has'} paid the most so far: {fmt(top['paid'])}."
    if any(w in q for w in ("largest", "expensive")) and ctx.get("largest"):
        big = ctx["largest"]
        return f"The largest expense was {big['description']} at {fmt(big['amount'])}, paid by {big['payer']}."
    return (f"So far the group has logged {ctx['expense_count']} expenses totalling {fmt(ctx['total_spent'])}. "
            "Try asking: “How much did we spend on food?” or “Who owes me?”")


def answer_question(question: str, ctx: dict, sender: str) -> str:
    if not get_settings().ai_enabled:
        return _offline_answer(question, ctx, sender)
    try:
        resp = _generate(question, ASK_PROMPT.format(sender=sender, context=json.dumps(ctx, default=str)),
                         temperature=0.3)
        return (resp.text or "").strip() or _offline_answer(question, ctx, sender)
    except Exception as exc:
        log.warning("Gemini ask failed, using offline answer: %s", exc)
        return _offline_answer(question, ctx, sender)


_NUDGE_TEMPLATES = {
    "friendly": "Hey {debtor}! 👋 Quick reminder that you owe me {amount} from {group} — you can settle it in one tap with PayPal on SplitSync. Thanks!",
    "funny": "{debtor}, my wallet misses its {amount} from {group} 🥲 Reunite them in one tap via PayPal on SplitSync?",
    "formal": "Hi {debtor}, a reminder that {amount} is outstanding for {group}. You can settle it via PayPal in SplitSync at your convenience.",
}


def write_nudge(debtor: str, creditor: str, amount: str, group: str, tone: str) -> str:
    fallback = _NUDGE_TEMPLATES[tone].format(debtor=debtor, amount=amount, group=group)
    if not get_settings().ai_enabled:
        return fallback
    try:
        resp = _generate("Write the message.", NUDGE_PROMPT.format(
            debtor=debtor, creditor=creditor, amount=amount, group=group, tone=tone), temperature=0.8)
        return (resp.text or "").strip().strip('"') or fallback
    except Exception as exc:
        log.warning("Gemini nudge failed, using template: %s", exc)
        return fallback
