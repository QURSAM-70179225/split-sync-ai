"""Settlement service: validate a debt payment and create its PayPal (or demo) order.

Shared by the manual "Settle via PayPal" button and the Settle-Up Agent.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

import paypal_client
from config import get_settings
from ledger import compute_balances
from models import Group, Settlement, User


def outstanding_debt(db: Session, group: Group, debtor_id: int, creditor_id: int, currency: str) -> float:
    return next(
        (d.amount for d in compute_balances(db, group).debts
         if d.from_user.id == debtor_id and d.to_user.id == creditor_id and d.currency == currency),
        0.0,
    )


def start_settlement(db: Session, group: Group, debtor: User, creditor: User, amount: float,
                     currency: str, *, commit: bool = True) -> tuple[Settlement, str, str]:
    """Create a Settlement + PayPal order. Returns (settlement, approval_url, mode)."""
    s = get_settings()
    currency = currency.upper()
    if debtor.id == creditor.id:
        raise HTTPException(422, "Cannot settle a debt with yourself")
    outstanding = outstanding_debt(db, group, debtor.id, creditor.id, currency)
    if outstanding <= 0:
        raise HTTPException(422, "There is no outstanding debt between these members")
    if amount - outstanding > 0.01:
        raise HTTPException(422, f"Amount exceeds outstanding debt ({outstanding:.2f} {currency})")

    settlement = Settlement(group_id=group.id, from_user_id=debtor.id, to_user_id=creditor.id,
                            amount=round(amount, 2), currency=currency)
    db.add(settlement)
    db.flush()

    base, mode = s.public_url, s.effective_paypal_mode
    if mode == "demo":
        order_id = f"DEMO-{uuid.uuid4().hex[:16].upper()}"
        approval_url = f"{base}/?paypal=demo&settlement_id={settlement.id}&token={order_id}"
    else:
        try:
            order = paypal_client.create_paypal_order(
                settlement.amount, currency, f"SplitSync: {debtor.name} -> {creditor.name} ({group.name})",
                reference_id=f"settlement-{settlement.id}",
                payee_email=creditor.email if s.paypal_use_payee_email else None,
                return_url=f"{base}/?paypal=success&settlement_id={settlement.id}",
                cancel_url=f"{base}/?paypal=cancel&settlement_id={settlement.id}",
            )
        except paypal_client.PayPalError:
            db.rollback()
            raise
        order_id, approval_url = order["order_id"], order["approval_url"]

    settlement.paypal_order_id = order_id
    if commit:
        db.commit()
        db.refresh(settlement)
    return settlement, approval_url, mode
