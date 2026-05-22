import uuid

from sqlalchemy import Column, Date, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

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
    embedding_vector = Column(Vector(256), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
