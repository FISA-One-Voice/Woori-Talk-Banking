import uuid
from sqlalchemy import Column, String, Date, Float, DateTime, func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    birthday = Column(Date)
    address = Column(String)
    resident_number = Column(String)
    disability_type = Column(String)
    tts_speed = Column(Float)
    pin_hash = Column(String)
    created_at = Column(DateTime, server_default=func.now())