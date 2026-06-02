import io
import struct
import wave

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.core.database import SessionLocal
from app.core.exception import VoiceServiceError
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


def _make_dummy_wav() -> bytes:
    """테스트용 최소 WAV 파일 바이트를 반환합니다."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<" + "h" * 160, *([0] * 160)))
    return buf.getvalue()


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
        "/api/users/login",
        json={"phone": TEST_PHONE, "pin": TEST_PIN},
    )
    return res.json()["data"]["accessToken"]


# ── 테스트 케이스 ─────────────────────────────────────────────────────────────


class TestVoiceRegistration:
    """POST /voice/register 테스트"""

    @pytest.mark.integration
    @pytest.mark.xfail(
        reason="더미 WAV(무음)로는 ASV 서버가 500을 반환함. 실제 목소리 파일 필요.",
        strict=False,
    )
    def test_voice_register_success(self, client: TestClient, valid_token: str):
        """192차원 벡터를 전송하면 성공적으로 DB에 등록되어야 합니다.

        실제 ASV 서버와 실제 목소리 WAV 파일이 있어야 통과됩니다 (integration 마커).
        """
        wav_bytes = _make_dummy_wav()
        res = client.post(
            "/api/voice/register",
            headers={"Authorization": f"Bearer {valid_token}"},
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
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
        wav_bytes = _make_dummy_wav()
        res = client.post(
            "/api/voice/register",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
        )

        assert res.status_code == 401

    def test_voice_register_invalid_token(self, client: TestClient):
        """잘못된 토큰으로 요청하면 오류(401)가 발생해야 합니다."""
        wav_bytes = _make_dummy_wav()
        res = client.post(
            "/api/voice/register",
            headers={"Authorization": "Bearer invalid_fake_token_123"},
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
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
        wav_bytes = _make_dummy_wav()
        res = client.post(
            "/api/voice/register",
            headers={"Authorization": f"Bearer {valid_token}"},
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
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
        wav_bytes = _make_dummy_wav()
        res = client.post(
            "/api/voice/register",
            headers={"Authorization": f"Bearer {valid_token}"},
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
        )

        assert res.status_code == 503
        assert res.json()["code"] == "SERVICE_UNAVAILABLE"
