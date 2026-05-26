import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.recipient import RegisteredRecipient
    from app.models.standing_order import StandingOrder
    from app.models.transaction import Transaction


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """사용자 테이블 (DB 테이블명: users)"""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    birthday: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    resident_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="AES-256 암호화 저장 필수. 복호화는 service.py에서 decrypt() 호출",
    )
    # 전맹 / 저시력 / 후천성 전맹 중 하나
    disability_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tts_speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 로그인 후 음성을 등록할 수 있으므로 nullable=True 로 변경
    embedding_vector: Mapped[list | None] = mapped_column(Vector(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="user"
    )
    recipients: Mapped[list["RegisteredRecipient"]] = relationship(
        "RegisteredRecipient", back_populates="user"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user"
    )
    standing_orders: Mapped[list["StandingOrder"]] = relationship(
        "StandingOrder", back_populates="user"
    )
