"""자동이체 API Swagger 테스트용 전체 시드 스크립트.

실행:
    cd backend
    CRYPTO_NOOP=true python tests/seed_auto_transfer.py

생성 계정 6명 (PIN 전원 동일: 000001):
    안유민 010-1111-0001
    김지연 010-1111-0002
    민채영 010-1111-0003
    이남길 010-1111-0004
    권민석 010-1111-0005
    이도원 010-1111-0006
"""

import sys
sys.path.insert(0, ".")

import bcrypt
from datetime import datetime, timedelta, timezone
import app.models  # noqa: F401
from app.core.database import Base, SessionLocal, engine
from app.models.account import Account
from app.models.event import Event, EventParticipation
from app.models.recipient import RegisteredRecipient
from app.models.standing_order import StandingOrder
from app.models.transaction import Transaction
from app.models.user import User

PIN = "000001"

def _now():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).replace(tzinfo=None)

USERS = [
    {"name": "안유민", "phone": "010-1111-0001"},
    {"name": "김지연", "phone": "010-1111-0002"},
    {"name": "민채영", "phone": "010-1111-0003"},
    {"name": "이남길", "phone": "010-1111-0004"},
    {"name": "권민석", "phone": "010-1111-0005"},
    {"name": "이도원", "phone": "010-1111-0006"},
]

ALIASES = ["바보", "멍청이", "똑똑이", "귀염둥이", "천재"]

BANKS = ["우리은행", "신한은행", "국민은행", "카카오뱅크", "하나은행"]

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pin_hash = bcrypt.hashpw(PIN.encode(), bcrypt.gensalt()).decode()

    try:
        # ── 이벤트 2개 공통 생성 ──────────────────────────────────────────────────
        event1 = db.query(Event).filter_by(title="신규가입 환영 이벤트").first()
        if not event1:
            event1 = Event(
                title="신규가입 환영 이벤트",
                description="우리톡 뱅킹 신규 가입 고객 대상 혜택 이벤트입니다.",
                banner_image_url="https://example.com/banner1.png",
                is_active=True,
                start_at=_now() - timedelta(days=5),
                end_at=_now() + timedelta(days=25),
            )
            db.add(event1)

        event2 = db.query(Event).filter_by(title="자동이체 첫 등록 캐시백").first()
        if not event2:
            event2 = Event(
                title="자동이체 첫 등록 캐시백",
                description="자동이체 첫 등록 고객에게 1,000원 캐시백 지급",
                banner_image_url="https://example.com/banner2.png",
                is_active=True,
                start_at=_now() - timedelta(days=1),
                end_at=_now() + timedelta(days=30),
            )
            db.add(event2)

        db.flush()

        created_users = []

        for idx, u_data in enumerate(USERS):
            existing = db.query(User).filter_by(phone=u_data["phone"]).first()
            if existing:
                print(f"⚠️  {u_data['name']} 이미 존재 — 건너뜁니다.")
                created_users.append(existing)
                continue

            # ── User ──────────────────────────────────────────────────────────
            user = User(
                name=u_data["name"],
                phone=u_data["phone"],
                birthday="1995-01-01",
                address=f"서울시 강남구 테헤란로 {idx + 1}길",
                resident_number=f"9501{idx+1:02d}-1234567",
                disability_type="전맹",
                tts_speed=1.0,
                pin_hash=pin_hash,
                embedding_vector=[0.1] * 192,
            )
            db.add(user)
            db.flush()

            # ── Account (주계좌 + 저축계좌) ────────────────────────────────────
            account_main = Account(
                user_id=user.user_id,
                bank_name="우리은행",
                account_number=f"1002-{idx+1:03d}-{100001 + idx}",
                account_type="입출금",
                balance=5_000_000 + idx * 1_000_000,
                alias="주거래",
                is_primary=True,
            )
            account_save = Account(
                user_id=user.user_id,
                bank_name="우리은행",
                account_number=f"1002-{idx+1:03d}-{200001 + idx}",
                account_type="저축",
                balance=10_000_000 + idx * 500_000,
                alias="저축",
                is_primary=False,
            )
            db.add_all([account_main, account_save])
            db.flush()

            # ── RegisteredRecipient (5명) ──────────────────────────────────────
            recipients = []
            for r_idx, (alias, other) in enumerate(
                zip(ALIASES, [u for u in USERS if u["name"] != u_data["name"]])
            ):
                r = RegisteredRecipient(
                    user_id=user.user_id,
                    alias=alias,
                    bank_name=BANKS[r_idx % len(BANKS)],
                    account_number=f"999-{idx+1:03d}-{r_idx+1:06d}",
                    recipient_name=other["name"],
                )
                db.add(r)
                recipients.append(r)
            db.flush()

            # ── StandingOrder (자동이체 2건: monthly + weekly) ─────────────────
            order_monthly = StandingOrder(
                user_id=user.user_id,
                from_account_id=account_main.account_id,
                recipient_id=recipients[0].recipient_id,
                amount=50_000,
                cycle="monthly",
                scheduled_day=15,
                scheduled_dow=None,
                password_hash=pin_hash,
                terms_agreed_at=_now(),
                status="active",
                next_execution_at=_now() + timedelta(days=10),
                transfer_note="용돈",
            )
            order_weekly = StandingOrder(
                user_id=user.user_id,
                from_account_id=account_main.account_id,
                recipient_id=recipients[1].recipient_id,
                amount=30_000,
                cycle="weekly",
                scheduled_day=None,
                scheduled_dow=0,
                password_hash=pin_hash,
                terms_agreed_at=_now(),
                status="active",
                next_execution_at=_now() + timedelta(days=3),
                transfer_note="점심값",
            )
            order_paused = StandingOrder(
                user_id=user.user_id,
                from_account_id=account_save.account_id,
                recipient_id=recipients[2].recipient_id,
                amount=100_000,
                cycle="monthly",
                scheduled_day=1,
                scheduled_dow=None,
                password_hash=pin_hash,
                terms_agreed_at=_now(),
                status="paused",
                next_execution_at=None,
                transfer_note="월세",
            )
            db.add_all([order_monthly, order_weekly, order_paused])
            db.flush()

            # ── Transaction (거래내역 3건) ─────────────────────────────────────
            tx1 = Transaction(
                user_id=user.user_id,
                from_account_id=account_main.account_id,
                recipient_id=recipients[0].recipient_id,
                auto_order_id=None,
                to_bank_name=recipients[0].bank_name,
                to_account_number=recipients[0].account_number,
                to_name=recipients[0].recipient_name,
                amount=50_000,
                tx_type="transfer",
                status="completed",
                category="가족",
                memo="이번달 용돈",
            )
            tx2 = Transaction(
                user_id=user.user_id,
                from_account_id=account_main.account_id,
                recipient_id=recipients[1].recipient_id,
                auto_order_id=order_monthly.order_id,
                to_bank_name=recipients[1].bank_name,
                to_account_number=recipients[1].account_number,
                to_name=recipients[1].recipient_name,
                amount=50_000,
                tx_type="auto_transfer",
                status="completed",
                category="생활비",
                memo="자동이체",
            )
            tx3 = Transaction(
                user_id=user.user_id,
                from_account_id=account_main.account_id,
                recipient_id=None,
                auto_order_id=None,
                to_bank_name="카카오뱅크",
                to_account_number=f"3333-{idx+1:02d}-000000",
                to_name="홍직접",
                amount=200_000,
                tx_type="transfer",
                status="completed",
                category="기타",
                memo="직접이체 테스트",
            )
            db.add_all([tx1, tx2, tx3])
            db.flush()

            # ── EventParticipation ─────────────────────────────────────────────
            db.add(EventParticipation(event_id=event1.event_id, user_id=user.user_id))
            if idx % 2 == 0:
                db.add(EventParticipation(event_id=event2.event_id, user_id=user.user_id))
            db.flush()

            created_users.append(user)
            print(f"✅ {user.name} ({user.phone}) 생성 완료")

        db.commit()

        # ── 결과 출력 ──────────────────────────────────────────────────────────
        print()
        print("=" * 65)
        print("  Swagger 테스트 정보  (PIN 전원 공통: 000001)")
        print("=" * 65)
        for user in created_users:
            account = db.query(Account).filter_by(
                user_id=user.user_id, is_primary=True
            ).first()
            recipients = db.query(RegisteredRecipient).filter_by(
                user_id=user.user_id
            ).all()
            print(f"\n  ▶ {user.name}  |  {user.phone}")
            print(f"    fromAccountId : {account.account_id}")
            print(f"    잔액          : {account.balance:,}원")
            print(f"    수취인:")
            for r in recipients:
                print(f"      [{r.alias}] {r.recipient_id}  ({r.recipient_name} / {r.bank_name})")

        print()
        print("=" * 65)
        print("  POST /api/auto-transfer  예시 바디 (안유민 기준)")
        print("=" * 65)
        u0 = created_users[0]
        a0 = db.query(Account).filter_by(user_id=u0.user_id, is_primary=True).first()
        r0 = db.query(RegisteredRecipient).filter_by(user_id=u0.user_id).first()
        print(f"""
  [monthly]
  {{
    "fromAccountId": "{a0.account_id}",
    "recipientId": "{r0.recipient_id}",
    "amount": 50000,
    "cycle": "monthly",
    "scheduledDay": 15,
    "password": "000001",
    "termsAgreed": true,
    "transferNote": "용돈"
  }}

  [weekly]
  {{
    "fromAccountId": "{a0.account_id}",
    "recipientId": "{r0.recipient_id}",
    "amount": 30000,
    "cycle": "weekly",
    "scheduledDow": 0,
    "password": "000001",
    "termsAgreed": true
  }}

  [DIRECT]
  {{
    "fromAccountId": "{a0.account_id}",
    "toAccountNumber": "1002-999-888888",
    "bankName": "하나은행",
    "toName": "홍직접",
    "amount": 100000,
    "cycle": "monthly",
    "scheduledDay": 1,
    "password": "000001",
    "termsAgreed": true
  }}""")
        print("=" * 65)

    except Exception as e:
        db.rollback()
        print(f"❌ 오류: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
