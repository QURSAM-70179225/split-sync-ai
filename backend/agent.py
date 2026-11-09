"""Settle-Up Agent: turns "settle everything for me" into a concrete, confirmable payment plan.

The AI only classifies *what the user wants* (intent + which people). Every amount in the
plan comes from the ledger's simplified debts, computed in code, and the agent can only
pay debts owed BY the person it acts for. Nothing moves until the user confirms.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from ai_parser import _ai_structured, _scrub, ai_mode
from config import get_settings
from ledger import compute_balances
from models import Group, User
from schemas import AgentAction, AgentPlanOut, UserOut

log = logging.getLogger("splitsync.agent")

Intent = Literal["pay_my_debts", "pay_specific", "collect", "settle_all", "unknown"]


class AgentIntent(BaseModel):
    """Strict schema the AI fills in for an agent command."""

    intent: Intent = Field(description=(
        "pay_my_debts: pay everything the user owes; pay_specific: pay only the named people; "
        "collect: remind people who owe the user; settle_all: pay what the user owes AND remind "
        "people who owe them; unknown: anything else"))
    people: list[str] = Field(default_factory=list, description="Group members named in the command")


INTENT_PROMPT = """You are the Settle-Up Agent of SplitSync AI, an expense-splitting app.
Classify the user's command. Group members: {members}. The user is "{sender}" ("I", "me", "my").
Return JSON only. Only fill "people" with members the user explicitly named (not the user)."""

_COLLECT = re.compile(r"\b(remind|nudge|collect|chase|who owes me|owed to me|get paid|ask .* to pay)\b", re.I)
_PAY = re.compile(r"\b(pay|settle|clear|square up|pay back|pay off|reimburse)\b", re.I)
_ALL = re.compile(r"\b(everything|everyone|all|whole|every debt|square)\b", re.I)


def _offline_intent(text: str, members: list[str], sender: str) -> AgentIntent:
    people = [m for m in members if m != sender and re.search(rf"\b{re.escape(m)}\b", text, re.I)]
    collect, pay = bool(_COLLECT.search(text)), bool(_PAY.search(text))
    if collect and pay:
        intent = "settle_all"
    elif collect:
        intent = "collect"
    elif pay:
        intent = "pay_specific" if people and not _ALL.search(text) else (
            "settle_all" if re.search(r"\bsettle (everything|all|up)\b", text, re.I) else "pay_my_debts")
    else:
        intent = "unknown"
    return AgentIntent(intent=intent, people=people)


def understand(text: str, members: list[str], sender: str) -> tuple[AgentIntent, str]:
    """Return (intent, mode). AI first; deterministic keyword fallback."""
    if get_settings().ai_enabled:
        try:
            parsed = _ai_structured(text, INTENT_PROMPT.format(members=", ".join(members), sender=sender), AgentIntent)
            return parsed, getattr(parsed, "_source", ai_mode())
        except Exception as exc:  # noqa: BLE001 - any AI failure falls back
            log.warning("Agent intent via AI failed, using keywords: %s", _scrub(str(exc)))
    return _offline_intent(text, members, sender), "offline"


def _money(v: float, cur: str) -> str:
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥"}.get(cur)
    return f"{sym}{v:,.2f}" if sym else f"{v:,.2f} {cur}"


def build_plan(db, group: Group, me: User, intent: AgentIntent, mode: str) -> AgentPlanOut:
    """Deterministic plan from the ledger: amounts never come from the model."""
    debts = compute_balances(db, group).debts
    named = {p.strip().lower() for p in intent.people}

    def is_named(u) -> bool:
        return u.name.lower() in named or u.name.lower().split()[0] in named

    pays = [d for d in debts if d.from_user.id == me.id]
    if intent.intent == "pay_specific":
        pays = [d for d in pays if is_named(d.to_user)]
    owed = [d for d in debts if d.to_user.id == me.id]
    if intent.intent == "collect" and named:
        owed = [d for d in owed if is_named(d.from_user)]

    actions: list[AgentAction] = []
    if intent.intent in ("pay_my_debts", "pay_specific", "settle_all"):
        actions += [AgentAction(kind="pay", from_user=d.from_user, to_user=d.to_user, amount=d.amount,
                                currency=d.currency) for d in pays]
    if intent.intent in ("collect", "settle_all"):
        actions += [AgentAction(kind="nudge", from_user=d.from_user, to_user=d.to_user, amount=d.amount,
                                currency=d.currency) for d in owed]

    n_pay = sum(a.kind == "pay" for a in actions)
    n_nudge = len(actions) - n_pay
    if intent.intent == "unknown":
        summary = ("I can settle your debts with PayPal or remind people who owe you. "
                   "Try “Settle everything for me”, “Pay back Sarah” or “Remind everyone who owes me”.")
    elif not actions:
        summary = ("You're all square. There's nothing for me to pay or collect. 🎉"
                   if intent.intent == "settle_all" else
                   "You don't owe anyone right now. 🎉" if intent.intent != "collect" else
                   "Nobody owes you anything right now.")
    else:
        parts = []
        if n_pay:
            total = ", ".join(_money(a.amount, a.currency) + f" to {a.to_user.name}" for a in actions if a.kind == "pay")
            parts.append(f"pay {n_pay} debt{'s' if n_pay > 1 else ''} with PayPal ({total})")
        if n_nudge:
            who = ", ".join(a.from_user.name for a in actions if a.kind == "nudge")
            parts.append(f"send a friendly reminder to {who}")
        summary = "Here's my plan: I'll " + " and ".join(parts) + ". Nothing happens until you confirm."
    return AgentPlanOut(intent=intent.intent, summary=summary, actions=actions, ai_mode=mode,
                        acting_for=UserOut.model_validate(me))
