"""Pydantic request/response schemas (the API contract) and AI structured-output schemas."""
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal[
    "food", "groceries", "transport", "lodging", "entertainment",
    "shopping", "utilities", "travel", "health", "other",
]
CATEGORIES: tuple[str, ...] = Category.__args__  # type: ignore[attr-defined]


# ====================================================== AI structured output
class CustomShare(BaseModel):
    name: str = Field(description="Participant name exactly as it should appear in the group")
    amount: float = Field(description="Amount this participant owes for the expense")


class ParsedExpense(BaseModel):
    """Strict schema Gemini must return for a chat message."""

    total_amount: float = Field(description="Total amount of the expense")
    currency: str = Field(default="USD", description="ISO 4217 currency code, e.g. USD")
    description: str = Field(description="Short description of what was bought, e.g. 'Dinner'")
    payer_name: str = Field(description="Name of the member who paid")
    split_type: Literal["equal", "custom"] = Field(description="'equal' or 'custom'")
    participants: list[str] = Field(description="Every member who shares the cost (including payer if they share)")
    custom_shares: list[CustomShare] = Field(
        default_factory=list,
        description="Only when split_type is 'custom': the explicit amount each participant owes",
    )
    category: Category = Field(default="other", description="Spending category")


class ReceiptItem(BaseModel):
    name: str = Field(description="Line item name as printed on the receipt")
    price: float = Field(description="Line item total price")
    assigned_to: list[str] = Field(
        default_factory=list, description="Members who consumed this item; empty = shared by all participants"
    )


class ParsedReceipt(ParsedExpense):
    """Gemini Vision output for a photographed receipt."""

    merchant: str = Field(default="", description="Merchant / store name")
    items: list[ReceiptItem] = Field(default_factory=list, description="Line items (excluding tax / tip)")
    tax_and_tip: float = Field(default=0.0, description="Tax + tip + service charges combined")


# ====================================================== Users / groups
class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be blank")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str | None = None


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    members: list[MemberIn] = Field(min_length=1)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime
    members: list[UserOut]


# ====================================================== Expenses
class ExpenseParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    sender_id: int | None = Field(default=None, description="Member typing the message; resolves 'I' / 'me'")
    source: Literal["chat", "voice"] = "chat"


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user: UserOut
    owed_amount: float
    status: str


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    payer: UserOut
    amount: float
    currency: str
    description: str
    category: str = "other"
    source: str = "chat"
    raw_text: str
    created_at: datetime
    splits: list[SplitOut]
    items: list[ReceiptItem] = []

    @classmethod
    def from_model(cls, e) -> "ExpenseOut":
        out = cls.model_validate(e)
        if e.items_json:
            out.items = [ReceiptItem(**i) for i in json.loads(e.items_json)]
        return out


class ExpenseParseResponse(BaseModel):
    expense: ExpenseOut
    parsed: ParsedExpense
    new_members: list[UserOut] = []
    ai_mode: str
    notes: list[str] = []


# ====================================================== Balances
class MemberBalance(BaseModel):
    user: UserOut
    net: float = Field(description="Positive = is owed money, negative = owes money")


class Debt(BaseModel):
    from_user: UserOut
    to_user: UserOut
    amount: float
    currency: str = "USD"


class BalancesOut(BaseModel):
    group_id: int
    currency: str
    members: list[MemberBalance]
    debts: list[Debt]
    naive_transfer_count: int = Field(0, description="Payments needed without debt simplification")


# ====================================================== Insights / AI copilot
class CategoryStat(BaseModel):
    category: str
    total: float
    count: int


class PersonStat(BaseModel):
    user: UserOut
    paid: float
    share: float


class DailyStat(BaseModel):
    date: str
    total: float


class InsightsOut(BaseModel):
    currency: str
    total_spent: float
    expense_count: int
    avg_expense: float
    largest_expense: ExpenseOut | None
    by_category: list[CategoryStat]
    by_person: list[PersonStat]
    daily: list[DailyStat]
    settled_amount: float
    outstanding_amount: float
    payments_saved: int
    highlights: list[str]


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    sender_id: int | None = None


class AskResponse(BaseModel):
    answer: str
    ai_mode: str


class NudgeRequest(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float = Field(gt=0)
    currency: str = "USD"
    tone: Literal["friendly", "funny", "formal"] = "friendly"


class NudgeResponse(BaseModel):
    message: str
    ai_mode: str


# ====================================================== Settlements
class SettlementPayRequest(BaseModel):
    group_id: int
    from_user_id: int
    to_user_id: int
    amount: float = Field(gt=0)
    currency: str = "USD"


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_id: int
    from_user: UserOut
    to_user: UserOut
    amount: float
    currency: str
    status: str
    paypal_order_id: str | None
    created_at: datetime
    completed_at: datetime | None


class SettlementPayResponse(BaseModel):
    settlement: SettlementOut
    approval_url: str
    mode: str = "sandbox"


class CaptureRequest(BaseModel):
    order_id: str | None = None
