import uuid
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.recipient import RegisteredRecipient
    from app.models.transaction import Transaction
    from app.models.user import User


def _now() -> datetime:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).replace(tzinfo=None)


class StandingOrder(Base):
    """자동이체 테이블 (DB 테이블명: standing_orders)"""

    __tablename__ = "standing_orders"

    order_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    from_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.account_id"), nullable=False
    )
    recipient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registered_recipients.recipient_id"), nullable=False
    )
    # CHECK amount > 0 (애플리케이션 레벨에서 강제)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 'monthly' | 'weekly'
    cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    # monthly일 때 1~31
    scheduled_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # weekly일 때 0~6 (0=월요일)
    scheduled_dow: Mapped[int | None] = mapped_column(Integer, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    terms_agreed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 'active' | 'paused' | 'cancelled'
    status: Mapped[str] = mapped_column(String(10), default="active", nullable=False)
    next_execution_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="standing_orders")
    from_account: Mapped["Account"] = relationship(
        "Account", back_populates="standing_orders"
    )
    recipient: Mapped["RegisteredRecipient"] = relationship(
        "RegisteredRecipient", back_populates="standing_orders"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="auto_order"
    )
