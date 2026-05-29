"""이체 HTTP 엔드포인트 통합 테스트.

검증 범위:
    - POST /api/transfer/   : 이체 실행, 멱등성(completed/failed), 잔액 부족, 형식 오류
    - POST /api/transfer/{tx_id}/memo  : 메모 업데이트 성공 / 트랜잭션 없음
    - GET  /api/transfer/recent        : 최근 수취인 목록, 인증 없는 요청(401)

실행:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_transfer_api.py -v
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — Base.metadata에 모든 테이블 등록
from app.core.jwt_utils import get_current_user_id
from app.main import app
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.transaction import Transaction
from app.models.user import User

# ── 고정 테스트 식별자 ──────────────────────────────────────────────────────────
# service 테스트와 UUID 충돌 방지를 위해 다른 값 사용
_USER_UUID = uuid.UUID("11111111-2222-3333-4444-555555555555")
_USER_ID = str(_USER_UUID)
_ACCOUNT_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"


# ── 공통 픽스처 ────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def patch_for_update(monkeypatch):
    """SQLite 호환을 위해 SELECT FOR UPDATE를 no-op으로 패치."""
    from sqlalchemy.orm import Query

    monkeypatch.setattr(Query, "with_for_update", lambda self, **kw: self)


@pytest.fixture(scope="module")
def api_setup(db: Session):
    """모듈 공유 테스트 데이터: User + Account(잔액 5M).
    API 테스트가 실제 DB를 읽으므로 PostgreSQL에 데이터를 커밋한다.

    사전 정리: 이전 실행에서 teardown이 실패한 경우 잔류 데이터를 제거한다.
    """
    # 이전 실행 잔류 데이터 정리
    db.query(Transaction).filter(Transaction.user_id == _USER_UUID).delete()
    db.query(RegisteredRecipient).filter(RegisteredRecipient.user_id == _USER_UUID).delete()
    db.query(Account).filter(Account.user_id == _USER_UUID).delete()
    db.query(User).filter(User.user_id == _USER_UUID).delete()
    db.commit()

    user = User(
        user_id=_USER_UUID,
        name="API이체테스터",
        phone="01099993001",
        pin_hash="x",
    )
    account = Account(
        account_id=_ACCOUNT_ID,
        user_id=_USER_UUID,
        bank_name="우리은행",
        account_number="12345678905678",
        account_type="입출금",
        balance=5_000_000,
        is_primary=True,
    )
    db.add_all([user, account])
    db.commit()

    yield

    # 모듈 종료 시 정리
    db.query(Transaction).filter(Transaction.user_id == _USER_UUID).delete()
    db.query(RegisteredRecipient).filter(RegisteredRecipient.user_id == _USER_UUID).delete()
    db.query(Account).filter(Account.user_id == _USER_UUID).delete()
    db.query(User).filter(User.user_id == _USER_UUID).delete()
    db.commit()


@pytest.fixture(scope="module")
def authed_client(api_setup):
    """get_current_user_id를 오버라이드해 JWT 로그인 없이 특정 user_id로 고정한 TestClient.
    실제 DB는 그대로 사용 (get_db 오버라이드 없음).
    """
    app.dependency_overrides[get_current_user_id] = lambda: _USER_ID
    with TestClient(app) as c:
        yield c
    # 다른 테스트 모듈에 영향이 없도록 오버라이드 해제
    app.dependency_overrides.pop(get_current_user_id, None)


# ── 인증 미적용 요청 테스트 (authed_client 활성화 전에 실행) ───────────────────
def test_unauthorized_access(client: TestClient):
    """[인증 없는 요청] Authorization 헤더 없이 API 호출 시 → 401 Unauthorized 반환.
    이 테스트는 authed_client 픽스처가 아직 활성화되지 않은 시점에 실행되어야 한다.
    """
    resp = client.get("/api/transfer/recent")
    assert resp.status_code == 401


# ── TestCreateTransferAPI ──────────────────────────────────────────────────────
class TestCreateTransferAPI:
    def test_success(self, authed_client: TestClient, db: Session):
        """[이체 성공] 유효한 요청 시 → 200, success=True, data.status=completed."""
        key = str(uuid.uuid4())
        resp = authed_client.post(
            "/api/transfer/",
            json={
                "recipient": "12345678901",
                "bankName": "하나은행",
                "amount": 5_000,
                "idempotencyKey": key,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "completed"
        assert "txId" in body["data"]

        # 테스트 데이터 정리
        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_duplicate_completed(self, authed_client: TestClient, db: Session):
        """[멱등성 - completed 재요청] 동일 idempotencyKey로 2번 요청 시
        → 두 번 모두 200을 반환하고, txId가 동일해야 한다 (재출금 없음)."""
        key = str(uuid.uuid4())

        # 첫 번째 요청
        resp1 = authed_client.post(
            "/api/transfer/",
            json={"recipient": "12345678901", "bankName": "하나은행", "amount": 5_000, "idempotencyKey": key},
        )
        assert resp1.status_code == 200
        tx_id_first = resp1.json()["data"]["txId"]

        # 동일 key로 두 번째 요청 → 기존 영수증 재반환
        resp2 = authed_client.post(
            "/api/transfer/",
            json={"recipient": "12345678901", "bankName": "하나은행", "amount": 5_000, "idempotencyKey": key},
        )
        assert resp2.status_code == 200
        # 새 트랜잭션이 아닌 기존 txId 반환
        assert resp2.json()["data"]["txId"] == tx_id_first

        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_insufficient_balance(self, authed_client: TestClient, db: Session):
        """[잔액 부족] 이체 금액이 현재 잔액을 크게 초과하는 경우 → 400 INSUFFICIENT_BALANCE."""
        key = str(uuid.uuid4())
        resp = authed_client.post(
            "/api/transfer/",
            json={
                "recipient": "12345678901",
                "bankName": "하나은행",
                "amount": 99_999_999,  # 잔액(5,000,000)을 훨씬 초과
                "idempotencyKey": key,
            },
        )

        assert resp.status_code == 400
        assert resp.json()["code"] == "INSUFFICIENT_BALANCE"

        # 실패로 커밋된 트랜잭션 정리
        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_invalid_format(self, authed_client: TestClient):
        """[계좌번호 형식 오류] 숫자가 아닌 계좌번호 입력 시 → 400 INVALID_ACCOUNT_FORMAT."""
        resp = authed_client.post(
            "/api/transfer/",
            json={
                "recipient": "abc",  # 유효하지 않은 형식
                "bankName": "하나은행",
                "amount": 1_000,
                "idempotencyKey": str(uuid.uuid4()),
            },
        )

        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_ACCOUNT_FORMAT"


# ── TestMemoAPI ────────────────────────────────────────────────────────────────
class TestMemoAPI:
    def test_success(self, authed_client: TestClient, db: Session):
        """[메모 업데이트 성공] 본인 txId에 메모 입력 시 → 200, data.memo에 값이 반영된다."""
        tx = Transaction(
            user_id=_USER_UUID,
            from_account_id=_ACCOUNT_ID,
            to_bank_name="하나은행",
            amount=1_000,
            tx_type="transfer",
            status="completed",
        )
        db.add(tx)
        db.commit()

        resp = authed_client.post(f"/api/transfer/{tx.tx_id}/memo", json={"memo": "생일 선물"})

        assert resp.status_code == 200
        assert resp.json()["data"]["memo"] == "생일 선물"

        db.delete(tx)
        db.commit()

    def test_not_found(self, authed_client: TestClient):
        """[트랜잭션 없음] 존재하지 않는 txId로 메모 업데이트 시 → 404 TRANSACTION_NOT_FOUND."""
        non_existent_id = str(uuid.uuid4())
        resp = authed_client.post(
            f"/api/transfer/{non_existent_id}/memo",
            json={"memo": "없는 트랜잭션"},
        )

        assert resp.status_code == 404


# ── TestRecentRecipientsAPI ────────────────────────────────────────────────────
class TestRecentRecipientsAPI:
    def test_response_structure(self, authed_client: TestClient):
        """[응답 구조 확인] GET /api/transfer/recent 응답이 표준 형식을 따르는지 확인.
        (data.recipients가 리스트 형태여야 함)"""
        resp = authed_client.get("/api/transfer/recent")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "recipients" in body["data"]
        assert isinstance(body["data"]["recipients"], list)

    def test_returns_recent_recipient(self, authed_client: TestClient, db: Session):
        """[최근 수취인 반환] completed 이체 내역이 있는 수취인이 목록에 포함되어야 한다.
        응답 항목에는 recipientId, toBankName, toName, accountMasked, lastTransferredAt이 포함."""
        r_id = str(uuid.uuid4())
        recipient = RegisteredRecipient(
            recipient_id=r_id,
            user_id=_USER_UUID,
            alias="API테스트수취인",
            bank_name="국민은행",
            account_number="98765432109876",
            recipient_name="김테스트",
        )
        tx = Transaction(
            user_id=_USER_UUID,
            from_account_id=_ACCOUNT_ID,
            recipient_id=r_id,
            to_bank_name="국민은행",
            to_account_number="98765432109876",
            to_name="김테스트",
            amount=1_000,
            tx_type="transfer",
            status="completed",
        )
        db.add(recipient)
        db.flush()
        db.add(tx)
        db.commit()

        resp = authed_client.get("/api/transfer/recent")

        assert resp.status_code == 200
        recipients = resp.json()["data"]["recipients"]
        # 방금 추가한 수취인이 목록에 있어야 함
        assert any(item["recipientId"] == r_id for item in recipients)
        # 응답 항목 구조 검증
        target = next(item for item in recipients if item["recipientId"] == r_id)
        assert "toBankName" in target
        assert "toName" in target
        assert "accountMasked" in target
        assert "lastTransferredAt" in target

        db.delete(tx)
        db.delete(recipient)
        db.commit()
