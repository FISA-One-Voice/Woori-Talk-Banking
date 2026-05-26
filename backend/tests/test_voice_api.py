import pytest
import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User

# 테스트용 계정 상수 (auth 테스트와 충돌하지 않도록 다른 번호 사용)
TEST_PHONE = "010-0000-VOIC"
TEST_PIN = "123456"

# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

def _create_test_user(db: Session) -> User:
    pin_hash = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        name="테스트유저_voice",
        phone=TEST_PHONE,
        pin_hash=pin_hash,
        embedding_vector=None,  # 처음엔 등록 안됨
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def _delete_test_user(phone: str) -> None:
    cleanup_db = SessionLocal()
    try:
        cleanup_db.query(User).filter(User.phone == phone).delete()
        cleanup_db.commit()
    finally:
        cleanup_db.close()

# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup():
    yield
    _delete_test_user(TEST_PHONE)

@pytest.fixture
def test_user(db: Session) -> User:
    return _create_test_user(db)

@pytest.fixture
def valid_token(client: TestClient, test_user: User) -> str:
    """로그인하여 유효한 액세스 토큰을 반환합니다."""
    res = client.post(
        "/users/login",
        json={"phone": TEST_PHONE, "pin": TEST_PIN},
    )
    return res.json()["data"]["accessToken"]

# ── 테스트 케이스 ─────────────────────────────────────────────────────────────

class TestVoiceRegistration:
    """POST /voice/register 테스트"""

    def test_voice_register_success(self, client: TestClient, valid_token: str):
        """192차원 벡터를 전송하면 성공적으로 DB에 등록되어야 합니다."""
        dummy_vector = [0.1] * 192

        res = client.post(
            "/voice/register",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"embedding_vector": dummy_vector}
        )

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["message"] == "음성 벡터(192차원)가 사용자의 계정에 성공적으로 등록되었습니다."

    def test_voice_register_invalid_dimension(self, client: TestClient, valid_token: str):
        """192차원이 아닌 벡터를 보내면 Pydantic에 의해 차단(422)되어야 합니다."""
        invalid_vector = [0.1] * 100  # 100차원

        res = client.post(
            "/voice/register",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"embedding_vector": invalid_vector}
        )

        assert res.status_code == 422
        body = res.json()
        assert body["success"] is False
        assert body["error_code"] == "INVALID_REQUEST"

    def test_voice_register_no_token(self, client: TestClient):
        """토큰 없이 요청하면 인증 오류(401)가 발생해야 합니다."""
        dummy_vector = [0.1] * 192

        res = client.post(
            "/voice/register",
            json={"embedding_vector": dummy_vector}
        )

        assert res.status_code == 401

    def test_voice_register_invalid_token(self, client: TestClient):
        """잘못된 토큰으로 요청하면 오류(401)가 발생해야 합니다."""
        dummy_vector = [0.1] * 192

        res = client.post(
            "/voice/register",
            headers={"Authorization": "Bearer invalid_fake_token_123"},
            json={"embedding_vector": dummy_vector}
        )

        assert res.status_code == 401
        body = res.json()
        assert body["code"] == "TOKEN_INVALID"
