import uuid
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.standing_order import StandingOrder
    from app.models.transaction import Transaction
    from app.models.user import User


def _now() -> datetime:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).replace(tzinfo=None)


class RegisteredRecipient(Base):
    """등록 수취인 테이블 (DB 테이블명: registered_recipients)"""

    __tablename__ = "registered_recipients"
    # 동일 사용자 내 alias 중복 등록 DB 레벨 차단 (다른 사용자 간 충돌 없음)
    __table_args__ = (UniqueConstraint("user_id", "alias", name="uq_user_alias"),)

    recipient_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(50), nullable=False)
    account_number: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="AES-256 암호화 저장 필수. 복호화는 service.py에서 decrypt() 호출",
    )
    recipient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="recipients")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="recipient"
    )
    standing_orders: Mapped[list["StandingOrder"]] = relationship(
        "StandingOrder", back_populates="recipient"
    )
