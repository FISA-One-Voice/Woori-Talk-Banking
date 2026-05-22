# =============================================================================
# backend/app/models/account.py
#
# [이 파일의 역할]
# accounts 테이블의 구조를 Python 클래스로 정의합니다.
# SQLAlchemy ORM 을 사용하여 DB 테이블과 Python 객체를 매핑합니다.
#
# [다른 파일과의 관계]
# ├─ database.py              → Base 클래스를 가져와 상속합니다.
# ├─ features/account/service.py → 이 모델을 사용해 DB 쿼리를 실행합니다.
# └─ main.py                 → 테이블 생성 시 이 모델을 import 합니다.
# =============================================================================

import uuid

from sqlalchemy import BigInteger, Column, DateTime, String, func

from app.core.database import Base


class Account(Base):
    """accounts 테이블 ORM 모델."""

    __tablename__ = "accounts"

    # 계좌 고유 ID (Primary Key)
    account_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # 계좌 소유자 ID (users 테이블 참조)
    user_id = Column(String, nullable=False)

    # 은행명
    bank_name = Column(String, nullable=False)

    # 계좌번호
    account_number = Column(String, nullable=False)

    # 계좌 유형 (입출금, 저축 등)
    account_type = Column(String)

    # 잔액 (원화 정수)
    balance = Column(BigInteger, nullable=False)

    # 계좌 별명 (선택)
    alias = Column(String)

    # 생성 일시
    created_at = Column(DateTime, server_default=func.now())