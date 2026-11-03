"""Pydantic request/response schemas (API contract)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------- AI structured output ----------
class CustomShare(BaseModel):
    name: str = Field(description="Participant name exactly as it should appear in the group")
    amount: float = Field(description="Amount this participant owes for the expense")


class ParsedExpense(BaseModel):
    """Strict schema Gemini must return."""

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


# ---------- Users / groups ----------
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


# ---------- Expenses ----------
class ExpenseParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    sender_id: int | None = Field(
        default=None, description="Member typing the message; resolves 'I' / 'me'"
    )


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
    raw_text: str
    created_at: datetime
    splits: list[SplitOut]


class ExpenseParseResponse(BaseModel):
    expense: ExpenseOut
    parsed: ParsedExpense
    new_members: list[UserOut] = []
    ai_mode: str


# ---------- Balances ----------
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


# ---------- Settlements ----------
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


class CaptureRequest(BaseModel):
    order_id: str | None = None
