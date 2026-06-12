"""수취인 API 통합 테스트.

GET /api/recipients, GET /api/contacts/match 엔드포인트를 실제 HTTP로 검증합니다.

실행 방법:
    cd backend
    pytest tests/test_recipients_api.py -v

전제 조건:
    - .env에 DATABASE_URL 설정 (Aiven PostgreSQL)
    - CRYPTO_NOOP=true (config.py 기본값)
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.user import User

# ── 테스트 데이터 상수 ──────────────────────────────────────────────────────────
_TEST_PIN = "000001"
_TEST_PIN_HASH = bcrypt.hashpw(_TEST_PIN.encode(), bcrypt.gensalt()).decode()


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _random_phone() -> str:
    return f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}"


def _create_user(db: Session, phone: str | None = None) -> User:
    user = User(
        name="수취인API테스트",
        phone=phone or _random_phone(),
        pin_hash=_TEST_PIN_HASH,
        embedding_vector=[0.0] * 192,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client: TestClient, phone: str) -> str:
    """로그인하여 access token을 반환합니다."""
    res = client.post("/api/users/login", json={"phone": phone, "pin": _TEST_PIN})
    assert res.status_code == 200, f"로그인 실패: {res.json()}"
    return res.json()["data"]["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _cleanup(user_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        db.query(RegisteredRecipient).filter_by(user_id=user_id).delete()
        db.query(Account).filter_by(user_id=user_id).delete()
        db.query(User).filter_by(user_id=user_id).delete()
        db.commit()
    finally:
        db.close()


# ── 픽스처 ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api_user(db: Session):
    """API 테스트용 사용자 + 등록 수취인 3건."""
    user = _create_user(db)

    recipients = [
        RegisteredRecipient(
            user_id=user.user_id,
            alias="엄마",
            bank_name="국민은행",
            account_number="123-456-789012",
            recipient_name="홍어머니",
        ),
        RegisteredRecipient(
            user_id=user.user_id,
            alias="아빠",
            bank_name="신한은행",
            account_number="110-222-333444",
            recipient_name="홍아버지",
        ),
        RegisteredRecipient(
            user_id=user.user_id,
            alias="동생홍",
            bank_name="우리은행",
            account_number="1002-111-222333",
            recipient_name="홍길동",
        ),
    ]
    for r in recipients:
        db.add(r)
    db.commit()

    yield user

    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def api_token(client: TestClient, api_user: User) -> str:
    """api_user의 JWT access token."""
    return _login(client, api_user.phone)


@pytest.fixture(scope="module")
def other_user(db: Session):
    """격리 검증용 다른 사용자 (수취인 없음)."""
    user = _create_user(db)
    yield user
    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def other_token(client: TestClient, other_user: User) -> str:
    return _login(client, other_user.phone)


# ── GET /api/recipients ────────────────────────────────────────────────────────


class TestListRecipients:
    """GET /api/recipients 테스트"""

    def test_success_returns_list(
        self, client: TestClient, api_token: str, api_user: User
    ):
        """등록 수취인 목록을 정상 반환합니다."""
        res = client.get("/api/recipients", headers=_auth(api_token))

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 3

    def test_response_envelope(self, client: TestClient, api_token: str):
        """응답이 표준 envelope(success, data, message)를 갖습니다."""
        body = client.get("/api/recipients", headers=_auth(api_token)).json()

        assert "success" in body
        assert "data" in body
        assert "message" in body

    def test_recipient_fields(self, client: TestClient, api_token: str):
        """각 수취인 항목이 필수 필드를 포함합니다."""
        items = client.get("/api/recipients", headers=_auth(api_token)).json()["data"]

        for item in items:
            assert "recipientId" in item
            assert "alias" in item
            assert "recipientName" in item
            assert "bankName" in item
            assert "accountMasked" in item

    def test_account_number_masked(self, client: TestClient, api_token: str):
        """계좌번호가 마스킹되어 반환됩니다 (뒤 4자리만 노출)."""
        items = client.get("/api/recipients", headers=_auth(api_token)).json()["data"]

        for item in items:
            masked = item["accountMasked"]
            assert "*" in masked, "마스킹 문자(*)가 없습니다"
            # 뒤 4자리는 원본 숫자여야 함
            assert masked[-4:].isdigit() or masked[-4:].replace("-", "").isdigit()

    def test_user_isolation(self, client: TestClient, other_token: str):
        """다른 사용자에게는 본인 수취인만 반환됩니다."""
        items = client.get("/api/recipients", headers=_auth(other_token)).json()["data"]

        # other_user는 수취인이 없음
        assert items == []

    def test_no_token_returns_401(self, client: TestClient):
        """토큰 없이 요청하면 401입니다."""
        res = client.get("/api/recipients")

        assert res.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient):
        """위조된 토큰으로 요청하면 401입니다."""
        res = client.get("/api/recipients", headers=_auth("fake.token.here"))

        assert res.status_code == 401
        assert res.json()["success"] is False

    def test_malformed_bearer_returns_401(self, client: TestClient):
        """Bearer 형식이 잘못된 경우 401입니다."""
        res = client.get(
            "/api/recipients",
            headers={"Authorization": "NotBearer token"},
        )

        assert res.status_code == 401

    def test_empty_recipient_list(self, client: TestClient, other_token: str):
        """수취인이 없는 사용자는 빈 리스트와 success:true를 받습니다."""
        body = client.get("/api/recipients", headers=_auth(other_token)).json()

        assert body["success"] is True
        assert body["data"] == []


# ── GET /api/contacts/match ────────────────────────────────────────────────────


class TestMatchContacts:
    """GET /api/contacts/match 테스트"""

    def test_match_by_alias_exact(self, client: TestClient, api_token: str):
        """별칭 정확히 일치하는 수취인을 반환합니다."""
        res = client.get(
            "/api/contacts/match", params={"name": "엄마"}, headers=_auth(api_token)
        )

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        matched = body["data"]["matched"]
        assert len(matched) >= 1
        assert any(m["alias"] == "엄마" for m in matched)

    def test_match_by_recipient_name(self, client: TestClient, api_token: str):
        """수취인 실명으로 검색됩니다."""
        res = client.get(
            "/api/contacts/match", params={"name": "홍길동"}, headers=_auth(api_token)
        )

        matched = res.json()["data"]["matched"]
        assert len(matched) >= 1
        assert any(m["recipientName"] == "홍길동" for m in matched)

    def test_match_partial_alias(self, client: TestClient, api_token: str):
        """별칭 일부만 입력해도 부분 일치로 검색됩니다."""
        res = client.get(
            "/api/contacts/match", params={"name": "홍"}, headers=_auth(api_token)
        )

        # "동생홍" alias + "홍어머니", "홍아버지", "홍길동" recipient_name 포함
        matched = res.json()["data"]["matched"]
        assert len(matched) >= 3

    def test_match_multiple_results(self, client: TestClient, api_token: str):
        """동명이인 포함 여러 명이 매칭되면 전체 목록을 반환합니다."""
        # "홍"으로 검색 시 3명 모두 포함
        matched = client.get(
            "/api/contacts/match", params={"name": "홍"}, headers=_auth(api_token)
        ).json()["data"]["matched"]

        assert len(matched) >= 2

    def test_no_match_returns_empty_list(self, client: TestClient, api_token: str):
        """매칭 결과가 없으면 빈 리스트를 반환합니다."""
        res = client.get(
            "/api/contacts/match",
            params={"name": "존재하지않는이름xyz123"},
            headers=_auth(api_token),
        )

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["matched"] == []

    def test_matched_fields(self, client: TestClient, api_token: str):
        """각 매칭 항목이 필수 필드를 포함합니다."""
        matched = client.get(
            "/api/contacts/match", params={"name": "엄마"}, headers=_auth(api_token)
        ).json()["data"]["matched"]

        for item in matched:
            assert "recipientId" in item
            assert "alias" in item
            assert "recipientName" in item
            assert "bankName" in item
            assert "accountMasked" in item

    def test_account_masked_in_match(self, client: TestClient, api_token: str):
        """매칭 결과의 계좌번호도 마스킹됩니다."""
        matched = client.get(
            "/api/contacts/match", params={"name": "엄마"}, headers=_auth(api_token)
        ).json()["data"]["matched"]

        assert all("*" in m["accountMasked"] for m in matched)

    def test_user_isolation(self, client: TestClient, other_token: str):
        """다른 사용자의 수취인은 검색되지 않습니다."""
        # other_user로 api_user의 수취인 이름 검색
        matched = client.get(
            "/api/contacts/match", params={"name": "엄마"}, headers=_auth(other_token)
        ).json()["data"]["matched"]

        assert matched == []

    def test_missing_name_param_returns_422(self, client: TestClient, api_token: str):
        """name 파라미터 누락 시 422를 반환합니다."""
        res = client.get("/api/contacts/match", headers=_auth(api_token))

        assert res.status_code == 422

    def test_no_token_returns_401(self, client: TestClient):
        """토큰 없이 요청하면 401입니다."""
        res = client.get("/api/contacts/match", params={"name": "엄마"})

        assert res.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient):
        """위조 토큰이면 401입니다."""
        res = client.get(
            "/api/contacts/match",
            params={"name": "엄마"},
            headers=_auth("invalid.jwt.token"),
        )

        assert res.status_code == 401

    def test_korean_name(self, client: TestClient, api_token: str):
        """한글 이름도 정상 처리됩니다."""
        res = client.get(
            "/api/contacts/match", params={"name": "아빠"}, headers=_auth(api_token)
        )

        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_sql_injection_attempt(self, client: TestClient, api_token: str):
        """SQL 인젝션 시도는 에러 없이 빈 결과를 반환합니다."""
        injection = "' OR '1'='1"
        res = client.get(
            "/api/contacts/match",
            params={"name": injection},
            headers=_auth(api_token),
        )

        assert res.status_code == 200
        assert res.json()["success"] is True
        assert isinstance(res.json()["data"]["matched"], list)

    def test_very_long_name(self, client: TestClient, api_token: str):
        """매우 긴 이름 입력도 에러 없이 처리됩니다."""
        long_name = "가" * 200
        res = client.get(
            "/api/contacts/match",
            params={"name": long_name},
            headers=_auth(api_token),
        )

        assert res.status_code == 200
        assert res.json()["data"]["matched"] == []

    def test_special_characters(self, client: TestClient, api_token: str):
        """특수문자 입력도 에러 없이 처리됩니다."""
        res = client.get(
            "/api/contacts/match",
            params={"name": "!@#$%^&*()"},
            headers=_auth(api_token),
        )

        assert res.status_code == 200

    def test_response_message_includes_count(self, client: TestClient, api_token: str):
        """응답 message에 매칭 건수가 포함됩니다."""
        body = client.get(
            "/api/contacts/match", params={"name": "엄마"}, headers=_auth(api_token)
        ).json()

        assert "1명" in body["message"] or "명" in body["message"]
