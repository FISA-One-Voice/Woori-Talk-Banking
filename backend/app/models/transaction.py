import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.recipient import RegisteredRecipient
    from app.models.standing_order import StandingOrder
    from app.models.user import User


_KST = timezone(timedelta(hours=9))


def _now() -> datetime:
    return datetime.now(_KST).replace(tzinfo=None)


class Transaction(Base):
    """거래내역 테이블 (DB 테이블명: transactions)"""

    __tablename__ = "transactions"

    tx_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    from_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.account_id"), nullable=False
    )
    recipient_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("registered_recipients.recipient_id"),
        nullable=True,
    )
    auto_order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("standing_orders.order_id"), nullable=True
    )
    to_bank_name: Mapped[str] = mapped_column(String(50), nullable=False)
    to_account_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="AES-256 암호화 저장 필수. 복호화는 service.py에서 decrypt() 호출",
    )
    to_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # CHECK amount > 0 (애플리케이션 레벨에서 강제)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 'transfer' | 'auto_transfer' | 'bill_payment'
    tx_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'pending' | 'completed' | 'failed'
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    from_account: Mapped["Account"] = relationship(
        "Account", back_populates="transactions_from"
    )
    recipient: Mapped["RegisteredRecipient | None"] = relationship(
        "RegisteredRecipient", back_populates="transactions"
    )
    auto_order: Mapped["StandingOrder | None"] = relationship(
        "StandingOrder", back_populates="transactions"
    )
