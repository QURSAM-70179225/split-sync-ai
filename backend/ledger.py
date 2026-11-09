"""Core money logic: member resolution, splitting, balances and debt simplification."""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import Expense, ExpenseSplit, Group, GroupMember, Settlement, User
from schemas import BalancesOut, Debt, MemberBalance, UserOut

EPS = 0.005


def get_group(db: Session, group_id: int) -> Group | None:
    return db.scalar(
        select(Group)
        .where(Group.id == group_id)
        .options(selectinload(Group.memberships).selectinload(GroupMember.user))
    )


def add_member(db: Session, group: Group, name: str, email: str | None = None) -> User:
    user = User(name=name.strip(), email=(email or None))
    db.add(user)
    db.flush()
    group.memberships.append(GroupMember(group_id=group.id, user_id=user.id, user=user))
    return user


def resolve_member(name: str, members: list[User]) -> User | None:
    n = name.strip().lower()
    if not n:
        return None
    for u in members:
        if u.name.lower() == n:
            return u
    for u in members:  # first-name match ("Sarah" -> "Sarah Lee")
        if u.name.lower().split()[0] == n.split()[0]:
            return u
    return None


def split_equal(total: float, n: int) -> list[float]:
    """Split in whole cents so shares always sum exactly to the total."""
    cents = round(total * 100)
    base, remainder = divmod(cents, n)
    return [(base + (1 if i < remainder else 0)) / 100 for i in range(n)]


def scale_to_total(shares: list[float], total: float) -> list[float]:
    """Proportionally scale shares so they sum to total (cent-exact). Used for receipts (tax/tip)."""
    s = sum(shares)
    if s <= 0:
        return split_equal(total, len(shares))
    cents = [round(x / s * total * 100) for x in shares]
    diff = round(total * 100) - sum(cents)
    cents[cents.index(max(cents))] += diff
    return [c / 100 for c in cents]


def load_expenses(db: Session, group_id: int) -> list[Expense]:
    return list(
        db.scalars(
            select(Expense)
            .where(Expense.group_id == group_id)
            .options(selectinload(Expense.splits).selectinload(ExpenseSplit.user), selectinload(Expense.payer))
            .order_by(Expense.created_at.desc(), Expense.id.desc())
        ).all()
    )


def completed_settlements(db: Session, group_id: int) -> list[Settlement]:
    return list(
        db.scalars(
            select(Settlement).where(Settlement.group_id == group_id, Settlement.status == "completed")
        ).all()
    )


def compute_balances(db: Session, group: Group) -> BalancesOut:
    expenses = load_expenses(db, group.id)
    settlements = completed_settlements(db, group.id)

    # net[currency][user_id]: positive => others owe them
    net: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    pair_debt: dict[tuple[str, int, int], float] = defaultdict(float)
    for e in expenses:
        for s in e.splits:
            if s.user_id != e.payer_id:
                net[e.currency][e.payer_id] += s.owed_amount
                net[e.currency][s.user_id] -= s.owed_amount
                pair_debt[(e.currency, s.user_id, e.payer_id)] += s.owed_amount
    for st in settlements:
        net[st.currency][st.from_user_id] += st.amount
        net[st.currency][st.to_user_id] -= st.amount
        pair_debt[(st.currency, st.to_user_id, st.from_user_id)] += st.amount

    # Payments needed if everyone paid back each person they owe directly (netting only pairs)
    naive = 0
    seen: set[tuple[str, int, int]] = set()
    for (cur, a, b), amt in pair_debt.items():
        if (cur, b, a) in seen or (cur, a, b) in seen:
            continue
        seen.add((cur, a, b))
        if abs(amt - pair_debt.get((cur, b, a), 0.0)) > EPS:
            naive += 1

    users = {u.id: u for u in group.members}
    for s in settlements:
        users.setdefault(s.from_user_id, s.from_user)
        users.setdefault(s.to_user_id, s.to_user)

    primary = Counter(e.currency for e in expenses).most_common(1)[0][0] if expenses else "USD"

    # Greedy simplification per currency: largest debtor pays largest creditor (≤ n-1 payments).
    debts: list[Debt] = []
    for currency, balances in net.items():
        creditors = sorted([[uid, b] for uid, b in balances.items() if b > EPS], key=lambda x: -x[1])
        debtors = sorted([[uid, -b] for uid, b in balances.items() if b < -EPS], key=lambda x: -x[1])
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            pay = round(min(debtors[i][1], creditors[j][1]), 2)
            if pay > EPS:
                debts.append(Debt(
                    from_user=UserOut.model_validate(users[debtors[i][0]]),
                    to_user=UserOut.model_validate(users[creditors[j][0]]),
                    amount=pay, currency=currency,
                ))
            debtors[i][1] -= pay
            creditors[j][1] -= pay
            if debtors[i][1] <= EPS:
                i += 1
            if creditors[j][1] <= EPS:
                j += 1

    members = [
        MemberBalance(user=UserOut.model_validate(u), net=round(net[primary].get(u.id, 0.0), 2))
        for u in group.members
    ]
    return BalancesOut(group_id=group.id, currency=primary, members=members, debts=debts,
                       naive_transfer_count=max(naive, len(debts)))


def mark_splits_paid(db: Session, st: Settlement) -> None:
    """Best-effort: mark the debtor's oldest pending splits owed to the creditor as paid."""
    remaining = st.amount
    splits = db.scalars(
        select(ExpenseSplit)
        .join(Expense)
        .where(
            Expense.group_id == st.group_id,
            Expense.payer_id == st.to_user_id,
            Expense.currency == st.currency,
            ExpenseSplit.user_id == st.from_user_id,
            ExpenseSplit.status == "pending",
        )
        .order_by(Expense.created_at, Expense.id)
    ).all()
    for s in splits:
        if remaining + EPS < s.owed_amount:
            break
        s.status = "paid"
        remaining -= s.owed_amount


def itemized_shares(items: list, participants: list[str], total: float) -> dict[str, float]:
    """Per-person shares for a receipt, computed in code (never trust LLM arithmetic).

    Each item goes to the people in its `assigned_to` (split equally), or to every participant
    when unassigned. Tax, tip and any rounding are spread proportionally to each person's
    subtotal by scaling to the printed total, cent-exact.
    """
    names = list(dict.fromkeys([*participants, *(n for it in items for n in it.assigned_to)]))
    subtotal = {n: 0.0 for n in names}
    for it in items:
        people = [n for n in it.assigned_to if n in subtotal] or list(participants) or names
        for n in people:
            subtotal[n] += it.price / len(people)
    names = [n for n in names if subtotal[n] > 0]
    return dict(zip(names, scale_to_total([subtotal[n] for n in names], total), strict=True))
