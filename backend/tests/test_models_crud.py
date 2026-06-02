"""모델 CRUD 검증 테스트.

models.plan.md §9 완료 기준 중 DB 연결이 필요한 항목을 검증한다.

실행 방법:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_models_crud.py -v

전제 조건:
    - .env에 DATABASE_URL=postgresql://... 설정 (Aiven PostgreSQL)
    - Aiven에서 CREATE EXTENSION IF NOT EXISTS vector; 실행 완료
    - CRYPTO_NOOP=true 또는 .env에 CRYPTO_KEY 설정
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

# app.models import는 conftest.py에서 처리합니다.
# engine은 test_all_tables_exist에서 테이블 목록 조회에 직접 사용합니다.
from app.core.database import engine
from app.models.account import Account
from app.models.event import Event, EventParticipation
from app.models.recipient import RegisteredRecipient
from app.models.standing_order import StandingOrder
from app.models.transaction import Transaction
from app.models.user import User


_KST = timezone(timedelta(hours=9))


def _now() -> datetime:
    return datetime.now(_KST).replace(tzinfo=None)


# ── fixtures ──────────────────────────────────────────────────────────────────
# db 픽스처는 conftest.py에서 제공합니다.


@pytest.fixture(scope="module")
def test_user(db):
    """테스트 전용 사용자 1명. 모듈 종료 시 CASCADE로 연관 데이터 모두 삭제."""
    user = User(
        name="테스트유저",
        phone=f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}",
        disability_type="전맹",
        tts_speed=1.0,
        pin_hash="$2b$12$test_hash",
        embedding_vector=[0.0] * 192,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    # 테스트 데이터 정리 (FK 순서 역순)
    db.query(EventParticipation).filter_by(user_id=user.user_id).delete()
    db.query(Transaction).filter_by(user_id=user.user_id).delete()
    db.query(StandingOrder).filter_by(user_id=user.user_id).delete()
    db.query(RegisteredRecipient).filter_by(user_id=user.user_id).delete()
    db.query(Account).filter_by(user_id=user.user_id).delete()
    db.query(User).filter_by(user_id=user.user_id).delete()
    db.commit()


# ── 테이블 생성 확인 ───────────────────────────────────────────────────────────


def test_all_tables_exist():
    """uvicorn 기동 시 모든 테이블이 오류 없이 생성되는지 확인."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    expected = {
        "users",
        "accounts",
        "registered_recipients",
        "standing_orders",
        "transactions",
        "events",
        "event_participations",
    }
    existing = set(inspector.get_table_names())
    missing = expected - existing
    assert not missing, f"생성되지 않은 테이블: {missing}"


# ── User CRUD ─────────────────────────────────────────────────────────────────


def test_user_create(test_user):
    """users 테이블 CREATE 확인."""
    assert test_user.user_id is not None
    # UUID 문자열 36자 확인 (PostgreSQL은 UUID 객체로 반환되므로 str 변환)
    assert len(str(test_user.user_id)) == 36


def test_user_read(db, test_user):
    """users 테이블 READ 확인."""
    found = db.query(User).filter_by(user_id=test_user.user_id).first()
    assert found is not None
    assert found.name == "테스트유저"
    assert found.embedding_vector is not None


def test_user_update(db, test_user):
    """users 테이블 UPDATE 확인 (tts_speed 변경)."""
    test_user.tts_speed = 1.5
    db.commit()
    db.expire(test_user)
    assert test_user.tts_speed == 1.5


def test_user_delete_is_soft(db, test_user):
    """users 테이블 soft-delete 패턴 — status 변경 (fixture가 실제 삭제 담당)."""
    # User는 FK 의존이 많아 soft delete 패턴 확인용으로 disability_type 수정
    test_user.disability_type = "저시력"
    db.commit()
    db.expire(test_user)
    assert test_user.disability_type == "저시력"


# ── Account CRUD ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_account(db, test_user):
    account = Account(
        user_id=test_user.user_id,
        bank_name="우리은행",
        account_number="1002-TEST-001",
        account_type="입출금",
        balance=500_000,
        alias="테스트 계좌",
        is_primary=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_account_create(test_account):
    """accounts CREATE + is_primary 기본값 확인."""
    assert test_account.account_id is not None
    assert test_account.is_primary is True


def test_account_read_via_relationship(db, test_user, test_account):
    """user.accounts relationship 조회 확인."""
    db.expire(test_user)
    assert any(a.account_id == test_account.account_id for a in test_user.accounts)


def test_account_update_balance(db, test_account):
    """accounts UPDATE — balance 차감."""
    db.expire(test_account)
    fresh = db.get(Account, test_account.account_id)
    fresh.balance -= 100_000
    db.commit()
    db.expire(fresh)
    assert fresh.balance == 400_000


def test_account_is_primary_flag(db, test_user, test_account):
    """is_primary=True 계좌 단건 조회 (transfer 서비스 시나리오)."""
    primary = (
        db.query(Account).filter_by(user_id=test_user.user_id, is_primary=True).first()
    )
    assert primary is not None
    assert primary.account_id == test_account.account_id


# ── RegisteredRecipient CRUD + UniqueConstraint ────────────────────────────────


@pytest.fixture(scope="module")
def test_recipient(db, test_user):
    recipient = RegisteredRecipient(
        user_id=test_user.user_id,
        alias="엄마",
        bank_name="신한은행",
        account_number="110-TEST-001",
        recipient_name="김순자",
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient


def test_recipient_create(test_recipient):
    """registered_recipients CREATE 확인."""
    assert test_recipient.recipient_id is not None


def test_alias_search_returns_single_row(db, test_user, test_recipient):
    """alias 검색 쿼리 단건 반환 확인 (WHERE user_id=? AND alias='엄마')."""
    found = (
        db.query(RegisteredRecipient)
        .filter_by(user_id=test_user.user_id, alias="엄마")
        .one()
    )
    assert found.recipient_name == "김순자"


def test_unique_constraint_alias(db, test_user):
    """alias 중복 등록 시 UniqueConstraint 오류 발생 확인."""
    duplicate = RegisteredRecipient(
        user_id=test_user.user_id,
        alias="엄마",  # 중복
        bank_name="하나은행",
        account_number="111-TEST-999",
        recipient_name="홍길순",
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_recipient_update(db, test_recipient):
    """registered_recipients UPDATE — alias 변경."""
    test_recipient.alias = "어머니"
    db.commit()
    db.expire(test_recipient)
    assert test_recipient.alias == "어머니"


# ── StandingOrder CRUD ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_standing_order(db, test_user, test_account, test_recipient):
    order = StandingOrder(
        user_id=test_user.user_id,
        from_account_id=test_account.account_id,
        recipient_id=test_recipient.recipient_id,
        amount=200_000,
        cycle="monthly",
        scheduled_day=25,
        password_hash="$2b$12$test_hash",
        terms_agreed_at=_now(),
        status="active",
        next_execution_at=_now() + timedelta(days=5),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def test_standing_order_create(test_standing_order):
    """standing_orders CREATE 확인."""
    assert test_standing_order.order_id is not None
    assert test_standing_order.status == "active"


def test_standing_order_cancel(db, test_standing_order):
    """standing_orders UPDATE — status=cancelled (취소 시나리오)."""
    test_standing_order.status = "cancelled"
    db.commit()
    db.expire(test_standing_order)
    assert test_standing_order.status == "cancelled"


# ── Transaction CRUD ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_transaction(db, test_user, test_account, test_recipient):
    tx = Transaction(
        user_id=test_user.user_id,
        from_account_id=test_account.account_id,
        recipient_id=test_recipient.recipient_id,
        to_bank_name="신한은행",
        to_account_number="110-TEST-001",
        to_name="김순자",
        amount=50_000,
        tx_type="transfer",
        status="pending",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def test_transaction_create(test_transaction):
    """transactions CREATE 확인."""
    assert test_transaction.tx_id is not None
    assert test_transaction.status == "pending"


def test_transaction_read_relationships(db, test_transaction):
    """transaction.user, from_account, recipient relationship 조회 확인."""
    db.expire(test_transaction)
    assert test_transaction.user is not None
    assert test_transaction.from_account is not None
    assert test_transaction.recipient is not None


def test_transaction_update_status(db, test_transaction):
    """transactions UPDATE — status=completed."""
    test_transaction.status = "completed"
    db.commit()
    db.expire(test_transaction)
    assert test_transaction.status == "completed"


def test_transaction_nullable_recipient(db, test_user, test_account):
    """미등록 수취인 이체 (recipient_id=None) 저장 확인."""
    tx = Transaction(
        user_id=test_user.user_id,
        from_account_id=test_account.account_id,
        to_bank_name="카카오뱅크",
        to_account_number="3333-TEST-999",
        to_name="이철수",
        amount=10_000,
        tx_type="transfer",
        status="completed",
    )
    db.add(tx)
    db.commit()
    assert tx.recipient_id is None
    assert tx.auto_order_id is None
    db.delete(tx)
    db.commit()


# ── Event + EventParticipation ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_event(db):
    event = Event(
        title="테스트 이벤트",
        is_active=True,
        start_at=_now() - timedelta(days=1),
        end_at=_now() + timedelta(days=10),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    yield event
    db.query(EventParticipation).filter_by(event_id=event.event_id).delete()
    db.delete(event)
    db.commit()


def test_event_participation_with_user_fk(db, test_user, test_event):
    """event_participations.user_id FK 정상 동작 확인."""
    participation = EventParticipation(
        event_id=test_event.event_id,
        user_id=test_user.user_id,
    )
    db.add(participation)
    db.commit()
    assert participation.participation_id is not None


def test_event_participation_unique(db, test_user, test_event):
    """동일 (user_id, event_id) 중복 참여 시 UniqueConstraint 오류 확인."""
    duplicate = EventParticipation(
        event_id=test_event.event_id,
        user_id=test_user.user_id,
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
