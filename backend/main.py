"""SplitSync AI — FastAPI application (routes only; logic lives in ledger/insights/ai_parser)."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import paypal_client
from ai_parser import (
    ExpenseParseError,
    ai_mode,
    answer_question,
    check_ai,
    parse_expense_prompt,
    parse_receipt,
    write_nudge,
)
from config import get_settings
from database import get_db, init_db
from demo_data import seed_demo_group
from events import broker
from insights import _money, compute_insights, ledger_context
from ledger import (
    add_member,
    compute_balances,
    get_group,
    load_expenses,
    mark_splits_paid,
    resolve_member,
    scale_to_total,
    split_equal,
)
from models import Expense, ExpenseSplit, Group, GroupMember, Settlement, User
from schemas import (
    AskRequest,
    AskResponse,
    BalancesOut,
    CaptureRequest,
    ExpenseOut,
    ExpenseParseRequest,
    ExpenseParseResponse,
    GroupCreate,
    GroupOut,
    InsightsOut,
    MemberIn,
    NudgeRequest,
    NudgeResponse,
    ParsedExpense,
    ParsedReceipt,
    SettlementOut,
    SettlementPayRequest,
    SettlementPayResponse,
    UserOut,
)

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("splitsync.api")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    broker.bind(asyncio.get_running_loop())
    if settings.seed_demo_on_start:
        from database import SessionLocal

        with SessionLocal() as db:
            if db.scalar(select(Group.id).limit(1)) is None:
                seed_demo_group(db)
                log.info("Seeded demo group")
    log.info("SplitSync AI ready · ai=%s · paypal=%s", ai_mode(), settings.effective_paypal_mode)
    yield


app = FastAPI(
    title="SplitSync AI",
    version="2.0.4",
    description="Conversational group expenses with Gemini AI and autonomous PayPal settlement.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    if request.url.path != "/api/health" and not request.url.path.endswith("/events"):
        log.info("%s %s -> %s (%.0fms) rid=%s", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000, rid)
    return response


@app.exception_handler(paypal_client.PayPalError)
async def paypal_error_handler(_req, exc: paypal_client.PayPalError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "paypal": exc.details})


@app.exception_handler(Exception)
async def unhandled_error(_req, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


# ---------------------------------------------------------------- helpers
def _group_or_404(db: Session, group_id: int) -> Group:
    group = get_group(db, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return group


def _load_expense(db: Session, expense_id: int) -> Expense:
    return db.scalar(
        select(Expense)
        .where(Expense.id == expense_id)
        .options(selectinload(Expense.splits).selectinload(ExpenseSplit.user), selectinload(Expense.payer))
    )


def _sender(group: Group, sender_id: int | None) -> User | None:
    if sender_id is None:
        return None
    sender = next((u for u in group.members if u.id == sender_id), None)
    if not sender:
        raise HTTPException(422, "sender_id is not a member of this group")
    return sender


def _save_expense(
    db: Session, group: Group, parsed: ParsedExpense, raw_text: str, source: str, *,
    items: list | None = None, scale_custom: bool = False,
) -> tuple[Expense, list[User], list[str]]:
    """Resolve names, compute splits, persist. Shared by chat, voice and receipt flows."""
    new_members: list[User] = []
    notes: list[str] = []

    def resolve_or_create(name: str) -> User:
        user = resolve_member(name, group.members)
        if not user:
            user = add_member(db, group, name.strip().title())
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
        values = [shares.get(u.id, 0.0) for u in participants]
        if abs(sum(values) - total) > 0.02:
            if not scale_custom:
                raise HTTPException(422, f"Custom shares add up to {sum(values):.2f}, but the total is {total:.2f}.")
            notes.append("Shares were adjusted proportionally to match the receipt total (tax & tip).")
            values = scale_to_total(values, total)
        amounts = list(zip(participants, values, strict=True))
    else:
        parsed.split_type = "equal"
        amounts = list(zip(participants, split_equal(total, len(participants)), strict=True))

    expense = Expense(
        group_id=group.id, payer_id=payer.id, amount=total, currency=parsed.currency,
        description=parsed.description.strip()[:255] or "Shared Expense",
        category=parsed.category, source=source, raw_text=raw_text,
        items_json=json.dumps([i.model_dump() for i in items]) if items else None,
    )
    db.add(expense)
    db.flush()
    for user, owed in amounts:
        if owed > 0:
            db.add(ExpenseSplit(expense_id=expense.id, user_id=user.id, owed_amount=owed,
                                status="paid" if user.id == payer.id else "pending"))
    db.commit()
    parsed.payer_name = payer.name
    parsed.participants = [u.name for u in participants]
    return expense, new_members, notes


def _parse_response(db, expense, parsed, new_members, notes) -> ExpenseParseResponse:
    if parsed._fallback_reason:
        notes = [*notes, "Gemini was unavailable, so the offline parser handled this one. Check the server logs."]
    return ExpenseParseResponse(
        expense=ExpenseOut.from_model(_load_expense(db, expense.id)),
        parsed=ParsedExpense.model_validate(parsed.model_dump(include=set(ParsedExpense.model_fields))),
        new_members=[UserOut.model_validate(u) for u in new_members],
        ai_mode=parsed._source,
        notes=notes,
    )


# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": app.version,
        "ai_mode": ai_mode(),
        "paypal_configured": paypal_client.is_configured(),
        "paypal_mode": settings.effective_paypal_mode,
        "paypal_env": "sandbox" if "sandbox" in settings.paypal_base_url else "live",
    }


@app.get("/api/health/ai")
async def health_ai():
    """Live Gemini check: makes one tiny request and lists usable flash models. Never exposes the key."""
    return await asyncio.to_thread(check_ai)


@app.post("/api/demo/seed", response_model=GroupOut, status_code=201)
def seed_demo(db: Session = Depends(get_db)):
    return _group_or_404(db, seed_demo_group(db).id)


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
        add_member(db, group, m.name, m.email)
    db.commit()
    return _group_or_404(db, group.id)


@app.get("/api/groups", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db)):
    return db.scalars(
        select(Group)
        .options(selectinload(Group.memberships).selectinload(GroupMember.user))
        .order_by(Group.created_at.desc())
    ).all()


@app.get("/api/groups/{group_id}", response_model=GroupOut)
def read_group(group_id: int, db: Session = Depends(get_db)):
    return _group_or_404(db, group_id)


@app.post("/api/groups/{group_id}/members", response_model=UserOut, status_code=201)
def create_member(group_id: int, payload: MemberIn, db: Session = Depends(get_db)):
    group = _group_or_404(db, group_id)
    if any(u.name.lower() == payload.name.lower() for u in group.members):
        raise HTTPException(409, "A member with that name already exists")
    user = add_member(db, group, payload.name, payload.email)
    db.commit()
    broker.publish(group_id, "member.added", {"name": user.name})
    return user


@app.delete("/api/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    db.delete(_group_or_404(db, group_id))
    db.commit()
    broker.publish(group_id, "group.deleted")


# ---------------------------------------------------------------- expenses
@app.post("/api/groups/{group_id}/expenses/parse", response_model=ExpenseParseResponse, status_code=201)
def parse_and_save_expense(group_id: int, payload: ExpenseParseRequest, db: Session = Depends(get_db)):
    group = _group_or_404(db, group_id)
    sender = _sender(group, payload.sender_id)
    try:
        parsed = parse_expense_prompt(payload.text, [u.name for u in group.members], sender.name if sender else None)
    except ExpenseParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    expense, new_members, notes = _save_expense(db, group, parsed, payload.text, payload.source)
    broker.publish(group_id, "expense.created", {"description": expense.description, "by": sender.name if sender else None})
    return _parse_response(db, expense, parsed, new_members, notes)


@app.post("/api/groups/{group_id}/expenses/receipt", response_model=ExpenseParseResponse, status_code=201)
async def scan_receipt(
    group_id: int,
    file: UploadFile = File(...),
    note: str = Form(""),
    sender_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    group = _group_or_404(db, group_id)
    sender = _sender(group, sender_id)
    if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG, WEBP or HEIC photo of the receipt.")
    data = await file.read()
    if len(data) > settings.max_receipt_mb * 1024 * 1024:
        raise HTTPException(413, f"Receipt image must be under {settings.max_receipt_mb} MB.")
    members = [u.name for u in group.members]
    try:
        parsed: ParsedReceipt = await asyncio.to_thread(
            parse_receipt, data, file.content_type, members, sender.name if sender else members[0], note[:500]
        )
    except ExpenseParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    raw = f"📷 Receipt{f' from {parsed.merchant}' if parsed.merchant else ''}" + (f" — “{note}”" if note else "")
    expense, new_members, notes = await asyncio.to_thread(
        _save_expense, db, group, parsed, raw, "receipt", items=parsed.items, scale_custom=True
    )
    broker.publish(group_id, "expense.created", {"description": expense.description, "by": sender.name if sender else None})
    return _parse_response(db, expense, parsed, new_members, notes)


@app.get("/api/groups/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(group_id: int, db: Session = Depends(get_db)):
    _group_or_404(db, group_id)
    return [ExpenseOut.from_model(e) for e in load_expenses(db, group_id)]


@app.delete("/api/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(404, "Expense not found")
    gid = expense.group_id
    db.delete(expense)
    db.commit()
    broker.publish(gid, "expense.deleted")


@app.get("/api/groups/{group_id}/export.csv")
def export_csv(group_id: int, db: Session = Depends(get_db)):
    group = _group_or_404(db, group_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "description", "category", "amount", "currency", "paid_by", "participant", "share", "status", "source"])
    for e in reversed(load_expenses(db, group_id)):
        for s in e.splits:
            w.writerow([e.created_at.isoformat(), e.description, e.category, f"{e.amount:.2f}", e.currency,
                        e.payer.name, s.user.name, f"{s.owed_amount:.2f}", s.status, e.source])
    filename = "".join(c if c.isalnum() else "-" for c in group.name).strip("-").lower() or "group"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="splitsync-{filename}.csv"'},
    )


# ---------------------------------------------------------------- balances & insights
@app.get("/api/groups/{group_id}/balances", response_model=BalancesOut)
def get_balances(group_id: int, db: Session = Depends(get_db)):
    return compute_balances(db, _group_or_404(db, group_id))


@app.get("/api/groups/{group_id}/insights", response_model=InsightsOut)
def get_insights(group_id: int, db: Session = Depends(get_db)):
    return compute_insights(db, _group_or_404(db, group_id))


@app.post("/api/groups/{group_id}/ask", response_model=AskResponse)
def ask_ledger(group_id: int, payload: AskRequest, db: Session = Depends(get_db)):
    group = _group_or_404(db, group_id)
    sender = _sender(group, payload.sender_id)
    ctx = ledger_context(db, group)
    return AskResponse(answer=answer_question(payload.question, ctx, sender.name if sender else "the user"),
                       ai_mode=ai_mode())


@app.post("/api/groups/{group_id}/nudge", response_model=NudgeResponse)
def nudge(group_id: int, payload: NudgeRequest, db: Session = Depends(get_db)):
    group = _group_or_404(db, group_id)
    ids = {u.id: u for u in group.members}
    if payload.from_user_id not in ids or payload.to_user_id not in ids:
        raise HTTPException(422, "Both users must be members of the group")
    msg = write_nudge(ids[payload.from_user_id].name, ids[payload.to_user_id].name,
                      _money(payload.amount, payload.currency.upper()), group.name, payload.tone)
    return NudgeResponse(message=msg, ai_mode=ai_mode())


# ---------------------------------------------------------------- live sync (SSE)
@app.get("/api/groups/{group_id}/events")
async def group_events(group_id: int, request: Request):
    queue = broker.subscribe(group_id)

    async def stream():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'listeners': broker.subscriber_count(group_id)})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            broker.unsubscribe(group_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- settlements
@app.post("/api/settlements/pay", response_model=SettlementPayResponse, status_code=201)
def pay_settlement(payload: SettlementPayRequest, db: Session = Depends(get_db)):
    group = _group_or_404(db, payload.group_id)
    ids = {u.id: u for u in group.members}
    if payload.from_user_id not in ids or payload.to_user_id not in ids:
        raise HTTPException(422, "Both users must be members of the group")
    if payload.from_user_id == payload.to_user_id:
        raise HTTPException(422, "Cannot settle a debt with yourself")

    currency = payload.currency.upper()
    outstanding = next(
        (d.amount for d in compute_balances(db, group).debts
         if d.from_user.id == payload.from_user_id and d.to_user.id == payload.to_user_id and d.currency == currency),
        0.0,
    )
    if outstanding <= 0:
        raise HTTPException(422, "There is no outstanding debt between these members")
    if payload.amount - outstanding > 0.01:
        raise HTTPException(422, f"Amount exceeds outstanding debt ({outstanding:.2f} {currency})")

    debtor, creditor = ids[payload.from_user_id], ids[payload.to_user_id]
    settlement = Settlement(group_id=group.id, from_user_id=debtor.id, to_user_id=creditor.id,
                            amount=round(payload.amount, 2), currency=currency)
    db.add(settlement)
    db.flush()

    base = settings.public_url
    mode = settings.effective_paypal_mode
    if mode == "demo":
        order = {"order_id": f"DEMO-{uuid.uuid4().hex[:16].upper()}"}
        order["approval_url"] = f"{base}/?paypal=demo&settlement_id={settlement.id}&token={order['order_id']}"
    else:
        try:
            order = paypal_client.create_paypal_order(
                settlement.amount, currency, f"SplitSync: {debtor.name} -> {creditor.name} ({group.name})",
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
    return SettlementPayResponse(settlement=settlement, approval_url=order["approval_url"], mode=mode)


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

    if st.paypal_order_id.startswith("DEMO-"):
        if settings.effective_paypal_mode != "demo":
            raise HTTPException(409, "Demo payments are disabled while real PayPal is configured")
    else:
        result = paypal_client.capture_paypal_order(st.paypal_order_id)
        if result.get("status") != "COMPLETED":
            st.status = "failed"
            db.commit()
            raise HTTPException(402, f"PayPal capture status: {result.get('status')}")

    st.status = "completed"
    st.completed_at = datetime.now(timezone.utc)
    mark_splits_paid(db, st)
    db.commit()
    db.refresh(st)
    broker.publish(st.group_id, "settlement.completed",
                   {"from": st.from_user.name, "to": st.to_user.name, "amount": st.amount})
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
    _group_or_404(db, group_id)
    return db.scalars(
        select(Settlement).where(Settlement.group_id == group_id).order_by(Settlement.created_at.desc())
    ).all()


# ---------------------------------------------------------------- single-URL hosting
# When STATIC_DIR points at the built frontend (frontend/dist), FastAPI serves the SPA too,
# so the whole app deploys as one service (see Dockerfile / render.yaml at the repo root).
_static = Path(settings.static_dir) if settings.static_dir else None
if _static and (_static / "index.html").is_file():
    _static = _static.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and _static in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
