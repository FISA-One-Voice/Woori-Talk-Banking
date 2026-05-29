import uuid
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.standing_order import StandingOrder
    from app.models.transaction import Transaction
    from app.models.user import User


_KST = timezone(timedelta(hours=9))


def _now() -> datetime:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).replace(tzinfo=None)


class Account(Base):
    """계좌 테이블 (DB 테이블명: accounts)"""

    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    bank_name: Mapped[str] = mapped_column(String(50), nullable=False)
    account_number: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="AES-256 암호화 저장 필수. 복호화는 service.py에서 decrypt() 호출",
    )
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # CHECK balance >= 0 (애플리케이션 레벨에서 강제)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    alias: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 이름 기반 이체 수신 계좌 지정용 (transfer: phone으로 조회 시 is_primary=True 계좌로 이체)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="accounts")
    transactions_from: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="from_account"
    )
    standing_orders: Mapped[list["StandingOrder"]] = relationship(
        "StandingOrder", back_populates="from_account"
    )
