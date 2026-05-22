# =============================================================================
# backend/app/models/user.py
#
# [이 파일의 역할]
# users 테이블의 구조를 Python 클래스로 정의합니다.
# SQLAlchemy ORM 을 사용하여 DB 테이블과 Python 객체를 매핑합니다.
#
# [다른 파일과의 관계]
# ├─ database.py  → Base 클래스를 가져와 상속합니다.
# └─ main.py      → 테이블 생성 시 이 모델을 import 합니다.
# =============================================================================

import uuid

from sqlalchemy import Column, Date, DateTime, Float, String, func

from app.core.database import Base


class User(Base):
    """users 테이블 ORM 모델."""

    __tablename__ = "users"

    # 사용자 고유 ID (Primary Key)
    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # 이름
    name = Column(String, nullable=False)

    # 전화번호
    phone = Column(String, nullable=False)

    # 생년월일 (선택)
    birthday = Column(Date)

    # 주소 (선택)
    address = Column(String)

    # 주민등록번호 (선택)
    resident_number = Column(String)

    # 장애 유형 (선택)
    disability_type = Column(String)

    # TTS 속도 (선택)
    tts_speed = Column(Float)

    # PIN 해시값
    pin_hash = Column(String)

    # 생성 일시
    created_at = Column(DateTime, server_default=func.now())