"""Group analytics and the compact ledger context fed to the AI copilot."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger import compute_balances, load_expenses
from models import Group, Settlement
from schemas import CategoryStat, DailyStat, ExpenseOut, InsightsOut, PersonStat, UserOut

CATEGORY_LABEL = {
    "food": "Food & drinks", "groceries": "Groceries", "transport": "Transport", "lodging": "Lodging",
    "entertainment": "Entertainment", "shopping": "Shopping", "utilities": "Utilities",
    "travel": "Travel", "health": "Health", "other": "Other",
}


def _money(v: float, cur: str) -> str:
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥"}.get(cur)
    return f"{sym}{v:,.2f}" if sym else f"{v:,.2f} {cur}"


def compute_insights(db: Session, group: Group) -> InsightsOut:
    balances = compute_balances(db, group)
    cur = balances.currency
    expenses = [e for e in load_expenses(db, group.id) if e.currency == cur]
    settlements = db.scalars(select(Settlement).where(Settlement.group_id == group.id)).all()

    total = round(sum(e.amount for e in expenses), 2)
    by_cat: dict[str, list[float]] = defaultdict(list)
    paid: dict[int, float] = defaultdict(float)
    share: dict[int, float] = defaultdict(float)
    daily: dict[str, float] = defaultdict(float)
    for e in expenses:
        by_cat[e.category or "other"].append(e.amount)
        paid[e.payer_id] += e.amount
        daily[e.created_at.date().isoformat()] += e.amount
        for s in e.splits:
            share[s.user_id] += s.owed_amount

    cats = sorted(
        (CategoryStat(category=c, total=round(sum(v), 2), count=len(v)) for c, v in by_cat.items()),
        key=lambda c: -c.total,
    )
    people = sorted(
        (PersonStat(user=UserOut.model_validate(u), paid=round(paid[u.id], 2), share=round(share[u.id], 2))
         for u in group.members),
        key=lambda p: -p.paid,
    )
    largest = max(expenses, key=lambda e: e.amount, default=None)
    settled = round(sum(s.amount for s in settlements if s.status == "completed" and s.currency == cur), 2)
    outstanding = round(sum(d.amount for d in balances.debts if d.currency == cur), 2)
    saved = max(balances.naive_transfer_count - len(balances.debts), 0)

    highlights: list[str] = []
    if expenses:
        if cats:
            top = cats[0]
            highlights.append(f"{CATEGORY_LABEL.get(top.category, top.category)} is your biggest spend at "
                              f"{_money(top.total, cur)} ({round(top.total / total * 100)}% of the total).")
        if people and people[0].paid > 0:
            p = people[0]
            verb = "are" if p.user.name.lower() == "you" else "is"
            highlights.append(f"{p.user.name} {verb} carrying the group, fronting {_money(p.paid, cur)} so far.")
        if saved:
            highlights.append(f"Smart settlement cuts {saved} payment{'s' if saved != 1 else ''} — "
                              f"only {len(balances.debts)} needed to clear every debt.")
        if not balances.debts:
            highlights.append("Everyone is fully settled up. 🎉")
        elif settled:
            pct = round(settled / (settled + outstanding) * 100)
            highlights.append(f"{pct}% of debts already settled via PayPal.")

    return InsightsOut(
        currency=cur,
        total_spent=total,
        expense_count=len(expenses),
        avg_expense=round(total / len(expenses), 2) if expenses else 0.0,
        largest_expense=ExpenseOut.from_model(largest) if largest else None,
        by_category=cats,
        by_person=people,
        daily=[DailyStat(date=d, total=round(v, 2)) for d, v in sorted(daily.items())],
        settled_amount=settled,
        outstanding_amount=outstanding,
        payments_saved=saved,
        highlights=highlights,
    )


def ledger_context(db: Session, group: Group) -> dict:
    """Compact JSON the AI copilot answers questions from."""
    ins = compute_insights(db, group)
    bal = compute_balances(db, group)
    expenses = load_expenses(db, group.id)[:150]
    return {
        "group": group.name,
        "currency": ins.currency,
        "members": [u.name for u in group.members],
        "total_spent": ins.total_spent,
        "expense_count": ins.expense_count,
        "by_category": [c.model_dump() for c in ins.by_category],
        "by_person": [{"name": p.user.name, "paid": p.paid, "share": p.share} for p in ins.by_person],
        "debts": [{"from": d.from_user.name, "to": d.to_user.name, "amount": d.amount} for d in bal.debts],
        "largest": ({"description": ins.largest_expense.description, "amount": ins.largest_expense.amount,
                     "payer": ins.largest_expense.payer.name} if ins.largest_expense else None),
        "expenses": [
            {"date": e.created_at.date().isoformat(), "description": e.description, "category": e.category,
             "amount": e.amount, "currency": e.currency, "payer": e.payer.name,
             "split": {s.user.name: s.owed_amount for s in e.splits}}
            for e in expenses
        ],
    }
