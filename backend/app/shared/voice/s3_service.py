"""S3 동의 음성 업로드 서비스 (voice-consent-s3).

ASV 인증 성공 시 이체 확인 단계의 TTS 안내 + 사용자 동의 음성을
결합하여 S3에 저장한다. 모든 예외는 이 모듈 내부에서 흡수하여
이체 흐름에 전파하지 않는다.

Design Ref: §4 API Specification, §6 Error Handling, §9 Clean Architecture
"""

import asyncio
import io
import logging

from pydub import AudioSegment

from app.core.config import settings

logger = logging.getLogger(__name__)


def mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """MP3 바이트를 WAV 바이트로 변환합니다.

    Azure TTS 출력(MP3)을 WAV로 변환하여 concat_wav에 전달할 때 사용합니다.

    Args:
        mp3_bytes: MP3 포맷 오디오 바이트.

    Returns:
        WAV 포맷 오디오 바이트.
    """
    audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    return buf.getvalue()


def concat_wav(first: bytes, second: bytes) -> bytes:
    """두 WAV 바이트를 순서대로 결합합니다.

    Args:
        first: 앞에 올 WAV 바이트 (TTS 안내 음성).
        second: 뒤에 올 WAV 바이트 (사용자 동의 음성).

    Returns:
        결합된 WAV 바이트.
    """
    seg1 = AudioSegment.from_file(io.BytesIO(first), format="wav")
    seg2 = AudioSegment.from_file(io.BytesIO(second), format="wav")
    combined = seg1 + seg2
    buf = io.BytesIO()
    combined.export(buf, format="wav")
    return buf.getvalue()


async def upload_consent_audio(
    user_id: str,
    tx_id: str,
    audio_bytes: bytes,
) -> str | None:
    """동의 증빙 WAV를 S3에 업로드합니다.

    AWS_S3_BUCKET 환경변수가 비어있으면 업로드를 스킵하고 None을 반환합니다.
    boto3 호출은 asyncio.to_thread로 실행하여 이벤트 루프를 차단하지 않습니다.
    모든 예외를 내부에서 흡수하여 이체 흐름에 영향을 주지 않습니다.

    Args:
        user_id: 사용자 ID. S3 경로 구성에 사용.
        tx_id: 거래 ID. S3 파일명으로 사용.
        audio_bytes: WAV 포맷 오디오 바이트 (TTS + 동의 음성 결합).

    Returns:
        S3 URI (s3://{bucket}/voice-consent/{user_id}/{tx_id}.wav).
        AWS_S3_BUCKET 미설정 또는 업로드 실패 시 None.
    """
    if not settings.AWS_S3_BUCKET:
        logger.warning("AWS_S3_BUCKET 미설정 — 동의 음성 S3 업로드 스킵")
        return None

    s3_key = f"voice-consent/{user_id}/{tx_id}.wav"

    def _sync_upload() -> str:
        import boto3

        client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )
        client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=audio_bytes,
            ContentType="audio/wav",
        )
        return f"s3://{settings.AWS_S3_BUCKET}/{s3_key}"

    try:
        s3_uri = await asyncio.to_thread(_sync_upload)
        logger.info("동의 음성 S3 업로드 성공: %s", s3_uri)
        return s3_uri
    except Exception:
        logger.error(
            "동의 음성 S3 업로드 실패 (user_id=%s, tx_id=%s) — 이체 결과 영향 없음",
            user_id,
            tx_id,
            exc_info=True,
        )
        return None
