"""
backend/tests/test_auto_transfer.py

[이 파일의 역할]
자동이체 기능(features/auto_transfer) 핵심 도메인의 최종 HTTP 통합 테스트입니다.
실제 PostgreSQL(Aiven) DB에 픽스처 데이터를 삽입하고,
POST /api/auto-transfer 파이프라인의 5개 비즈니스 게이트(관문)를 전부 검증합니다.

[5개 비즈니스 게이트 검증 범위]
  1관문 - 수취인 3방향 XOR 스위치 (recipientId / recipientPhone / toAccountNumber)
  2관문 - 출금 계좌 소유권 확인 (타인 계좌 접근 차단)
  3관문 - PIN bcrypt 검증 (AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID)
  4관문 - 약관 동의 확인 (AUTO_ORDER_TERMS_NOT_AGREED)
  5관문 - next_execution_at 계산 + StandingOrder DB 커밋

[실행 방법]
  cd backend
  CRYPTO_NOOP=true pytest tests/test_auto_transfer.py -v

[전제 조건]
  - .env 또는 환경변수에 PostgreSQL 접속 정보(DATABASE_URL) 설정
  - CRYPTO_NOOP=true: shared/crypto.py의 encrypt/decrypt가 평문 패스스루로 동작

[UUID 타입 안전성]
  User.user_id, StandingOrder.user_id, RegisteredRecipient.user_id 는 모두
  PGUUID(as_uuid=True)로 선언되어 Python uuid.UUID 객체를 직접 바인딩합니다.
  Account.account_id, StandingOrder.order_id 는 String(36) 타입이므로 str로 저장합니다.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.standing_order import StandingOrder
from app.models.transaction import Transaction
from app.models.user import User
from app.shared.crypto import encrypt
from datetime import datetime

# ── 테스트 상수 ─────────────────────────────────────────────────────────────────
_TEST_PIN = "000001"
_TEST_PIN_HASH = bcrypt.hashpw(_TEST_PIN.encode(), bcrypt.gensalt()).decode()


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────


def _random_phone() -> str:
    """테스트마다 고유한 전화번호를 생성합니다."""
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

    [삭제 순서 — FK 의존 관계 준수]
    Transaction(FK: auto_order_id → standing_orders)
      → StandingOrder(FK: user_id)
        → RegisteredRecipient(FK: user_id)
          → Account(FK: user_id)
            → User(PK: user_id)
    """
    db = SessionLocal()
    try:
        # Transaction이 StandingOrder를 FK로 참조하므로 먼저 삭제
        db.query(Transaction).filter(
            Transaction.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(StandingOrder).filter(
            StandingOrder.user_id == user_id
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


def _base_payload(from_account_id: str, **kwargs) -> dict:
    """자동이체 등록 기본 페이로드를 반환합니다.

    기본값: amount=50,000 / cycle='monthly' / scheduledDay=15 / password=_TEST_PIN / termsAgreed=True
    **kwargs로 recipientId / recipientPhone / toAccountNumber+bankName+toName 중 하나를 추가합니다.
    """
    return {
        "fromAccountId": str(from_account_id),
        "amount": 50_000,
        "cycle": "monthly",
        "scheduledDay": 15,
        "password": _TEST_PIN,
        "termsAgreed": True,
        **kwargs,
    }


# ── 픽스처 ────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def user_with_account(db: Session):
    """[픽스처] 자동이체 등록자 — 잔액 1,000,000원 / 주계좌 등록 완료

    [암호화 주의]
    Account.account_number는 DB에 AES-256 암호화 상태로 저장해야 합니다.
    CRYPTO_NOOP=true 환경에서는 encrypt()가 평문을 그대로 반환합니다.
    """
    user = User(
        name="자동이체 테스터",
        phone=_random_phone(),
        pin_hash=_TEST_PIN_HASH,
        embedding_vector=None,
    )
    db.add(user)
    db.flush()

    account = Account(
        user_id=user.user_id,
        bank_name="우리은행",
        account_number=encrypt("1002-AUTO-0001"),
        account_type="입출금",
        balance=1_000_000,
        is_primary=True,
    )
    db.add(account)
    db.commit()
    db.refresh(user)
    db.refresh(account)
    yield user, account
    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def registered_recipient(db: Session, user_with_account):
    """[픽스처] 등록 수취인 — REGISTERED 경로 테스트용"""
    user, _ = user_with_account
    r = RegisteredRecipient(
        user_id=user.user_id,
        alias="엄마",
        bank_name="신한은행",
        account_number=encrypt("110-AUTO-RECV"),
        recipient_name="김어머니",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    yield r
    # user_with_account _cleanup()에서 일괄 삭제




@pytest.fixture(scope="module")
def token(client: TestClient, user_with_account):
    """[픽스처] 등록자 JWT 토큰"""
    user, _ = user_with_account
    return _login(client, user.phone)


# ── TestRegisteredMode ────────────────────────────────────────────────────────


class TestRegisteredMode:
    def test_monthly_success(
        self, client, token, user_with_account, registered_recipient, db
    ):
        """REGISTERED + monthly 등록 성공 — DB StandingOrder 생성 확인."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        assert res.json()["success"] is True

        data = res.json()["data"]
        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == data["orderId"]
        ).first()
        assert order is not None
        assert order.status == "active"
        assert order.cycle == "monthly"
        assert order.scheduled_day == 15

    def test_weekly_success(
        self, client, token, user_with_account, registered_recipient
    ):
        """REGISTERED + weekly 등록 성공."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
            cycle="weekly",
            scheduledDow=0,
        )
        del payload["scheduledDay"]
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["cycle"] == "weekly"
        assert data["scheduledDow"] == 0

    def test_response_fields(
        self, client, token, user_with_account, registered_recipient
    ):
        """응답 필드 구조 + accountMasked 마스킹 + nextExecutionAt 형식 검증."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        data = res.json()["data"]

        for field in (
            "orderId", "toName", "bankName", "accountMasked",
            "amount", "cycle", "nextExecutionAt", "status",
        ):
            assert field in data, f"{field} 필드 누락 — AutoTransferResult by_alias=True 기준"

        assert "*" in data["accountMasked"], (
            f"계좌번호 마스킹 미적용: '{data['accountMasked']}'"
        )
        assert data["status"] == "active"
        assert data["amount"] == payload["amount"]
        # nextExecutionAt 은 YYYY-MM-DD 형식이어야 합니다.
        assert len(data["nextExecutionAt"]) == 10


# ── TestDirectMode ────────────────────────────────────────────────────────────


class TestDirectMode:
    def test_direct_success(self, client, token, user_with_account):
        """DIRECT 경로 등록 성공 — RegisteredRecipient 자동 생성 후 StandingOrder 연결."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            toAccountNumber="9999-DIRECT-001",
            bankName="하나은행",
            toName="이영희",
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200

    def test_direct_missing_bank_name_returns_422(
        self, client, token, user_with_account
    ):
        """DIRECT 경로에서 bankName 누락 → XOR 검증 오류 422."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            toAccountNumber="9999-DIRECT-002",
            toName="이영희",
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 422


# ── TestXORValidation ─────────────────────────────────────────────────────────


class TestXORValidation:
    def test_two_methods_returns_422(
        self, client, token, user_with_account, registered_recipient
    ):
        """recipientId + toAccountNumber 동시 입력 → XOR 위반 422."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
            toAccountNumber="9999-XOR-001",
            bankName="하나은행",
            toName="홍길동",
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 422

    def test_no_method_returns_422(self, client, token, user_with_account):
        """수취인 지정 방식 미입력 → XOR 위반 422."""
        _, account = user_with_account
        payload = _base_payload(account.account_id)
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 422


# ── TestFailureCases ──────────────────────────────────────────────────────────


class TestFailureCases:
    def test_wrong_pin_returns_403(
        self, client, token, user_with_account, registered_recipient
    ):
        """PIN 불일치 → AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID 403."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
            password="999999",
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 403
        assert res.json()["code"] == "AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID"

    def test_terms_not_agreed_returns_400(
        self, client, token, user_with_account, registered_recipient
    ):
        """약관 미동의 → AUTO_ORDER_TERMS_NOT_AGREED 400."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
            termsAgreed=False,
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 400
        assert res.json()["code"] == "AUTO_ORDER_TERMS_NOT_AGREED"

    def test_monthly_missing_scheduled_day_returns_422(
        self, client, token, user_with_account, registered_recipient
    ):
        """monthly + scheduledDay 누락 → cycle 검증 오류 422."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )
        del payload["scheduledDay"]
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 422

    def test_no_token_returns_401(self, client):
        """Authorization 헤더 없음 → JWT 인증 실패 401."""
        payload = _base_payload("fake-id", recipientId=str(uuid.uuid4()))
        res = client.post("/api/auto-transfer", json=payload)
        assert res.status_code == 401


# ── TestList ──────────────────────────────────────────────────────────────────


class TestList:
    def test_list_returns_items(self, client, token):
        """목록 조회 성공 — 리스트 형태로 반환."""
        res = client.get("/api/auto-transfer", headers=_auth(token))
        assert res.status_code == 200
        assert isinstance(res.json()["data"], list)

    def test_filter_by_active(self, client, token):
        """status=active 필터 — 반환된 모든 항목이 active 상태."""
        res = client.get(
            "/api/auto-transfer",
            params={"status": "active"},
            headers=_auth(token),
        )
        assert res.status_code == 200
        for item in res.json()["data"]:
            assert item["status"] == "active"


# ── TestStatusUpdate ──────────────────────────────────────────────────────────


class TestStatusUpdate:
    def _register(self, client, token, account_id, recipient_id) -> str:
        """테스트용 자동이체를 등록하고 orderId를 반환합니다."""
        payload = _base_payload(
            account_id,
            recipientId=str(recipient_id),
        )
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        return res.json()["data"]["orderId"]

    def test_pause_and_resume(
        self, client, token, user_with_account, registered_recipient, db
    ):
        """active → paused → active 상태 전환 성공."""
        _, account = user_with_account
        order_id = self._register(
            client, token, account.account_id, registered_recipient.recipient_id
        )

        res = client.patch(
            f"/api/auto-transfer/{order_id}/status",
            json={"status": "paused"},
            headers=_auth(token),
        )
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "paused"

        # paused 상태에서는 next_execution_at이 null이어야 합니다.
        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == order_id
        ).first()
        db.refresh(order)
        assert order.next_execution_at is None

        res = client.patch(
            f"/api/auto-transfer/{order_id}/status",
            json={"status": "active"},
            headers=_auth(token),
        )
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "active"

    def test_cancel_is_irreversible(
        self, client, token, user_with_account, registered_recipient
    ):
        """cancelled → active 시도 → AUTO_ORDER_STATUS_INVALID 400."""
        _, account = user_with_account
        order_id = self._register(
            client, token, account.account_id, registered_recipient.recipient_id
        )

        client.patch(
            f"/api/auto-transfer/{order_id}/status",
            json={"status": "cancelled"},
            headers=_auth(token),
        )
        res = client.patch(
            f"/api/auto-transfer/{order_id}/status",
            json={"status": "active"},
            headers=_auth(token),
        )
        assert res.status_code == 400
        assert res.json()["code"] == "AUTO_ORDER_STATUS_INVALID"

    def test_not_found_returns_404(self, client, token):
        """없는 orderId → AUTO_ORDER_NOT_FOUND 404."""
        res = client.patch(
            f"/api/auto-transfer/{uuid.uuid4()}/status",
            json={"status": "paused"},
            headers=_auth(token),
        )
        assert res.status_code == 404
        assert res.json()["code"] == "AUTO_ORDER_NOT_FOUND"


# ── TestMemo ──────────────────────────────────────────────────────────────────


class TestMemo:
    def test_save_memo_success(
        self, client, token, user_with_account, registered_recipient, db
    ):
        """자동이체 메모(label) 저장 성공 — DB 반영 확인."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )
        reg = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        order_id = reg.json()["data"]["orderId"]

        res = client.post(
            f"/api/auto-transfer/{order_id}/memo",
            json={"transferNote": "월세"},
            headers=_auth(token),
        )
        assert res.status_code == 200
        assert res.json()["data"]["transferNote"] == "월세"

        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == order_id
        ).first()
        db.refresh(order)
        assert order.transfer_note == "월세"

    def test_save_memo_not_found_returns_404(self, client, token):
        """없는 orderId → AUTO_ORDER_NOT_FOUND 404."""
        res = client.post(
            f"/api/auto-transfer/{uuid.uuid4()}/memo",
            json={"transferNote": "공과금"},
            headers=_auth(token),
        )
        assert res.status_code == 404
        assert res.json()["code"] == "AUTO_ORDER_NOT_FOUND"


# ── TestExecute ───────────────────────────────────────────────────────────────


class TestExecute:
    def _register_and_set_past(
        self,
        client,
        token,
        account_id,
        recipient_id,
        db,
    ) -> str:
        """자동이체 등록 후 next_execution_at을 과거로 강제 설정하여 즉시 실행 대상으로 만듭니다."""
        payload = _base_payload(str(account_id), recipientId=str(recipient_id))
        reg = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        order_id = reg.json()["data"]["orderId"]

        # next_execution_at을 오늘 자정 이전으로 설정해 실행 대상으로 만듦
        from datetime import datetime
        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == order_id
        ).first()
        order.next_execution_at = datetime(2000, 1, 1)
        db.commit()
        return order_id

    def test_execute_success(
        self, client, token, user_with_account, registered_recipient, db
    ):
        """실행일이 된 자동이체 성공 — Transaction(completed) 생성 + 잔액 차감 확인."""
        user, account = user_with_account
        before_balance = db.query(Account).filter(
            Account.account_id == account.account_id
        ).first().balance

        order_id = self._register_and_set_past(
            client, token, account.account_id, registered_recipient.recipient_id, db
        )

        res = client.post("/api/auto-transfer/execute", headers=_auth(token))
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["success"] >= 1

        # Transaction 생성 확인
        from app.models.transaction import Transaction
        tx = db.query(Transaction).filter(
            Transaction.auto_order_id == order_id,
            Transaction.tx_type == "auto_transfer",
        ).first()
        db.refresh(tx)
        assert tx is not None
        assert tx.status == "completed"

        # 잔액 차감 확인
        db.refresh(account)
        assert account.balance == before_balance - 50_000

        # next_execution_at 갱신 확인
        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == order_id
        ).first()
        db.refresh(order)
        assert order.next_execution_at > datetime(2000, 1, 1)

    def test_execute_no_due_orders(self, client, token):
        """실행 예정 건 없음 → total=0 반환."""
        res = client.post("/api/auto-transfer/execute", headers=_auth(token))
        assert res.status_code == 200
        assert res.json()["data"]["total"] == 0

    def test_execute_insufficient_balance(
        self, client, token, user_with_account, registered_recipient, db
    ):
        """잔액 부족 → Transaction(failed) 생성, standing_order는 active 유지."""
        user, account = user_with_account

        # 잔액을 이체 금액보다 작게 설정
        account.balance = 100
        db.commit()

        order_id = self._register_and_set_past(
            client, token, account.account_id, registered_recipient.recipient_id, db
        )

        res = client.post("/api/auto-transfer/execute", headers=_auth(token))
        assert res.status_code == 200
        # failed 카운터는 예외 발생 건수 — 잔액 부족은 예외 없이 Transaction(failed) 생성
        assert res.json()["data"]["total"] >= 1

        tx = db.query(Transaction).filter(
            Transaction.auto_order_id == order_id,
            Transaction.tx_type == "auto_transfer",
        ).first()
        db.refresh(tx)
        assert tx is not None
        assert tx.status == "failed"

        # standing_order는 active 유지
        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == order_id
        ).first()
        db.refresh(order)
        assert order.status == "active"

        # 잔액 원복
        account.balance = 1_000_000
        db.commit()

    def test_execute_no_token_returns_401(self, client):
        """Authorization 없음 → 401."""
        res = client.post("/api/auto-transfer/execute")
        assert res.status_code == 401
