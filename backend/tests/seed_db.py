"""더미 데이터 시드 스크립트.

models.plan.md §8 기준 7개 테이블에 더미 데이터를 삽입하고
CRUD 동작 및 relationship 조회를 검증한다.

실행:
    cd backend
    python tests/seed_db.py
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

import app.models  # noqa: F401 — 전체 모델 등록
from app.core.database import Base, SessionLocal, engine
from app.models.account import Account
from app.models.event import Event, EventParticipation
from app.models.recipient import RegisteredRecipient
from app.models.standing_order import StandingOrder
from app.models.transaction import Transaction
from app.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed() -> None:
    """모든 테이블에 더미 데이터를 삽입하고 CRUD를 검증한다."""
    print("테이블 생성 중...")
    Base.metadata.create_all(bind=engine)
    print("완료.")

    db = SessionLocal()
    try:
        print("\n[CREATE] 더미 데이터 삽입 중...")

        # str() 제거 — uuid.UUID 객체로 넣어야 함
        user_id = uuid.uuid4()
        user = User(
            user_id=user_id,
            name="홍길동",
            phone="010-1234-5678",
            birthday="1990-01-01",
            address="서울시 강남구",
            resident_number="900101-1234567",
            disability_type="전맹",
            tts_speed=1.0,
            pin_hash="$2b$12$dummy_hash_for_seed",
            embedding_vector=[0.1] * 192,
        )
        db.add(user)
        db.flush()
        print(f"  users: {user.user_id} ({user.name})")

        account_primary = Account(
            user_id=user_id,
            bank_name="우리은행",
            account_number="1002-123-456789",
            account_type="입출금",
            balance=1_000_000,
            alias="주거래 계좌",
            is_primary=True,
        )
        account_savings = Account(
            user_id=user_id,
            bank_name="우리은행",
            account_number="1002-987-654321",
            account_type="저축",
            balance=5_000_000,
            alias="저축 계좌",
            is_primary=False,
        )
        db.add_all([account_primary, account_savings])
        db.flush()
        print(f"  accounts: {account_primary.alias} (is_primary=True), {account_savings.alias}")

        recipient_mom = RegisteredRecipient(
            user_id=user_id,
            alias="엄마",
            bank_name="신한은행",
            account_number="110-123-456789",
            recipient_name="김순자",
        )
        recipient_company = RegisteredRecipient(
            user_id=user_id,
            alias="회사",
            bank_name="국민은행",
            account_number="123-456-789012",
            recipient_name="(주)워리톡",
        )
        db.add_all([recipient_mom, recipient_company])
        db.flush()
        print(f"  registered_recipients: '{recipient_mom.alias}', '{recipient_company.alias}'")

        standing_order = StandingOrder(
            user_id=user_id,
            from_account_id=account_primary.account_id,
            recipient_id=recipient_mom.recipient_id,
            amount=300_000,
            cycle="monthly",
            scheduled_day=25,
            password_hash="$2b$12$dummy_hash_for_seed",
            terms_agreed_at=_now(),
            status="active",
            next_execution_at=_now() + timedelta(days=3),
        )
        db.add(standing_order)
        db.flush()
        print(f"  standing_orders: {standing_order.cycle} {standing_order.amount}원")

        tx_registered = Transaction(
            user_id=user_id,
            from_account_id=account_primary.account_id,
            recipient_id=recipient_mom.recipient_id,
            to_bank_name="신한은행",
            to_account_number="110-123-456789",
            to_name="김순자",
            amount=100_000,
            tx_type="transfer",
            status="completed",
            category="가족",
            memo="용돈",
        )
        tx_unregistered = Transaction(
            user_id=user_id,
            from_account_id=account_primary.account_id,
            to_bank_name="카카오뱅크",
            to_account_number="3333-01-1234567",
            to_name="이철수",
            amount=50_000,
            tx_type="transfer",
            status="completed",
        )
        db.add_all([tx_registered, tx_unregistered])
        db.flush()
        print(f"  transactions: 등록 수취인 이체 1건 + 미등록 이체 1건")

        event_active = Event(
            title="신규 가입 환영 이벤트",
            description="우리톡뱅킹 신규 가입 고객 혜택",
            is_active=True,
            start_at=_now() - timedelta(days=1),
            end_at=_now() + timedelta(days=30),
        )
        event_ended = Event(
            title="첫 이체 캐시백 이벤트",
            description="종료된 이벤트",
            is_active=False,
            start_at=_now() - timedelta(days=30),
            end_at=_now() - timedelta(days=1),
        )
        db.add_all([event_active, event_ended])
        db.flush()
        print(f"  events: active 1건, 종료 1건")

        participation = EventParticipation(
            event_id=event_active.event_id,
            user_id=user_id,
        )
        db.add(participation)
        db.commit()
        print(f"  event_participations: 1건")

        # ── READ ──────────────────────────────────────────────────
        print("\n[READ] relationship 조회 검증...")
        db.expire_all()

        loaded_user = db.query(User).filter_by(user_id=user_id).first()
        assert loaded_user is not None
        assert len(loaded_user.accounts) == 2
        assert len(loaded_user.recipients) == 2
        assert len(loaded_user.transactions) == 2
        assert len(loaded_user.standing_orders) == 1
        print(f"  user.accounts({len(loaded_user.accounts)}), recipients({len(loaded_user.recipients)}), "
              f"transactions({len(loaded_user.transactions)}), standing_orders({len(loaded_user.standing_orders)}) ✅")

        loaded_tx = db.query(Transaction).filter_by(tx_id=tx_registered.tx_id).first()
        assert loaded_tx.recipient is not None
        assert loaded_tx.from_account is not None
        print(f"  transaction.recipient='{loaded_tx.recipient.alias}', from_account='{loaded_tx.from_account.alias}' ✅")

        found = (
            db.query(RegisteredRecipient)
            .filter_by(user_id=user_id, alias="엄마")
            .one()
        )
        assert found.recipient_name == "김순자"
        print(f"  alias 검색 → {found.recipient_name} ✅")

        # ── UPDATE ────────────────────────────────────────────────
        print("\n[UPDATE] 잔액 업데이트 검증...")
        loaded_account = db.query(Account).filter_by(account_id=account_primary.account_id).first()
        loaded_account.balance -= 100_000
        db.commit()
        db.expire(loaded_account)
        assert loaded_account.balance == 900_000
        print(f"  balance 1,000,000 → 900,000 ✅")

        # ── DELETE ────────────────────────────────────────────────
        print("\n[DELETE] standing_order 취소 검증...")
        loaded_so = db.query(StandingOrder).filter_by(order_id=standing_order.order_id).first()
        loaded_so.status = "cancelled"
        db.commit()
        db.expire(loaded_so)
        assert loaded_so.status == "cancelled"
        print(f"  standing_order.status='cancelled' ✅")

        # ── UniqueConstraint ──────────────────────────────────────
        print("\n[UniqueConstraint] alias 중복 등록 오류 검증...")
        from sqlalchemy.exc import IntegrityError
        try:
            duplicate = RegisteredRecipient(
                user_id=user_id,
                alias="엄마",
                bank_name="하나은행",
                account_number="111-222-333444",
                recipient_name="홍길순",
            )
            db.add(duplicate)
            db.commit()
            print("  ❌ UniqueConstraint 미동작")
        except IntegrityError:
            db.rollback()
            print("  UniqueConstraint 오류 정상 발생 ✅")

        print("\n✅ 모든 CRUD 검증 완료.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 오류: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()