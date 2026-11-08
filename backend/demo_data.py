"""One-click realistic demo group for judges / first-time users (no AI calls needed)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ledger import add_member, split_equal
from models import Expense, ExpenseSplit, Group

MEMBERS = [("You", None), ("Alex", None), ("Sarah", None), ("Jordan", None)]

# (days_ago, hour, payer, amount, description, category, participants or None=all, raw_text)
EXPENSES = [
    (4, 10, "You", 412.00, "Villa Deposit", "lodging", None, "I paid $412 for the villa deposit, split between everyone"),
    (4, 15, "Alex", 64.80, "Airport Taxi", "transport", None, "Alex paid $64.80 for the airport taxi for all of us"),
    (3, 20, "Sarah", 138.50, "Seafood Dinner", "food", None, "Sarah covered $138.50 for the seafood dinner, split 4 ways"),
    (3, 23, "Jordan", 42.00, "Beach Bar", "food", ["Jordan", "Alex", "Sarah"], "Jordan paid 42 for drinks with Alex and Sarah"),
    (2, 9, "You", 96.00, "Surf Lessons", "entertainment", ["You", "Sarah"], "I paid $96 for surf lessons with Sarah"),
    (2, 13, "Alex", 57.25, "Groceries", "groceries", None, "Alex got groceries for $57.25 for everyone"),
    (1, 11, "Jordan", 180.00, "Scooter Rental", "transport", None, "Jordan paid $180 for scooter rental for the group"),
    (1, 19, "Sarah", 74.40, "Sunset Cruise", "entertainment", ["Sarah", "Alex", "You"], "Sarah paid 74.40 for the sunset cruise with Alex and me"),
    (0, 9, "You", 31.60, "Brunch", "food", ["You", "Jordan"], "I paid $31.60 for brunch with Jordan"),
]


def seed_demo_group(db: Session) -> Group:
    group = Group(name="Bali Trip 🌴")
    db.add(group)
    db.flush()
    users = {name: add_member(db, group, name, email) for name, email in MEMBERS}
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    for days, hour, payer, amount, desc, cat, parts, raw in EXPENSES:
        people = [users[p] for p in (parts or users)]
        e = Expense(
            group_id=group.id, payer_id=users[payer].id, amount=amount, currency="USD", description=desc,
            category=cat, source="demo", raw_text=raw,
            created_at=min((now - timedelta(days=days)).replace(hour=hour), now),
        )
        db.add(e)
        db.flush()
        for u, owed in zip(people, split_equal(amount, len(people)), strict=True):
            db.add(ExpenseSplit(expense_id=e.id, user_id=u.id, owed_amount=owed,
                                status="paid" if u.id == users[payer].id else "pending"))
    db.commit()
    return group
