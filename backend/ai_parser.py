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
from functools import lru_cache

from config import get_settings
from schemas import CATEGORIES, ParsedExpense, ParsedReceipt

log = logging.getLogger("splitsync.ai")


class ExpenseParseError(ValueError):
    """Raised when text/image can't be turned into a valid expense (maps to HTTP 422)."""


# Tried in order after GEMINI_MODEL when Google reports a model as retired / not found.
FALLBACK_MODELS = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-flash-latest")
_working_model: str | None = None


def current_model() -> str:
    return _working_model or get_settings().gemini_model


def ai_mode() -> str:
    return f"gemini:{current_model()}" if get_settings().ai_enabled else "offline"


def _is_model_missing(exc: Exception) -> bool:
    msg = str(exc)
    return getattr(exc, "code", None) == 404 or "NOT_FOUND" in msg or "no longer available" in msg


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
@lru_cache(maxsize=1)
def _client():
    """One long-lived client per process.

    google-genai >= 3 closes a Client when it is garbage-collected, so a throwaway
    `genai.Client(...).models.generate_content(...)` fails with "client has been closed".
    """
    from google import genai

    return genai.Client(api_key=get_settings().gemini_api_key)


def _generate(contents, system: str, schema=None, temperature: float = 0.0, schema_mode: str = "pydantic"):
    """One Gemini call. schema_mode: 'pydantic' (response_schema), 'json' (response_json_schema)
    or 'prompt' (JSON mime type + schema in the instructions)."""
    from google.genai import types

    if schema is not None and schema_mode == "prompt":
        system = f"{system}\n\nReturn ONLY a JSON object matching this JSON Schema:\n{json.dumps(schema.model_json_schema())}"
    cfg = types.GenerateContentConfig(system_instruction=system, temperature=temperature)
    if schema is not None:
        cfg.response_mime_type = "application/json"
        if schema_mode == "pydantic":
            cfg.response_schema = schema
        elif schema_mode == "json":
            cfg.response_json_schema = schema.model_json_schema()
    global _working_model
    client = _client()
    candidates = [current_model()] + [m for m in (get_settings().gemini_model, *FALLBACK_MODELS) if m != current_model()]
    last_exc: Exception | None = None
    for model in dict.fromkeys(candidates):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
        except Exception as exc:
            if _is_model_missing(exc):
                log.warning("Gemini model %s unavailable, trying the next one", model)
                last_exc = exc
                continue
            raise
        if model != _working_model:
            if model != get_settings().gemini_model:
                log.warning("Using Gemini model %s (GEMINI_MODEL=%s is unavailable)", model, get_settings().gemini_model)
            _working_model = model
        return resp
    raise last_exc or RuntimeError("No Gemini model available")


def _structured(response, schema):
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, schema):
        return parsed
    text = (response.text or "").strip()
    if not text:
        raise ValueError("Gemini returned an empty response")
    if text.startswith("```"):  # tolerate fenced JSON
        text = text.strip("`").removeprefix("json").strip()
    return schema.model_validate_json(text)


SCHEMA_MODES = ("pydantic", "json", "prompt")
_schema_mode: str | None = None
_last_ai_errors: list[str] = []


def _is_fatal(exc: Exception) -> bool:
    """Errors no schema strategy can fix: bad key, permissions, quota, retired model."""
    code = getattr(exc, "code", None)
    msg = str(exc)
    return code in (401, 403, 429) or "RESOURCE_EXHAUSTED" in msg or "API key not valid" in msg or _is_model_missing(exc)


def _generate_structured(contents, system: str, schema, temperature: float = 0.0):
    """Structured output that survives SDK/model differences.

    Tries response_schema (Pydantic), then response_json_schema, then prompt-only JSON, and
    remembers the first strategy that works. The result is always validated by Pydantic.
    """
    global _schema_mode
    modes = [_schema_mode] if _schema_mode else []
    modes += [m for m in SCHEMA_MODES if m not in modes]
    errors: list[str] = []
    for mode in modes:
        try:
            result = _structured(_generate(contents, system, schema, temperature, schema_mode=mode), schema)
        except Exception as exc:
            errors.append(f"{mode}: {type(exc).__name__}: {_scrub(str(exc))[:200]}")
            log.warning("Gemini structured output (%s) failed: %s", mode, errors[-1])
            if _is_fatal(exc):
                break
            continue
        if mode != _schema_mode:
            log.info("Gemini structured output strategy: %s", mode)
            _schema_mode = mode
        _last_ai_errors.clear()
        return result
    _last_ai_errors[:] = errors
    raise RuntimeError(" | ".join(errors) or "Gemini structured output failed")


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
        parsed = _finalize(_generate_structured(
            text,
            EXPENSE_PROMPT.format(members=", ".join(members) or "(none)", sender=sender,
                                  categories=", ".join(CATEGORIES)),
            ParsedExpense,
        ))
        parsed._source = ai_mode()
        return parsed
    except ExpenseParseError:
        raise
    except Exception as exc:
        log.warning("Gemini parse failed, using offline parser: %s", _scrub(str(exc)))
        try:
            parsed = _finalize(_offline_parse(text, members, sender))
        except ExpenseParseError:
            raise ExpenseParseError(f"AI parsing failed: {exc}") from exc
        parsed._fallback_reason = f"{type(exc).__name__}: {_scrub(str(exc))[:160]}"
        return parsed


def parse_receipt(image: bytes, mime_type: str, members: list[str], sender: str, note: str = "") -> ParsedReceipt:
    """Read a receipt photo with Gemini Vision and propose an itemized split."""
    if not get_settings().ai_enabled:
        raise ExpenseParseError("Receipt scanning needs a Gemini API key (set GEMINI_API_KEY in backend/.env).")
    from google.genai import types

    try:
        parsed = _generate_structured(
            [types.Part.from_bytes(data=image, mime_type=mime_type), "Parse this receipt."],
            RECEIPT_PROMPT.format(members=", ".join(members), sender=sender, note=note.replace('"', "'"),
                                  categories=", ".join(CATEGORIES)),
            ParsedReceipt,
        )
    except ExpenseParseError:
        raise
    except Exception as exc:
        log.exception("Gemini receipt parsing failed")
        raise ExpenseParseError(f"Couldn't read that receipt: {exc}") from exc
    if not parsed.participants:
        parsed.participants = list(members)
    parsed = _finalize(parsed)
    parsed._source = ai_mode()
    return parsed  # type: ignore[return-value]


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


def _scrub(msg: str) -> str:
    """Remove anything that looks like an API key from an error message."""
    return re.sub(r"AIza[0-9A-Za-z_-]{10,}", "AIza…", msg)[:300]


def check_ai() -> dict:
    """Live diagnostic: a plain call and a structured-output call. Never returns the key."""
    import itertools

    s = get_settings()
    out: dict = {"mode": ai_mode(), "configured_model": s.gemini_model, "key_set": bool(s.gemini_api_key)}
    if not s.ai_enabled:
        out.update(ok=False, error="AI disabled (no GEMINI_API_KEY, or AI_OFFLINE_MODE=true)")
        return out
    try:
        resp = _generate("Reply with the single word: pong", "You are a health check.")
        out["plain_call"] = f"ok: {(resp.text or '').strip()[:20]}"
    except Exception as exc:
        out["plain_call"] = f"{type(exc).__name__}: {_scrub(str(exc))}"
    try:
        p = _generate_structured("I paid $90 for dinner with Alex and Sam; Alex owes 50, I owe 25, Sam owes 15",
                                 EXPENSE_PROMPT.format(members="You, Alex, Sam", sender="You",
                                                       categories=", ".join(CATEGORIES)), ParsedExpense)
        out["structured_call"] = f"ok ({_schema_mode}): {p.split_type} {[(c.name, c.amount) for c in p.custom_shares]}"
    except Exception as exc:
        out["structured_call"] = "failed"
        out["structured_errors"] = list(_last_ai_errors) or [f"{type(exc).__name__}: {_scrub(str(exc))}"]
    out["model_in_use"] = current_model()
    out["mode"] = ai_mode()
    out["ok"] = out["plain_call"].startswith("ok") and out["structured_call"].startswith("ok")
    if not out["plain_call"].startswith("ok"):
        try:
            names = [m.name for m in itertools.islice(_client().models.list(), 200)]
            out["available_flash_models"] = sorted(n.removeprefix("models/") for n in names if "flash" in n)[:15]
        except Exception as exc:
            out["models_error"] = f"{type(exc).__name__}: {_scrub(str(exc))}"
    return out
