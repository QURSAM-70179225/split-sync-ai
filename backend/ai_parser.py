"""Natural-language expense parsing with Google Gemini structured output.

Falls back to a deterministic regex parser when no API key is configured
(or AI_OFFLINE_MODE=true) so the demo still works offline.
"""
from __future__ import annotations

import logging
import re

from config import get_settings
from schemas import ParsedExpense

log = logging.getLogger("splitsync.ai")

SYSTEM_PROMPT = """You are SplitSync AI, an expense-splitting assistant.
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
"""


class ExpenseParseError(ValueError):
    pass


def _gemini_parse(text: str, members: list[str], sender: str) -> ParsedExpense:
    from google import genai
    from google.genai import types

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(members=", ".join(members) or "(none)", sender=sender),
            response_mime_type="application/json",
            response_schema=ParsedExpense,
            temperature=0,
        ),
    )
    parsed = response.parsed
    if isinstance(parsed, ParsedExpense):
        return parsed
    if not response.text:
        raise ExpenseParseError("Gemini returned an empty response")
    return ParsedExpense.model_validate_json(response.text)


# ---------------- offline fallback ----------------
_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
_SELF_WORDS = {"i", "me", "my", "myself"}
_ALL_WORDS = ("everyone", "everybody", "all of us", "the group", "us all", "between us", "among us")


def _offline_parse(text: str, members: list[str], sender: str) -> ParsedExpense:
    lowered = text.lower()
    m = re.search(r"([$€£₹¥])\s?(\d+(?:[.,]\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s?(usd|eur|gbp|inr|dollars?|bucks)?", text, re.I)
    if not m:
        raise ExpenseParseError("Couldn't find an amount in that message.")
    if m.group(2):
        amount, currency = float(m.group(2).replace(",", ".")), _CURRENCY_SYMBOLS[m.group(1)]
    else:
        amount = float(m.group(3))
        code = (m.group(4) or "usd").lower()
        currency = {"eur": "EUR", "gbp": "GBP", "inr": "INR"}.get(code, "USD")

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    member_lookup = {n.lower(): n for n in members}
    mentioned: list[str] = []
    for w in words:
        lw = w.lower()
        name = sender if lw in _SELF_WORDS else member_lookup.get(lw)
        if name and name not in mentioned:
            mentioned.append(name)

    # payer: "<Name> paid" or "paid by <Name>", else sender
    payer = sender
    pm = re.search(r"\b([A-Za-z]+)\s+(?:paid|covered|bought|spent)\b", text, re.I) or re.search(
        r"\bpaid\s+by\s+([A-Za-z]+)", text, re.I
    )
    if pm:
        cand = pm.group(1).lower()
        payer = sender if cand in _SELF_WORDS else member_lookup.get(cand, payer)

    if any(w in lowered for w in _ALL_WORDS) or len(mentioned) <= 1 and "split" in lowered and "with" not in lowered:
        participants = list(members)
    else:
        participants = mentioned or list(members)
    if payer not in participants and ("with" in lowered or "and me" in lowered or not mentioned):
        participants.insert(0, payer)
    if not participants:
        participants = [payer]

    dm = re.search(r"\bfor\s+(?:the\s+|a\s+|an\s+|our\s+)?([A-Za-z][A-Za-z ]{1,30}?)(?:[,.]|\s+(?:split|with|between|and)\b|$)", text, re.I)
    description = dm.group(1).strip().title() if dm else "Shared Expense"

    return ParsedExpense(
        total_amount=round(amount, 2),
        currency=currency,
        description=description,
        payer_name=payer,
        split_type="equal",
        participants=participants,
    )


def ai_mode() -> str:
    s = get_settings()
    return "offline" if (s.ai_offline_mode or not s.gemini_api_key) else f"gemini:{s.gemini_model}"


def parse_expense_prompt(text: str, members: list[str], sender: str | None = None) -> ParsedExpense:
    """Turn free text into a validated ParsedExpense."""
    sender = sender or (members[0] if members else "Me")
    if ai_mode() == "offline":
        parsed = _offline_parse(text, members, sender)
    else:
        try:
            parsed = _gemini_parse(text, members, sender)
        except ExpenseParseError:
            raise
        except Exception as exc:  # network / quota / schema problems
            log.exception("Gemini parsing failed")
            raise ExpenseParseError(f"AI parsing failed: {exc}") from exc

    if parsed.total_amount <= 0:
        raise ExpenseParseError("The expense amount must be greater than zero.")
    if not parsed.participants:
        raise ExpenseParseError("Couldn't tell who should share this expense.")
    parsed.currency = (parsed.currency or "USD").upper()[:3]
    return parsed
