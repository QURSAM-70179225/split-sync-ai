"""SplitSync AI — FastAPI application."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import paypal_client
from ai_parser import ExpenseParseError, ai_mode, parse_expense_prompt
from config import get_settings
from database import get_db, init_db
from models import Expense, ExpenseSplit, Group, GroupMember, Settlement, User
from schemas import (
    BalancesOut,
    CaptureRequest,
    Debt,
    ExpenseOut,
    ExpenseParseRequest,
    ExpenseParseResponse,
    GroupCreate,
    GroupOut,
    MemberBalance,
    MemberIn,
    ParsedExpense,
    SettlementOut,
    SettlementPayRequest,
    SettlementPayResponse,
    UserOut,
)

logging.basicConfig(level=logging.INFO)
settings = get_settings()
EPS = 0.005


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SplitSync AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(paypal_client.PayPalError)
async def paypal_error_handler(_req, exc: paypal_client.PayPalError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "paypal": exc.details})


# ---------------------------------------------------------------- helpers
def _get_group(db: Session, group_id: int) -> Group:
    group = db.scalar(
        select(Group)
        .where(Group.id == group_id)
        .options(selectinload(Group.memberships).selectinload(GroupMember.user))
    )
    if not group:
        raise HTTPException(404, "Group not found")
    return group


def _add_member(db: Session, group: Group, name: str, email: str | None = None) -> User:
    user = User(name=name.strip(), email=(email or None))
    db.add(user)
    db.flush()
    group.memberships.append(GroupMember(group_id=group.id, user_id=user.id, user=user))
    return user


def _resolve_member(name: str, members: list[User]) -> User | None:
    n = name.strip().lower()
    for u in members:
        if u.name.lower() == n:
            return u
    for u in members:  # first-name match ("Sarah" -> "Sarah Lee")
        if u.name.lower().split()[0] == n.split()[0]:
            return u
    return None


def _split_equal(total: float, n: int) -> list[float]:
    cents = round(total * 100)
    base, remainder = divmod(cents, n)
    return [(base + (1 if i < remainder else 0)) / 100 for i in range(n)]


def _load_expense(db: Session, expense_id: int) -> Expense:
    return db.scalar(
        select(Expense)
        .where(Expense.id == expense_id)
        .options(selectinload(Expense.splits).selectinload(ExpenseSplit.user), selectinload(Expense.payer))
    )


# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_mode": ai_mode(),
        "paypal_configured": paypal_client.is_configured(),
        "paypal_env": "sandbox" if "sandbox" in settings.paypal_base_url else "live",
    }


# ---------------------------------------------------------------- groups
@app.post("/api/groups", response_model=GroupOut, status_code=201)
def create_group(payload: GroupCreate, db: Session = Depends(get_db)):
    names = [m.name.lower() for m in payload.members]
    if len(names) != len(set(names)):
        raise HTTPException(422, "Member names must be unique within a group")
    group = Group(name=payload.name.strip())
    db.add(group)
    db.flush()
    for m in payload.members:
        _add_member(db, group, m.name, m.email)
    db.commit()
    return _get_group(db, group.id)


@app.get("/api/groups", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db)):
    return db.scalars(
        select(Group)
        .options(selectinload(Group.memberships).selectinload(GroupMember.user))
        .order_by(Group.created_at.desc())
    ).all()


@app.get("/api/groups/{group_id}", response_model=GroupOut)
def get_group(group_id: int, db: Session = Depends(get_db)):
    return _get_group(db, group_id)


@app.post("/api/groups/{group_id}/members", response_model=UserOut, status_code=201)
def add_member(group_id: int, payload: MemberIn, db: Session = Depends(get_db)):
    group = _get_group(db, group_id)
    if any(u.name.lower() == payload.name.lower() for u in group.members):
        raise HTTPException(409, "A member with that name already exists")
    user = _add_member(db, group, payload.name, payload.email)
    db.commit()
    return user


@app.delete("/api/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    db.delete(_get_group(db, group_id))
    db.commit()


# ---------------------------------------------------------------- expenses
@app.post("/api/groups/{group_id}/expenses/parse", response_model=ExpenseParseResponse, status_code=201)
def parse_and_save_expense(group_id: int, payload: ExpenseParseRequest, db: Session = Depends(get_db)):
    group = _get_group(db, group_id)
    members = group.members
    sender = next((u for u in members if u.id == payload.sender_id), None) if payload.sender_id else None
    if payload.sender_id and not sender:
        raise HTTPException(422, "sender_id is not a member of this group")

    try:
        parsed: ParsedExpense = parse_expense_prompt(
            payload.text, [u.name for u in members], sender.name if sender else None
        )
    except ExpenseParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    new_members: list[User] = []

    def resolve_or_create(name: str) -> User:
        user = _resolve_member(name, group.members)
        if not user:
            user = _add_member(db, group, name.strip().title())
            new_members.append(user)
        return user

    payer = resolve_or_create(parsed.payer_name)
    participants: list[User] = []
    for name in parsed.participants:
        u = resolve_or_create(name)
        if u not in participants:
            participants.append(u)

    total = round(parsed.total_amount, 2)
    if parsed.split_type == "custom" and parsed.custom_shares:
        shares: dict[int, float] = defaultdict(float)
        for cs in parsed.custom_shares:
            u = resolve_or_create(cs.name)
            shares[u.id] += round(cs.amount, 2)
            if u not in participants:
                participants.append(u)
        if abs(sum(shares.values()) - total) > 0.02:
            raise HTTPException(
                422, f"Custom shares add up to {sum(shares.values()):.2f}, but the total is {total:.2f}."
            )
        amounts = [(u, shares.get(u.id, 0.0)) for u in participants]
    else:
        parsed.split_type = "equal"
        amounts = list(zip(participants, _split_equal(total, len(participants))))

    expense = Expense(
        group_id=group.id,
        payer_id=payer.id,
        amount=total,
        currency=parsed.currency,
        description=parsed.description.strip()[:255] or "Shared Expense",
        raw_text=payload.text,
    )
    db.add(expense)
    db.flush()
    for user, owed in amounts:
        if owed <= 0:
            continue
        db.add(
            ExpenseSplit(
                expense_id=expense.id,
                user_id=user.id,
                owed_amount=owed,
                # The payer's own share is never "owed" to anyone
                status="paid" if user.id == payer.id else "pending",
            )
        )
    db.commit()

    parsed.payer_name = payer.name
    parsed.participants = [u.name for u in participants]
    return ExpenseParseResponse(
        expense=_load_expense(db, expense.id),
        parsed=parsed,
        new_members=[UserOut.model_validate(u) for u in new_members],
        ai_mode=ai_mode(),
    )


@app.get("/api/groups/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(group_id: int, db: Session = Depends(get_db)):
    _get_group(db, group_id)
    return db.scalars(
        select(Expense)
        .where(Expense.group_id == group_id)
        .options(selectinload(Expense.splits).selectinload(ExpenseSplit.user), selectinload(Expense.payer))
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    ).all()


@app.delete("/api/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(404, "Expense not found")
    db.delete(expense)
    db.commit()


# ---------------------------------------------------------------- balances
def _compute_balances(db: Session, group: Group) -> BalancesOut:
    expenses = db.scalars(
        select(Expense).where(Expense.group_id == group.id).options(selectinload(Expense.splits))
    ).all()
    settlements = db.scalars(
        select(Settlement).where(Settlement.group_id == group.id, Settlement.status == "completed")
    ).all()

    # net[currency][user_id]: positive => others owe them
    net: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for e in expenses:
        for s in e.splits:
            if s.user_id != e.payer_id:
                net[e.currency][e.payer_id] += s.owed_amount
                net[e.currency][s.user_id] -= s.owed_amount
    for st in settlements:
        net[st.currency][st.from_user_id] += st.amount
        net[st.currency][st.to_user_id] -= st.amount

    users = {u.id: u for u in group.members}
    for s in settlements:  # members could theoretically have been removed
        users.setdefault(s.from_user_id, s.from_user)
        users.setdefault(s.to_user_id, s.to_user)

    primary = Counter(e.currency for e in expenses).most_common(1)[0][0] if expenses else "USD"

    # Greedy debt simplification per currency: largest debtor pays largest creditor.
    debts: list[Debt] = []
    for currency, balances in net.items():
        creditors = sorted([[uid, b] for uid, b in balances.items() if b > EPS], key=lambda x: -x[1])
        debtors = sorted([[uid, -b] for uid, b in balances.items() if b < -EPS], key=lambda x: -x[1])
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            pay = round(min(debtors[i][1], creditors[j][1]), 2)
            if pay > EPS:
                debts.append(
                    Debt(
                        from_user=UserOut.model_validate(users[debtors[i][0]]),
                        to_user=UserOut.model_validate(users[creditors[j][0]]),
                        amount=pay,
                        currency=currency,
                    )
                )
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
    return BalancesOut(group_id=group.id, currency=primary, members=members, debts=debts)


@app.get("/api/groups/{group_id}/balances", response_model=BalancesOut)
def get_balances(group_id: int, db: Session = Depends(get_db)):
    return _compute_balances(db, _get_group(db, group_id))


# ---------------------------------------------------------------- settlements
@app.post("/api/settlements/pay", response_model=SettlementPayResponse, status_code=201)
def pay_settlement(payload: SettlementPayRequest, db: Session = Depends(get_db)):
    group = _get_group(db, payload.group_id)
    ids = {u.id: u for u in group.members}
    if payload.from_user_id not in ids or payload.to_user_id not in ids:
        raise HTTPException(422, "Both users must be members of the group")
    if payload.from_user_id == payload.to_user_id:
        raise HTTPException(422, "Cannot settle a debt with yourself")

    currency = payload.currency.upper()
    outstanding = next(
        (
            d.amount
            for d in _compute_balances(db, group).debts
            if d.from_user.id == payload.from_user_id
            and d.to_user.id == payload.to_user_id
            and d.currency == currency
        ),
        0.0,
    )
    if payload.amount - outstanding > 0.01:
        raise HTTPException(422, f"Amount exceeds outstanding debt ({outstanding:.2f} {currency})")

    debtor, creditor = ids[payload.from_user_id], ids[payload.to_user_id]
    settlement = Settlement(
        group_id=group.id,
        from_user_id=debtor.id,
        to_user_id=creditor.id,
        amount=round(payload.amount, 2),
        currency=currency,
    )
    db.add(settlement)
    db.flush()

    base = settings.frontend_url.rstrip("/")
    try:
        order = paypal_client.create_paypal_order(
            settlement.amount,
            currency,
            f"SplitSync: {debtor.name} -> {creditor.name} ({group.name})",
            reference_id=f"settlement-{settlement.id}",
            payee_email=creditor.email if settings.paypal_use_payee_email else None,
            return_url=f"{base}/?paypal=success&settlement_id={settlement.id}",
            cancel_url=f"{base}/?paypal=cancel&settlement_id={settlement.id}",
        )
    except paypal_client.PayPalError:
        db.rollback()
        raise

    settlement.paypal_order_id = order["order_id"]
    db.commit()
    db.refresh(settlement)
    return SettlementPayResponse(settlement=settlement, approval_url=order["approval_url"])


def _mark_splits_paid(db: Session, st: Settlement) -> None:
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


@app.post("/api/settlements/{settlement_id}/capture", response_model=SettlementOut)
def capture_settlement(settlement_id: int, payload: CaptureRequest | None = None, db: Session = Depends(get_db)):
    st = db.get(Settlement, settlement_id)
    if not st:
        raise HTTPException(404, "Settlement not found")
    if payload and payload.order_id and payload.order_id != st.paypal_order_id:
        raise HTTPException(422, "Order ID does not match this settlement")
    if st.status == "completed":
        return st
    if not st.paypal_order_id:
        raise HTTPException(409, "Settlement has no PayPal order")

    result = paypal_client.capture_paypal_order(st.paypal_order_id)
    if result.get("status") != "COMPLETED":
        st.status = "failed"
        db.commit()
        raise HTTPException(402, f"PayPal capture status: {result.get('status')}")

    st.status = "completed"
    st.completed_at = datetime.now(timezone.utc)
    _mark_splits_paid(db, st)
    db.commit()
    db.refresh(st)
    return st


@app.post("/api/settlements/{settlement_id}/cancel", response_model=SettlementOut)
def cancel_settlement(settlement_id: int, db: Session = Depends(get_db)):
    st = db.get(Settlement, settlement_id)
    if not st:
        raise HTTPException(404, "Settlement not found")
    if st.status == "created":
        st.status = "cancelled"
        db.commit()
        db.refresh(st)
    return st


@app.get("/api/groups/{group_id}/settlements", response_model=list[SettlementOut])
def list_settlements(group_id: int, db: Session = Depends(get_db)):
    _get_group(db, group_id)
    return db.scalars(
        select(Settlement).where(Settlement.group_id == group_id).order_by(Settlement.created_at.desc())
    ).all()
