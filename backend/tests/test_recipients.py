"""수취인 공통 서비스 테스트.

실행 방법:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_recipients.py -v

전제 조건:
    - .env에 DATABASE_URL=postgresql://... 설정 (Aiven PostgreSQL)
    - CRYPTO_NOOP=true 또는 .env에 CRYPTO_KEY 설정
"""

import uuid

import pytest

from app.core.exception import RecipientError
from app.features.recipients.schema import ResolvedRecipient
from app.features.recipients.service import (
    match_by_name,
    resolve_by_id,
    resolve_by_phone,
    resolve_or_create_by_alias,
)
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.user import User


def _make_user(phone: str) -> User:
    return User(
        name="테스트유저",
        phone=phone,
        disability_type="전맹",
        tts_speed=1.0,
        pin_hash="$2b$12$test_hash",
        embedding_vector=[0.0] * 192,
    )


# ── 픽스처 ─────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_user(db):
    """수취인 테스트용 사용자."""
    user = _make_user(f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}")
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(RegisteredRecipient).filter_by(user_id=user.user_id).delete()
    db.query(Account).filter_by(user_id=user.user_id).delete()
    db.query(User).filter_by(user_id=user.user_id).delete()
    db.commit()


@pytest.fixture(scope="module")
def phone_user(db):
    """전화번호 조회 테스트용 수취인 사용자 (주계좌 포함)."""
    user = _make_user(f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}")
    db.add(user)
    db.flush()

    account = Account(
        user_id=user.user_id,
        bank_name="우리은행",
        account_number="1002-111-222333",  # CRYPTO_NOOP=true 이므로 평문 저장
        account_type="입출금",
        balance=500000,
        is_primary=True,
    )
    db.add(account)
    db.commit()
    db.refresh(user)
    yield user
    db.query(Account).filter_by(user_id=user.user_id).delete()
    db.query(User).filter_by(user_id=user.user_id).delete()
    db.commit()


@pytest.fixture(scope="module")
def registered_recipient(db, test_user):
    """등록 수취인 1건."""
    r = RegisteredRecipient(
        user_id=test_user.user_id,
        alias="엄마",
        bank_name="국민은행",
        account_number="123-456-789012",  # CRYPTO_NOOP=true 이므로 평문 저장
        recipient_name="홍길동",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    yield r


# ── resolve_by_id ──────────────────────────────────────────────────────────────

def test_resolve_by_id_success(db, test_user, registered_recipient):
    """등록된 수취인 ID로 정상 조회되는지 확인합니다."""
    result = resolve_by_id(db, test_user.user_id, registered_recipient.recipient_id)

    assert isinstance(result, ResolvedRecipient)
    assert result.recipient_id == registered_recipient.recipient_id
    assert result.bank_name == "국민은행"
    assert result.account_number == "123-456-789012"
    assert result.recipient_name == "홍길동"


def test_resolve_by_id_not_found(db, test_user):
    """존재하지 않는 recipient_id면 RECIPIENT_NOT_FOUND를 발생시킵니다."""
    with pytest.raises(RecipientError) as exc_info:
        resolve_by_id(db, test_user.user_id, str(uuid.uuid4()))

    assert exc_info.value.code == "RECIPIENT_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_resolve_by_id_other_user(db, registered_recipient):
    """다른 사용자의 수취인 조회 시도 시 RECIPIENT_NOT_FOUND를 발생시킵니다."""
    other_user_uuid = uuid.uuid4()

    with pytest.raises(RecipientError) as exc_info:
        resolve_by_id(db, other_user_uuid, registered_recipient.recipient_id)

    assert exc_info.value.code == "RECIPIENT_NOT_FOUND"


# ── resolve_by_phone ───────────────────────────────────────────────────────────

def test_resolve_by_phone_success(db, phone_user):
    """전화번호로 수취인 주계좌를 정상 조회합니다."""
    result = resolve_by_phone(db, phone_user.phone)

    assert isinstance(result, ResolvedRecipient)
    assert result.recipient_id is None
    assert result.bank_name == "우리은행"
    assert result.account_number == "1002-111-222333"
    assert result.recipient_name == phone_user.name


def test_resolve_by_phone_user_not_found(db):
    """미가입 전화번호면 TRANSFER_RECIPIENT_NOT_FOUND를 발생시킵니다."""
    with pytest.raises(RecipientError) as exc_info:
        resolve_by_phone(db, "010-0000-0000")

    assert exc_info.value.code == "TRANSFER_RECIPIENT_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_resolve_by_phone_no_primary_account(db):
    """가입 사용자지만 주계좌가 없으면 TRANSFER_RECIPIENT_NOT_FOUND를 발생시킵니다."""
    user_no_account = _make_user(f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}")
    db.add(user_no_account)
    db.commit()

    try:
        with pytest.raises(RecipientError) as exc_info:
            resolve_by_phone(db, user_no_account.phone)

        assert exc_info.value.code == "TRANSFER_RECIPIENT_NOT_FOUND"
    finally:
        db.query(User).filter_by(user_id=user_no_account.user_id).delete()
        db.commit()


# ── resolve_or_create_by_alias ─────────────────────────────────────────────────

def test_resolve_or_create_by_alias_creates_new(db, test_user):
    """존재하지 않는 별칭이면 신규 수취인을 등록하고 반환합니다."""
    alias = f"친구_{uuid.uuid4().hex[:6]}"

    result = resolve_or_create_by_alias(
        db,
        test_user.user_id,
        alias=alias,
        bank_name="신한은행",
        account_number="110-222-333444",
        recipient_name="김철수",
    )

    assert isinstance(result, ResolvedRecipient)
    assert result.recipient_id is not None
    assert result.bank_name == "신한은행"
    assert result.account_number == "110-222-333444"
    assert result.recipient_name == "김철수"

    # DB에 실제로 저장됐는지 확인
    saved = (
        db.query(RegisteredRecipient)
        .filter_by(user_id=test_user.user_id, alias=alias)
        .first()
    )
    assert saved is not None


def test_resolve_or_create_by_alias_returns_existing(db, test_user, registered_recipient):
    """이미 등록된 별칭이면 기존 수취인 정보를 반환합니다."""
    result = resolve_or_create_by_alias(
        db,
        test_user.user_id,
        alias="엄마",
        bank_name="다른은행",        # 기존과 다른 값을 넘겨도
        account_number="999-999-999",
        recipient_name="다른이름",
    )

    # 기존 등록 수취인 정보 그대로 반환
    assert result.recipient_id == registered_recipient.recipient_id
    assert result.bank_name == "국민은행"
    assert result.account_number == "123-456-789012"
    assert result.recipient_name == "홍길동"


# ── match_by_name ──────────────────────────────────────────────────────────────

def test_match_by_name_by_alias(db, test_user, registered_recipient):
    """별칭으로 수취인을 검색합니다."""
    results = match_by_name(db, test_user.user_id, "엄마")

    assert len(results) >= 1
    assert any(r.recipient_id == registered_recipient.recipient_id for r in results)


def test_match_by_name_by_recipient_name(db, test_user, registered_recipient):
    """수취인 실명으로 검색합니다."""
    results = match_by_name(db, test_user.user_id, "홍길동")

    assert len(results) >= 1
    assert any(r.recipient_id == registered_recipient.recipient_id for r in results)


def test_match_by_name_partial(db, test_user, registered_recipient):
    """이름 일부만 입력해도 부분 일치로 검색됩니다."""
    results = match_by_name(db, test_user.user_id, "길")

    assert len(results) >= 1


def test_match_by_name_no_result(db, test_user):
    """매칭 결과가 없으면 빈 리스트를 반환합니다."""
    results = match_by_name(db, test_user.user_id, "존재하지않는이름xyz")

    assert results == []


def test_match_by_name_other_user_isolated(db, test_user, registered_recipient):
    """다른 사용자의 수취인은 검색되지 않습니다."""
    other_uuid = uuid.uuid4()
    results = match_by_name(db, other_uuid, "엄마")

    assert all(r.recipient_id != registered_recipient.recipient_id for r in results)
