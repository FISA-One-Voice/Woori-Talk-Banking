"""
backend/tests/test_transfer.py

[이 파일의 역할]
이체 기능(features/transfer) 핵심 도메인의 최종 HTTP 통합 테스트입니다.
실제 PostgreSQL(Aiven) DB에 픽스처 데이터를 삽입하고,
POST /api/transfer 파이프라인의 6개 비즈니스 게이트(관문)를 전부 검증합니다.

[6개 비즈니스 게이트 검증 범위]
  1관문 - 음성 임베딩 등록 여부 확인 (embedding_vector IS NOT NULL)
  2관문 - ASV 화자 검증 httpx 호출 (is_same_speaker 값 기반 분기, mock 대체)
  3관문 - idempotency_key 중복 전표 차단 (동일 key 2회 요청 → 기존 결과 반환)
  4관문 - 수취인 3방향 XOR 스위치 타워 (recipient_id / phone / direct 정확히 1개)
  5관문 - 출금 계좌 소유권 확인 + 잔액 부족 차단 (INSUFFICIENT_BALANCE)
  6관문 - 잔액 차감 + AES-256 계좌번호 암호화 후 Transaction DB 커밋

[실행 방법]
  cd backend
  CRYPTO_NOOP=true pytest tests/test_transfer.py -v

[전제 조건]
  - .env 또는 환경변수에 PostgreSQL 접속 정보(DATABASE_URL) 설정
  - CRYPTO_NOOP=true: shared/crypto.py의 encrypt/decrypt가 평문 패스스루로 동작 (테스트 전용)
  - ASV 서버 실제 호출 없음: httpx.AsyncClient를 MagicMock으로 대체

[UUID 타입 안전성 보장]
  User.user_id, Transaction.user_id, RegisteredRecipient.user_id 는 모두
  PGUUID(as_uuid=True)로 선언되어 Python uuid.UUID 객체를 직접 바인딩합니다.
  Account.account_id, Transaction.tx_id, RegisteredRecipient.recipient_id 는
  String(36) 타입이므로 str(uuid.uuid4())로 저장합니다.
  _cleanup() 함수는 uuid.UUID 객체를 PGUUID 컬럼에 직접 비교하여 타입 충돌 없이 정리합니다.
"""

import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.transaction import Transaction
from app.models.user import User
from app.shared.crypto import encrypt

# ── 테스트 상수 ─────────────────────────────────────────────────────────────────
# 모든 테스트 픽스처 사용자가 공유하는 고정 PIN 및 bcrypt 해시
_TEST_PIN = "000001"
_TEST_PIN_HASH = bcrypt.hashpw(_TEST_PIN.encode(), bcrypt.gensalt()).decode()

# ASV 검증 모킹에 사용할 가짜 WAV 오디오 바이트 (RIFF/WAV 헤더 형식)
_FAKE_AUDIO = b"RIFF$\x00\x00\x00WAVEfmt "

# ── ASV 서버 Mock 패치 경로 ─────────────────────────────────────────────────────
# service.py 최상단이 `import httpx` 형태이므로 아래 경로가 정확합니다.
# 만약 `from httpx import AsyncClient`로 임포트했다면
# "app.features.transfer.service.AsyncClient" 로 변경해야 합니다.
ASV_PATCH = "app.features.transfer.service.httpx.AsyncClient"


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────


def _random_phone() -> str:
    """테스트마다 고유한 전화번호를 생성합니다.

    users.phone 컬럼에 UNIQUE 제약이 없더라도, 여러 테스트 모듈이 동시에 실행되거나
    이전 실행에서 cleanup이 실패했을 때 충돌하지 않도록 UUID 기반 랜덤값을 사용합니다.
    """
    return f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}"


def _auth(token: str) -> dict:
    """Authorization Bearer 헤더 딕셔너리를 반환합니다."""
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, phone: str) -> str:
    """지정 전화번호로 로그인하여 accessToken 문자열을 반환합니다."""
    res = client.post("/api/users/login", json={"phone": phone, "pin": _TEST_PIN})
    assert res.status_code == 200, (
        f"픽스처 로그인 실패 — phone={phone}, 응답: {res.json()}"
    )
    return res.json()["data"]["accessToken"]


def _cleanup(user_id: uuid.UUID) -> None:
    """테스트 사용자 및 관련 레코드를 DB에서 완전 삭제합니다.

    [삭제 순서 — 외래키(FK) 의존 관계 준수]
    Transaction(FK: user_id, from_account_id, recipient_id)
      → RegisteredRecipient(FK: user_id)
        → Account(FK: user_id)
          → User(PK: user_id)

    [UUID 타입 안전성]
    user_id는 Python uuid.UUID 객체입니다.
    User/Transaction/RegisteredRecipient/Account 모두 user_id 컬럼이
    PGUUID(as_uuid=True)로 선언되어 있어 uuid.UUID 객체를 직접 비교할 수 있습니다.

    synchronize_session=False: 현재 세션 식별 맵과의 동기화를 건너뛰어 성능을 높이고,
    세션 간 충돌(OperationalError)을 방지합니다.
    """
    db = SessionLocal()
    try:
        db.query(Transaction).filter(
            Transaction.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(RegisteredRecipient).filter(
            RegisteredRecipient.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(Account).filter(
            Account.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(User).filter(
            User.user_id == user_id
        ).delete(synchronize_session=False)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _asv_mock(is_same_speaker: bool) -> MagicMock:
    """httpx.AsyncClient의 비동기 컨텍스트 매니저를 흉내 내는 Mock을 반환합니다.

    service.py 코드 구조:
        async with httpx.AsyncClient() as client:   # __aenter__ → mock_client 반환
            resp = await client.post(...)           # post() → mock_resp 반환
            verify_result = resp.json()             # {"is_same_speaker": ...}

    Args:
        is_same_speaker: True이면 2관문 통과, False이면 VOICE_VERIFICATION_FAILED(403)
    """
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "is_same_speaker": is_same_speaker,
        "similarity_score": 0.95 if is_same_speaker else 0.3,
    }

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


def _post_transfer(
    client: TestClient,
    token: str,
    payload: dict,
    audio: bytes = _FAKE_AUDIO,
):
    """ASV를 성공(is_same_speaker=True)으로 모킹하여 POST /api/transfer를 호출합니다.

    multipart/form-data 형식:
      - files["audio"]          : WAV 파일 바이너리
      - data["transfer_data"]   : TransferRequest JSON 문자열
    """
    with patch(ASV_PATCH, return_value=_asv_mock(True)):
        return client.post(
            "/api/transfer",
            files={"audio": ("t.wav", io.BytesIO(audio), "audio/wav")},
            data={"transfer_data": json.dumps(payload)},
            headers=_auth(token),
        )


def _base_payload(account_id: str, **kwargs) -> dict:
    """이체 요청 기본 페이로드를 반환합니다.

    기본 amount=50,000 / idempotencyKey=새 UUID.
    **kwargs로 recipientId / recipientPhone / toAccountNumber+bankName+toName 중 하나를 추가합니다.
    kwargs에 idempotencyKey를 넘기면 기본값을 덮어씁니다.
    """
    return {
        "fromAccountId": str(account_id),
        "amount": 50_000,
        "idempotencyKey": str(uuid.uuid4()),
        **kwargs,
    }


# ── 픽스처 ────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sender(db: Session):
    """[픽스처] 이체 발신자 — 잔액 1,000,000원 / 음성 임베딩 192차원 등록 완료

    이 픽스처가 검증하는 게이트:
      1관문: embedding_vector=[0.1]*192 로 VOICE_NOT_REGISTERED 방어
      5관문: balance=1,000,000 으로 소액 이체(50,000 × 다수) 모두 통과 가능

    [암호화 주의]
    Account.account_number는 DB에 AES-256 암호화 상태로 저장해야 합니다.
    CRYPTO_NOOP=true 환경에서는 encrypt()가 평문을 그대로 반환하여 테스트가 투명하게 동작합니다.
    """
    user = User(
        name="이체 테스터",
        phone=_random_phone(),
        pin_hash=_TEST_PIN_HASH,
        embedding_vector=[0.1] * 192,
    )
    db.add(user)
    db.flush()  # PK(user_id) 생성, 아직 commit 안 함

    account = Account(
        user_id=user.user_id,
        bank_name="우리은행",
        account_number=encrypt("1002-100-111111"),  # 암호화 저장 필수
        account_type="입출금",
        balance=1_000_000,
        is_primary=True,
    )
    db.add(account)
    db.commit()
    db.refresh(user)
    db.refresh(account)

    yield user, account

    # 모듈 내 모든 테스트 완료 후 DB 정리 (FK 순서 준수)
    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def receiver(db: Session):
    """[픽스처] 이체 수신자 — Shinhan Bank 주계좌(is_primary=True) / 잔액 0원

    이 픽스처가 검증하는 게이트:
      4관문 PHONE 모드: resolve_by_phone(db, phone) → is_primary=True 계좌 자동 조회
    """
    user = User(
        name="수신자 테스터",
        phone=_random_phone(),
        pin_hash=_TEST_PIN_HASH,
        embedding_vector=[0.2] * 192,
    )
    db.add(user)
    db.flush()

    db.add(
        Account(
            user_id=user.user_id,
            bank_name="신한은행",
            account_number=encrypt("110-200-222222"),
            account_type="입출금",
            balance=0,
            is_primary=True,
        )
    )
    db.commit()
    db.refresh(user)

    yield user

    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def registered_recipient(db: Session, sender):
    """[픽스처] 발신자의 즐겨찾기 등록 수취인 (Kakao Bank)

    이 픽스처가 검증하는 게이트:
      4관문 REGISTERED 모드: resolve_by_id(db, user_uuid, recipient_id) → RegisteredRecipient 조회

    [UniqueConstraint 안전성]
    registered_recipients 테이블은 (user_id, alias)에 유니크 제약이 있습니다.
    sender가 _random_phone()으로 매 실행마다 새 user를 생성하므로 alias 충돌이 없습니다.

    [암호화 주의]
    RegisteredRecipient.account_number도 encrypt()로 암호화 저장해야 합니다.
    recipients/service.py의 resolve_by_id()가 내부에서 decrypt()를 호출합니다.
    """
    sender_user, _ = sender
    r = RegisteredRecipient(
        user_id=sender_user.user_id,
        alias="친구",
        bank_name="카카오뱅크",
        account_number=encrypt("3333-02-3333333"),
        recipient_name="김철수",
    )
    db.add(r)
    db.commit()
    db.refresh(r)

    yield r
    # registered_recipient 레코드는 sender _cleanup()에서 일괄 삭제됩니다


@pytest.fixture(scope="module")
def sender_token(client: TestClient, sender):
    """[픽스처] 발신자 JWT accessToken

    scope="module": 이 모듈 내 모든 테스트 메서드가 동일 토큰을 재사용합니다.
    JWT 만료 시간이 테스트 실행 시간보다 길어야 합니다 (기본 30분 이상 권장).
    """
    sender_user, _ = sender
    return _login(client, sender_user.phone)


# ── TestRegisteredMode ────────────────────────────────────────────────────────


class TestRegisteredMode:
    """4관문 — REGISTERED 모드: recipient_id(UUID)를 이용한 등록 수취인 이체

    이 클래스가 다루는 비즈니스 게이트:
      1~2관문(임베딩/ASV) → 3관문(멱등성 신규 key) → 4관문(recipient_id) →
      5관문(잔액 충분) → 6관문(커밋)
    """

    def test_transfer_success(
        self,
        client: TestClient,
        sender_token: str,
        sender,
        registered_recipient: RegisteredRecipient,
        db: Session,
    ):
        """등록 수취인 ID로 이체가 정상 완료되고 DB에 completed 상태 거래 레코드가 생성됩니다."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )

        res = _post_transfer(client, sender_token, payload)

        assert res.status_code == 200
        assert res.json()["success"] is True

        # 6관문 완료 후 DB에 거래 레코드가 실제로 생성되었는지 검증
        tx = (
            db.query(Transaction)
            .filter(Transaction.idempotency_key == payload["idempotencyKey"])
            .first()
        )
        assert tx is not None, "이체 완료 후 Transaction 레코드가 DB에 없습니다"
        assert tx.status == "completed"

    def test_response_fields(
        self,
        client: TestClient,
        sender_token: str,
        sender,
        registered_recipient: RegisteredRecipient,
    ):
        """응답 data의 필드 구조와 계좌번호 보안 마스킹 규칙을 검증합니다.

        [검증 항목]
        - TransferResult 스키마가 by_alias=True로 직렬화되어 camelCase 키 반환
        - 필수 필드: txId, toName, bankName, accountMasked, amount
        - 보안 규칙: accountMasked 값에 반드시 '*' 마스킹 문자 포함
          (뒷 4자리만 유지, 앞은 모두 '*' 처리: "3333-02-3333333" → "***********333")

        [주의] 응답 필드명은 schema.py TransferResult 기준 'accountMasked'입니다.
        schema.py의 account_masked 필드가 alias="accountMasked"이며,
        router.py에서 result.model_dump(by_alias=True)를 적용하므로 camelCase로 반환됩니다.
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )

        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200

        data = res.json()["data"]

        # ── 필수 필드 존재 여부 (TransferResult 스키마 camelCase alias 기준) ──
        assert "txId" in data, "txId 필드 누락 — TransferResult.tx_id (alias=txId)"
        assert "toName" in data, "toName 필드 누락 — TransferResult.to_name"
        assert "bankName" in data, "bankName 필드 누락 — TransferResult.bank_name"
        assert "accountMasked" in data, (
            "accountMasked 필드 누락 — TransferResult.account_masked (alias=accountMasked)\n"
            "toAccountNumber가 아닌 accountMasked가 올바른 필드명입니다."
        )
        assert "amount" in data, "amount 필드 누락 — TransferResult.amount"

        # ── 보안 마스킹 규칙: accountMasked에 반드시 '*' 포함 ─────────────────
        assert "*" in data["accountMasked"], (
            f"계좌번호 마스킹 미적용: '{data['accountMasked']}'\n"
            "service.py _mask_account()가 뒷 4자리 외 모두 '*' 처리해야 합니다."
        )

        # ── 이체 금액 일치 ────────────────────────────────────────────────────
        assert data["amount"] == payload["amount"]

        # ── txId가 비어있지 않음 ──────────────────────────────────────────────
        assert len(data["txId"]) > 0


# ── TestPhoneMode ─────────────────────────────────────────────────────────────


class TestPhoneMode:
    """4관문 — PHONE 모드: recipientPhone으로 수신자의 주계좌(is_primary=True)를 자동 조회하여 이체"""

    def test_transfer_via_primary_account(
        self,
        client: TestClient,
        sender_token: str,
        sender,
        receiver,
    ):
        """수신자 전화번호 입력 시 is_primary=True 계좌로 자동 라우팅하여 이체를 완료합니다.

        검증 게이트: 4관문 → resolve_by_phone(db, phone) → primary_account 조회 성공
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientPhone=receiver.phone,
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200

    def test_unregistered_phone_lookup_returns_404(
        self,
        client: TestClient,
        sender_token: str,
    ):
        """미가입 전화번호를 수취인 조회 API에 요청하면 TRANSFER_RECIPIENT_NOT_FOUND 404를 반환합니다.

        검증 게이트: GET /api/transfer/lookup/phone → recipients/service.resolve_by_phone()
                    → target_user is None → RecipientError(TRANSFER_RECIPIENT_NOT_FOUND, 404)
        """
        res = client.get(
            "/api/transfer/lookup/phone",
            params={"phone": "010-0000-0000"},
            headers=_auth(sender_token),
        )
        assert res.status_code == 404
        assert res.json()["code"] == "TRANSFER_RECIPIENT_NOT_FOUND"


# ── TestDirectMode ────────────────────────────────────────────────────────────


class TestDirectMode:
    """4관문 — DIRECT 모드: toAccountNumber + bankName + toName 직접 입력 이체"""

    def test_direct_entry_success(
        self,
        client: TestClient,
        sender_token: str,
        sender,
    ):
        """계좌번호·은행명·수취인명을 직접 입력하면 ResolvedRecipient를 생성하고 이체를 완료합니다.

        검증 게이트: 4관문 DIRECT 분기 → else 블록 → ResolvedRecipient 직접 생성
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="269-910111-22222",
            bankName="하나은행",
            toName="이영희",
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200

    def test_direct_missing_bank_name_returns_422(
        self,
        client: TestClient,
        sender_token: str,
        sender,
    ):
        """toAccountNumber 입력 시 bankName 미제공이면 Pydantic XOR 검증 오류를 반환합니다.

        검증 게이트: TransferRequest.validate_recipient_xor()
                    → toAccountNumber 있는데 bank_name 없음 → ValueError 발생

        [주의] router.py에서 model_validate_json()을 수동 호출하므로,
        발생하는 pydantic.ValidationError 처리 방식은 FastAPI 버전에 따라 다릅니다.
        FastAPI가 이를 RequestValidationError로 변환하면 422,
        그렇지 않으면 500이 반환될 수 있습니다.
        현재 프로젝트(FastAPI 0.136.1)에서 422를 기대합니다.
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="269-910111-33333",
            toName="이영희",
            # bankName 의도적으로 누락 — XOR 검증 실패 유발
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 422


# ── TestXORValidation ─────────────────────────────────────────────────────────


class TestXORValidation:
    """4관문 — XOR 검증: 수취인 지정 방식이 1개 초과/미만이면 422를 반환합니다.

    TransferRequest.validate_recipient_xor() 검증:
      len(provided) != 1 → ValueError → pydantic.ValidationError → 422(또는 500)

    [중요] XOR 오류는 router.py에서 model_validate_json()을 통해 파싱 시 발생합니다.
    FastAPI가 내부 handler에서 발생한 pydantic.ValidationError를 422로 처리하는지는
    FastAPI 버전 및 설정에 따라 다를 수 있습니다.
    """

    def test_two_methods_returns_422(
        self,
        client: TestClient,
        sender_token: str,
        sender,
        receiver,
        registered_recipient: RegisteredRecipient,
    ):
        """recipientId와 recipientPhone을 동시에 입력하면 422 오류를 반환합니다.

        검증: len(provided) == 2 → XOR 위반 → ValidationError
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientId=str(registered_recipient.recipient_id),
            recipientPhone=receiver.phone,
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 422

    def test_no_method_returns_422(
        self,
        client: TestClient,
        sender_token: str,
        sender,
    ):
        """수취인 지정 방식(recipientId/recipientPhone/toAccountNumber) 미입력 시 422를 반환합니다.

        검증: len(provided) == 0 → XOR 위반 → ValidationError
        """
        _, from_account = sender
        payload = _base_payload(from_account.account_id)  # 수취인 방식 없음
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 422


# ── TestIdempotency ───────────────────────────────────────────────────────────


class TestIdempotency:
    """3관문 — 멱등성: 동일 idempotency_key 중복 요청을 차단하고 기존 결과를 반환합니다."""

    def test_same_key_twice_one_record(
        self,
        client: TestClient,
        sender_token: str,
        sender,
        db: Session,
    ):
        """동일한 idempotency_key로 두 번 요청하면 DB 레코드는 1건만 생성되고 txId가 동일합니다.

        [시나리오]
        1차 요청: 신규 key → 6관문까지 통과 → Transaction 생성 + txId 반환
        2차 요청: 동일 key → 3관문에서 existing_tx 감지 → 기존 TransferResult 즉시 반환 (잔액 차감 없음)

        [검증 항목]
        - res1.json()["data"]["txId"] == res2.json()["data"]["txId"]
        - DB Transaction count by idempotency_key == 1 (중복 레코드 없음)

        [DB 세션 주의]
        route handler는 get_db()로 별도 세션을 열어 commit합니다.
        이 테스트의 db(픽스처 세션)는 별개 세션이지만,
        SQLAlchemy가 새 쿼리 실행 시 DB에서 직접 읽어오므로 committed 데이터를 볼 수 있습니다.
        """
        _, from_account = sender
        idempotency_key = str(uuid.uuid4())

        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="1002-400-444444",
            bankName="우리은행",
            toName="멱등성 테스터",
            idempotencyKey=idempotency_key,  # _base_payload 기본값을 덮어씁니다
        )

        res1 = _post_transfer(client, sender_token, payload)
        res2 = _post_transfer(client, sender_token, payload)

        assert res1.status_code == 200, f"1차 요청 실패: {res1.json()}"
        assert res2.status_code == 200, f"2차 요청 실패: {res2.json()}"

        # 두 응답의 txId가 동일해야 합니다 (동일 거래 반환)
        tx_id_1 = res1.json()["data"]["txId"]
        tx_id_2 = res2.json()["data"]["txId"]
        assert tx_id_1 == tx_id_2, (
            f"멱등성 위반: 동일 key인데 다른 txId 반환 ({tx_id_1} != {tx_id_2})"
        )

        # DB에 동일 idempotency_key 거래가 정확히 1건만 있어야 합니다
        count = (
            db.query(Transaction)
            .filter(Transaction.idempotency_key == idempotency_key)
            .count()
        )
        assert count == 1, f"멱등성 위반: DB에 중복 레코드 {count}건 존재"


# ── TestFailureCases ──────────────────────────────────────────────────────────


class TestFailureCases:
    """실패 시나리오: 2관문 ASV 실패, 5관문 잔액 부족, JWT 인증 없음"""

    def test_asv_failed_returns_403(
        self,
        client: TestClient,
        sender_token: str,
        sender,
    ):
        """ASV 서버가 is_same_speaker=False를 반환하면 VOICE_VERIFICATION_FAILED 403을 반환합니다.

        검증 게이트: 2관문 — verify_result["is_same_speaker"] is False
                    → TransferError(VOICE_VERIFICATION_FAILED, 403)

        [Mock 전략]
        patch(ASV_PATCH, return_value=_asv_mock(False)) 로 httpx.AsyncClient 클래스 자체를 교체합니다.
        컨텍스트 매니저(__aenter__)가 mock_client를 반환하고,
        mock_client.post()가 is_same_speaker=False JSON을 반환합니다.
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="1002-500-555555",
            bankName="우리은행",
            toName="위조자",
        )

        with patch(ASV_PATCH, return_value=_asv_mock(False)):
            res = client.post(
                "/api/transfer",
                files={"audio": ("t.wav", io.BytesIO(_FAKE_AUDIO), "audio/wav")},
                data={"transfer_data": json.dumps(payload)},
                headers=_auth(sender_token),
            )

        assert res.status_code == 403
        assert res.json()["code"] == "VOICE_VERIFICATION_FAILED"

    def test_insufficient_balance_returns_400(
        self,
        client: TestClient,
        sender_token: str,
        sender,
    ):
        """잔액을 초과하는 금액을 이체 시도하면 INSUFFICIENT_BALANCE 400을 반환합니다.

        검증 게이트: 5관문 — from_account.balance < data.amount
                    → TransferError(INSUFFICIENT_BALANCE, 400)

        sender 초기 잔액: 1,000,000원
        이전 테스트들의 누적 차감 후에도 잔액 > 0이므로 99,000,000 > 잔액 → 400 보장
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="1002-600-666666",
            bankName="우리은행",
            toName="대금 테스터",
            amount=99_000_000,  # 1,000,000원 잔액 대비 압도적으로 큰 금액
        )
        res = _post_transfer(client, sender_token, payload)

        assert res.status_code == 400
        assert res.json()["code"] == "INSUFFICIENT_BALANCE"

    def test_no_token_returns_401(
        self,
        client: TestClient,
        sender,
    ):
        """Authorization 헤더 없이 이체 요청 시 JWT 인증 미들웨어가 401을 반환합니다.

        검증 게이트: get_current_user_id() Depends → 토큰 없음 → 401
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="1002-700-777777",
            bankName="우리은행",
            toName="테스트",
        )
        # Authorization 헤더 의도적으로 누락 — headers 파라미터 미전달
        res = client.post(
            "/api/transfer",
            files={"audio": ("t.wav", io.BytesIO(_FAKE_AUDIO), "audio/wav")},
            data={"transfer_data": json.dumps(payload)},
        )
        assert res.status_code == 401
