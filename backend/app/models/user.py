import uuid
from sqlalchemy import Column, String, Float, Date, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    birthday = Column(Date, nullable=True)
    address = Column(String, nullable=True)
    resident_number = Column(String, nullable=True)
    disability_type = Column(String, nullable=True)
    tts_speed = Column(Float, default=1.0)
    pin_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
