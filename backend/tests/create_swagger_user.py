"""Swagger 테스트용 사용자 생성 스크립트.

실행:
    cd backend
    python tests/create_swagger_user.py

생성 계정:
    전화번호: 010-0000-0001
    PIN:      111111
"""

import sys

sys.path.insert(0, ".")

import bcrypt
import app.models  # noqa: F401
from app.core.database import Base, SessionLocal, engine
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.user import User


PHONE = "010-0000-0001"
PIN = "111111"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(phone=PHONE).first()
        if existing:
            print(f"이미 존재하는 계정입니다. 전화번호: {PHONE} / PIN: {PIN}")
            return

        pin_hash = bcrypt.hashpw(PIN.encode(), bcrypt.gensalt()).decode()
        user = User(
            name="스웨거테스트",
            phone=PHONE,
            pin_hash=pin_hash,
            embedding_vector=[0.0] * 192,
        )
        db.add(user)
        db.flush()

        account = Account(
            user_id=user.user_id,
            bank_name="우리은행",
            account_number="1002-000-000001",
            account_type="입출금",
            balance=1_000_000,
            alias="주거래",
            is_primary=True,
        )
        db.add(account)

        for alias, name, bank, acct in [
            ("엄마", "김순자", "신한은행", "110-123-456789"),
            ("회사", "(주)워리톡", "국민은행", "123-456-789012"),
            ("친구", "이철수", "카카오뱅크", "3333-01-000001"),
        ]:
            db.add(
                RegisteredRecipient(
                    user_id=user.user_id,
                    alias=alias,
                    bank_name=bank,
                    account_number=acct,
                    recipient_name=name,
                )
            )

        db.commit()
        print("✅ 테스트 계정 생성 완료")
        print(f"   전화번호 : {PHONE}")
        print(f"   PIN      : {PIN}")
        print(f"   등록 수취인: 엄마, 회사, 친구")

    except Exception as e:
        db.rollback()
        print(f"❌ 오류: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
