import pytest
import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User
from app.core.exception import VoiceServiceError
from unittest.mock import patch

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
        # 이전에 테스트는 json을 보냈지만 이제 UploadFile을 보냄.
        # ASV 서버와 실제 통신을 하므로, ASV 서버가 구동 중이어야 통과됨.
        with open("../speaker1_a_cn_16k.wav", "rb") as f:
            res = client.post(
                "/voice/register",
                headers={"Authorization": f"Bearer {valid_token}"},
                files={"file": ("speaker1_a_cn_16k.wav", f, "audio/wav")},
            )

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert (
            body["message"]
            == "음성 벡터(192차원)가 사용자의 계정에 성공적으로 등록되었습니다."
        )

    def test_voice_register_no_token(self, client: TestClient):
        """토큰 없이 요청하면 인증 오류(401)가 발생해야 합니다."""
        with open("../speaker1_a_cn_16k.wav", "rb") as f:
            res = client.post(
                "/voice/register",
                files={"file": ("speaker1_a_cn_16k.wav", f, "audio/wav")},
            )

        assert res.status_code == 401

    def test_voice_register_invalid_token(self, client: TestClient):
        """잘못된 토큰으로 요청하면 오류(401)가 발생해야 합니다."""
        with open("../speaker1_a_cn_16k.wav", "rb") as f:
            res = client.post(
                "/voice/register",
                headers={"Authorization": "Bearer invalid_fake_token_123"},
                files={"file": ("speaker1_a_cn_16k.wav", f, "audio/wav")},
            )

        assert res.status_code == 401
        body = res.json()
        assert body["code"] == "TOKEN_INVALID"

    @patch("app.features.voice.service.extract_voice_vector")
    def test_voice_register_extract_failed(
        self, mock_extract, client: TestClient, valid_token: str
    ):
        """ASV 서버 오류 또는 벡터 추출 실패 시 VOICE_VECTOR_EXTRACT_FAILED가 발생해야 합니다."""
        mock_extract.side_effect = VoiceServiceError(
            code="VOICE_VECTOR_EXTRACT_FAILED",
            message="ASV 서버에서 유효한 192차원 벡터를 반환하지 않았습니다.",
            status_code=500,
        )
        with open("../speaker1_a_cn_16k.wav", "rb") as f:
            res = client.post(
                "/voice/register",
                headers={"Authorization": f"Bearer {valid_token}"},
                files={"file": ("speaker1_a_cn_16k.wav", f, "audio/wav")},
            )

        assert res.status_code == 500
        assert res.json()["code"] == "VOICE_VECTOR_EXTRACT_FAILED"

    @patch("app.features.voice.service.extract_voice_vector")
    def test_voice_register_service_unavailable(
        self, mock_extract, client: TestClient, valid_token: str
    ):
        """ASV 서버가 꺼져있거나 통신 불가능 시 SERVICE_UNAVAILABLE이 발생해야 합니다."""
        mock_extract.side_effect = VoiceServiceError(
            code="SERVICE_UNAVAILABLE",
            message="ASV 서버와 통신할 수 없습니다.",
            status_code=503,
        )
        with open("../speaker1_a_cn_16k.wav", "rb") as f:
            res = client.post(
                "/voice/register",
                headers={"Authorization": f"Bearer {valid_token}"},
                files={"file": ("speaker1_a_cn_16k.wav", f, "audio/wav")},
            )

        assert res.status_code == 503
        assert res.json()["code"] == "SERVICE_UNAVAILABLE"
