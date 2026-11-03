"""SQLAlchemy ORM models."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["GroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Expense.created_at"
    )

    @property
    def members(self) -> list[User]:
        return [m.user for m in self.memberships]


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    group: Mapped[Group] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    group: Mapped[Group] = relationship(back_populates="expenses")
    payer: Mapped[User] = relationship()
    splits: Mapped[list["ExpenseSplit"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owed_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # 'pending' | 'paid'

    expense: Mapped[Expense] = relationship(back_populates="splits")
    user: Mapped[User] = relationship()


class Settlement(Base):
    """A debt payment between two members, backed by a PayPal order."""

    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(12), default="created")  # created|completed|cancelled|failed
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])
