import uuid
from sqlalchemy import Column, String, BigInteger, DateTime, func

from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    bank_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    account_type = Column(String)
    balance = Column(BigInteger, nullable=False)
    alias = Column(String)
    created_at = Column(DateTime, server_default=func.now())