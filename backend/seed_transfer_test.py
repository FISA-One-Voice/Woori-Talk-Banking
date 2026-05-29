"""이체 API 수동 테스트용 시드 스크립트.

실행:
    cd backend
    python seed_transfer_test.py

동작:
    1. 테스트 유저 + 주계좌(잔액 10,000,000원) 생성 (이미 있으면 잔액만 리셋)
    2. 테스트 등록 수취인 1건 생성 (recipientId 기반 이체 테스트용)
    3. JWT Access Token 발급 후 curl 명령어 출력
"""

import sys
import uuid
from pathlib import Path

# backend/ 를 Python 경로에 추가 (app.* import 가능)
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.jwt_utils import create_access_token  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.recipient import RegisteredRecipient  # noqa: E402
from app.models.user import User  # noqa: E402

# ── 고정 식별자 (재실행해도 동일한 데이터) ──────────────────────────────────────
_USER_UUID = uuid.UUID("aaaabbbb-cccc-dddd-eeee-111122223333")
_USER_ID = str(_USER_UUID)
_ACCOUNT_ID = "aaaabbbb-cccc-dddd-eeee-444455556666"
_RECIPIENT_ID = "aaaabbbb-cccc-dddd-eeee-777788889999"
_INITIAL_BALANCE = 10_000_000  # 1천만원


def seed(db):
    # ── 1. 유저 ─────────────────────────────────────────────────────────────────
    user = db.query(User).filter(User.user_id == _USER_UUID).first()
    if user is None:
        user = User(
            user_id=_USER_UUID,
            name="이체테스터",
            phone="01011112222",
            pin_hash="test-only-not-real-hash",
        )
        db.add(user)
        print(f"  [생성] 유저: {_USER_ID}")
    else:
        print(f"  [기존] 유저: {_USER_ID}")

    # ── 2. 주계좌 ────────────────────────────────────────────────────────────────
    account = db.query(Account).filter(Account.account_id == _ACCOUNT_ID).first()
    if account is None:
        account = Account(
            account_id=_ACCOUNT_ID,
            user_id=_USER_UUID,
            bank_name="우리은행",
            account_number="1002333344445555",
            account_type="입출금",
            balance=_INITIAL_BALANCE,
            alias="테스트계좌",
            is_primary=True,
        )
        db.add(account)
        print(f"  [생성] 주계좌: {_ACCOUNT_ID}  잔액: {_INITIAL_BALANCE:,}원")
    else:
        account.balance = _INITIAL_BALANCE
        print(f"  [리셋] 주계좌 잔액: {_INITIAL_BALANCE:,}원")

    # ── 3. 등록 수취인 (recipientId 기반 이체 테스트용) ───────────────────────────
    recipient = (
        db.query(RegisteredRecipient)
        .filter(RegisteredRecipient.recipient_id == _RECIPIENT_ID)
        .first()
    )
    if recipient is None:
        recipient = RegisteredRecipient(
            recipient_id=_RECIPIENT_ID,
            user_id=_USER_UUID,
            alias="단골수취인",
            bank_name="하나은행",
            account_number="11122233334444",
            recipient_name="김하나",
        )
        db.add(recipient)
        print(f"  [생성] 등록 수취인: {_RECIPIENT_ID} (김하나 / 하나은행)")
    else:
        print(f"  [기존] 등록 수취인: {_RECIPIENT_ID}")

    db.commit()


def print_test_guide(token: str):
    base = "http://localhost:8000"
    idempotency_key = str(uuid.uuid4())

    print()
    print("=" * 70)
    print("  이체 API 수동 테스트 가이드")
    print("=" * 70)
    print(f"\n  user_id      : {_USER_ID}")
    print(f"  account_id   : {_ACCOUNT_ID}")
    print(f"  recipient_id : {_RECIPIENT_ID}")
    print(f"  잔액         : {_INITIAL_BALANCE:,}원")
    print(f"\n  JWT Token:\n  {token}")
    print()

    print("─" * 70)
    print("  [1] 직접 계좌번호 입력 이체 (recipient_id 없이)")
    print("─" * 70)
    print(f"""curl -s -X POST {base}/api/transfer/ \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {token}" \\
  -d '{{
    "recipient": "12345678901234",
    "bankName": "국민은행",
    "amount": 50000,
    "idempotencyKey": "{idempotency_key}",
    "recipientName": "홍길동",
    "recipientId": null
  }}' | python3 -m json.tool""")

    idempotency_key2 = str(uuid.uuid4())
    print()
    print("─" * 70)
    print("  [2] 등록 수취인 기반 이체 (recipientId 사용)")
    print("─" * 70)
    print(f"""curl -s -X POST {base}/api/transfer/ \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {token}" \\
  -d '{{
    "recipient": "",
    "bankName": "",
    "amount": 30000,
    "idempotencyKey": "{idempotency_key2}",
    "recipientName": null,
    "recipientId": "{_RECIPIENT_ID}"
  }}' | python3 -m json.tool""")

    print()
    print("─" * 70)
    print("  [3] 최근 수취인 조회")
    print("─" * 70)
    print(f"""curl -s {base}/api/transfer/recent \\
  -H "Authorization: Bearer {token}" | python3 -m json.tool""")

    print()
    print("─" * 70)
    print("  [4] 잔액 부족 테스트")
    print("─" * 70)
    print(f"""curl -s -X POST {base}/api/transfer/ \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {token}" \\
  -d '{{
    "recipient": "12345678901234",
    "bankName": "국민은행",
    "amount": 99999999,
    "idempotencyKey": "{str(uuid.uuid4())}",
    "recipientName": "돈많은사람",
    "recipientId": null
  }}' | python3 -m json.tool""")

    print()
    print("  * 서버 실행: cd backend && uvicorn app.main:app --reload")
    print("  * Swagger UI: http://localhost:8000/docs")
    print("=" * 70)


def main():
    print(f"\n[DB] {settings.database_url[:60]}...")
    print("\n[시드 데이터 삽입]")

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()

    token = create_access_token({"sub": _USER_ID})
    print_test_guide(token)


if __name__ == "__main__":
    main()
