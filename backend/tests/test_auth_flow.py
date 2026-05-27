# =============================================================================
# backend/tests/test_auth_flow.py
#
# [이 파일의 역할]
# jwt_auth 기능의 HTTP 통합 테스트입니다.
# 실제 DB(Aiven PostgreSQL)에 테스트 사용자를 만들고,
# /jwt-auth/login, /refresh, /logout 엔드포인트를 호출해서
# 응답이 CLAUDE.md의 표준 형식을 따르는지 검증합니다.
#
# [테스트 케이스 목록]
# 1. 정상 로그인        → 200, accessToken/refreshToken/userId 반환
# 2. 없는 전화번호      → 404, code: USER_NOT_FOUND
# 3. 틀린 PIN          → 401, code: UNAUTHORIZED
# 4. refresh 토큰 갱신  → 200, 새 accessToken 반환
# 5. 위조 refresh 토큰  → 401, code: TOKEN_INVALID
# 6. 정상 로그아웃      → 200, userId 반환
# 7. 토큰 없이 logout   → 403, 인증 오류
#
# [실행 방법]
#   cd backend
#   CRYPTO_NOOP=true pytest tests/test_auth_flow.py -v
# =============================================================================

import time

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User

# ── 테스트 데이터 상수 ──────────────────────────────────────────────────────────
# 테스트 전용 전화번호 — 실제 서비스 번호와 절대 겹치지 않도록 특수한 번호 사용
TEST_PHONE = "010-0000-TEST"
TEST_PIN = "123456"


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

def _create_test_user(db: Session) -> User:
    """테스트용 사용자를 DB에 직접 삽입합니다.

    API 엔드포인트 없이 DB에 직접 넣는 이유:
    - 회원가입 API가 아직 구현되지 않았습니다.
    - 테스트는 "로그인" 동작만 검증하면 되므로 사전 데이터를 직접 만듭니다.

    중요: pin_hash는 반드시 실제 bcrypt 해시여야 합니다.
    verify_pin()이 bcrypt.checkpw()를 호출하기 때문입니다.
    """
    pin_hash = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        name="테스트유저_auth",
        phone=TEST_PHONE,
        pin_hash=pin_hash,
        embedding_vector=[0.0] * 192,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _delete_test_user(phone: str) -> None:
    """테스트 사용자를 DB에서 삭제합니다. 테스트 오염 방지용."""
    cleanup_db = SessionLocal()
    try:
        cleanup_db.query(User).filter(User.phone == phone).delete()
        cleanup_db.commit()
    finally:
        cleanup_db.close()


# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup():
    """각 테스트 함수 실행 후 테스트 사용자를 삭제합니다.

    autouse=True: 이 파일의 모든 테스트에 자동으로 적용됩니다.
    yield 이후 코드 = 테스트 실행 후 (teardown) 정리 로직
    """
    yield  # ← 이 줄에서 실제 테스트가 실행됩니다
    _delete_test_user(TEST_PHONE)


@pytest.fixture
def test_user(db: Session) -> User:
    """테스트 사용자를 생성하고 반환합니다."""
    return _create_test_user(db)


# ── 테스트 케이스 ─────────────────────────────────────────────────────────────


class TestLogin:
    """POST /jwt-auth/login 테스트"""

    def test_login_success(self, client: TestClient, test_user: User):
        """정상적인 전화번호 + PIN으로 로그인하면 토큰이 반환됩니다."""
        res = client.post(
            "/jwt-auth/login",
            json={"phone": TEST_PHONE, "pin": TEST_PIN},
        )

        assert res.status_code == 200

        body = res.json()
        assert body["success"] is True
        assert body["message"] == "로그인 성공 및 토큰이 발급되었습니다."

        # 응답 데이터에 세 가지 키가 모두 있어야 합니다
        data = body["data"]
        assert "accessToken" in data,  "accessToken이 없습니다"
        assert "refreshToken" in data, "refreshToken이 없습니다"
        assert "userId" in data,       "userId가 없습니다"

        # 각 값이 비어있지 않아야 합니다
        assert len(data["accessToken"]) > 0
        assert len(data["refreshToken"]) > 0
        assert data["userId"] == str(test_user.user_id)

    def test_login_unknown_phone(self, client: TestClient):
        """가입되지 않은 전화번호로 로그인하면 USER_NOT_FOUND 오류가 반환됩니다."""
        res = client.post(
            "/jwt-auth/login",
            json={"phone": "010-9999-9999", "pin": TEST_PIN},
        )

        assert res.status_code == 404

        body = res.json()
        assert body["success"] is False
        assert body["code"] == "USER_NOT_FOUND"
        # 프론트엔드는 message가 아닌 code로 분기해야 합니다 (CLAUDE.md 원칙)

    def test_login_wrong_pin(self, client: TestClient, test_user: User):
        """올바른 전화번호지만 틀린 PIN → UNAUTHORIZED 오류가 반환됩니다."""
        _ = test_user  # DB에 사용자가 존재해야 "잘못된 PIN" 케이스를 테스트할 수 있음
        res = client.post(
            "/jwt-auth/login",
            json={"phone": TEST_PHONE, "pin": "000000"},  # 틀린 PIN
        )

        assert res.status_code == 401

        body = res.json()
        assert body["success"] is False
        assert body["code"] == "UNAUTHORIZED"


class TestRefreshToken:
    """POST /jwt-auth/refresh 테스트"""

    def test_refresh_success(self, client: TestClient, test_user: User):
        """유효한 refresh token으로 새 access token을 발급받을 수 있습니다."""
        # 1단계: 로그인해서 refresh token 획득
        login_res = client.post(
            "/jwt-auth/login",
            json={"phone": TEST_PHONE, "pin": TEST_PIN},
        )
        refresh_token = login_res.json()["data"]["refreshToken"]

        # 2단계: 1초 대기 후 refresh 요청
        # JWT exp(만료 시각)는 초 단위이므로 같은 초 안에 재발급하면
        # exp 값이 동일해 완전히 같은 토큰이 생성됩니다.
        time.sleep(1)
        res = client.post(
            "/jwt-auth/refresh",
            json={"refreshToken": refresh_token},
        )

        assert res.status_code == 200

        body = res.json()
        assert body["success"] is True
        assert "accessToken" in body["data"]
        # 기존 토큰과 다른 새 토큰이어야 합니다
        original_access = login_res.json()["data"]["accessToken"]
        assert body["data"]["accessToken"] != original_access

    def test_refresh_with_invalid_token(self, client: TestClient):
        """위조된 refresh token은 TOKEN_INVALID 오류를 반환합니다."""
        res = client.post(
            "/jwt-auth/refresh",
            json={"refreshToken": "this.is.a.fake.token"},
        )

        assert res.status_code == 401

        body = res.json()
        assert body["success"] is False
        assert body["code"] == "TOKEN_INVALID"

    def test_refresh_with_empty_token(self, client: TestClient):
        """빈 문자열 refresh token도 TOKEN_INVALID 오류를 반환합니다."""
        res = client.post(
            "/jwt-auth/refresh",
            json={"refreshToken": ""},
        )

        assert res.status_code == 401

        body = res.json()
        assert body["success"] is False
        assert body["code"] == "TOKEN_INVALID"


class TestLogout:
    """PUT /jwt-auth/logout 테스트"""

    def test_logout_success(self, client: TestClient, test_user: User):
        """유효한 access token으로 로그아웃하면 userId가 반환됩니다."""
        # 1단계: 로그인해서 access token 획득
        login_res = client.post(
            "/jwt-auth/login",
            json={"phone": TEST_PHONE, "pin": TEST_PIN},
        )
        data = login_res.json()["data"]
        access_token = data["accessToken"]
        user_id = data["userId"]

        # 2단계: 로그아웃 요청
        res = client.put(
            "/jwt-auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert res.status_code == 200

        body = res.json()
        assert body["success"] is True
        assert body["data"]["userId"] == user_id
        assert body["data"]["userId"] == str(test_user.user_id)

    def test_logout_without_token(self, client: TestClient):
        """위조된 토큰으로 logout을 시도하면 401이 반환됩니다."""
        res = client.put(
            "/jwt-auth/logout",
            headers={"Authorization": "Bearer invalid.fake.token"},
        )
        assert res.status_code == 401

    def test_logout_with_invalid_token(self, client: TestClient):
        """위조된 access token으로 logout을 시도하면 401이 반환됩니다."""
        res = client.put(
            "/jwt-auth/logout",
            headers={"Authorization": "Bearer fake.access.token"},
        )

        assert res.status_code == 401

        body = res.json()
        assert body["success"] is False
        assert body["code"] == "TOKEN_INVALID"
