"""voice-consent-s3 pytest (Design Ref: §8 Test Plan).

L1: s3_service 단위 테스트 (concat_wav, mp3_to_wav, upload_consent_audio)
L2: _handle_normal_flow / _proceed_after_asv_success 캡처·업로드 동작 검증
"""

import asyncio
import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydub import AudioSegment

from app.shared.voice import s3_service


# ── 픽스처 ─────────────────────────────────────────────────────────────────────


def _make_wav_bytes(duration_ms: int = 100) -> bytes:
    """테스트용 짧은 WAV bytes를 생성합니다."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def _make_mp3_bytes() -> bytes:
    """pydub으로 생성한 최소 MP3 bytes를 반환합니다."""
    audio = AudioSegment.silent(duration=100)
    buf = io.BytesIO()
    audio.export(buf, format="mp3")
    return buf.getvalue()


# ── L1: concat_wav ─────────────────────────────────────────────────────────────


class TestConcatWav:
    def test_두_WAV_결합_후_RIFF_헤더_유지(self):
        wav1 = _make_wav_bytes(100)
        wav2 = _make_wav_bytes(200)

        result = s3_service.concat_wav(wav1, wav2)

        assert result[:4] == b"RIFF"

    def test_결합_길이가_합산_시간에_근접(self):
        wav1 = _make_wav_bytes(100)
        wav2 = _make_wav_bytes(200)

        result = s3_service.concat_wav(wav1, wav2)

        seg = AudioSegment.from_file(io.BytesIO(result), format="wav")
        # 100 + 200 = 300ms, 허용 오차 ±50ms
        assert 250 <= len(seg) <= 350


# ── L1: mp3_to_wav ─────────────────────────────────────────────────────────────


class TestMp3ToWav:
    def test_MP3_입력_시_WAV_반환(self):
        mp3 = _make_mp3_bytes()

        result = s3_service.mp3_to_wav(mp3)

        assert result[:4] == b"RIFF"

    def test_변환된_WAV_재생_가능(self):
        mp3 = _make_mp3_bytes()

        result = s3_service.mp3_to_wav(mp3)

        seg = AudioSegment.from_file(io.BytesIO(result), format="wav")
        assert len(seg) > 0


# ── L1: upload_consent_audio ───────────────────────────────────────────────────


class TestUploadConsentAudio:
    @pytest.mark.asyncio
    async def test_버킷_미설정_시_None_반환(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.AWS_S3_BUCKET", "")

        result = await s3_service.upload_consent_audio("user1", "tx1", b"data")

        assert result is None

    @pytest.mark.asyncio
    async def test_버킷_미설정_시_boto3_호출_없음(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.AWS_S3_BUCKET", "")

        with patch("boto3.client") as mock_boto3:
            await s3_service.upload_consent_audio("user1", "tx1", b"data")

        mock_boto3.assert_not_called()

    @pytest.mark.asyncio
    async def test_업로드_성공_시_S3_URI_반환(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.AWS_S3_BUCKET", "test-bucket")
        monkeypatch.setattr("app.core.config.settings.AWS_ACCESS_KEY_ID", "key")
        monkeypatch.setattr("app.core.config.settings.AWS_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setattr("app.core.config.settings.AWS_REGION", "ap-northeast-2")

        mock_client = MagicMock()
        mock_client.put_object.return_value = {}

        with patch("boto3.client", return_value=mock_client):
            result = await s3_service.upload_consent_audio("u1", "tx123", b"wav")

        assert result == "s3://test-bucket/voice-consent/u1/tx123.wav"

    @pytest.mark.asyncio
    async def test_업로드_성공_시_올바른_S3_키_사용(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.AWS_S3_BUCKET", "bucket")
        monkeypatch.setattr("app.core.config.settings.AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setattr("app.core.config.settings.AWS_SECRET_ACCESS_KEY", "s")

        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            await s3_service.upload_consent_audio("user99", "txABC", b"data")

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Key"] == "voice-consent/user99/txABC.wav"
        assert call_kwargs["ContentType"] == "audio/wav"

    @pytest.mark.asyncio
    async def test_ClientError_시_None_반환_예외_전파_없음(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.AWS_S3_BUCKET", "bucket")
        monkeypatch.setattr("app.core.config.settings.AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setattr("app.core.config.settings.AWS_SECRET_ACCESS_KEY", "s")

        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "not found"}},
            "PutObject",
        )

        with patch("boto3.client", return_value=mock_client):
            result = await s3_service.upload_consent_audio("user1", "tx1", b"data")

        assert result is None

    @pytest.mark.asyncio
    async def test_임의_예외_시_None_반환_예외_전파_없음(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.AWS_S3_BUCKET", "bucket")
        monkeypatch.setattr("app.core.config.settings.AWS_ACCESS_KEY_ID", "k")
        monkeypatch.setattr("app.core.config.settings.AWS_SECRET_ACCESS_KEY", "s")

        mock_client = MagicMock()
        mock_client.put_object.side_effect = RuntimeError("connection refused")

        with patch("boto3.client", return_value=mock_client):
            result = await s3_service.upload_consent_audio("user1", "tx1", b"data")

        assert result is None


# ── L2: _voice_state_reset_payload 초기화 확인 ────────────────────────────────


def test_reset_payload_에_pending_consent_필드_포함():
    from app.shared.voice.service import _voice_state_reset_payload

    payload = _voice_state_reset_payload()

    assert "pending_consent_tts_text" in payload
    assert payload["pending_consent_tts_text"] is None
    assert "pending_consent_audio_b64" in payload
    assert payload["pending_consent_audio_b64"] is None
