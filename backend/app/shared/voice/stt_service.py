import io

import httpx
import mutagen

from app.core.config import settings
from app.core.exception import STTError

SUPPORTED_CONTENT_TYPES = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/aac",
        "audio/flac",
        "audio/ogg",
        "audio/mp3",
    }
)

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_DURATION = 60.0


async def transcribe_audio(
    audio_bytes: bytes,
    content_type: str = "audio/wav",
) -> str:
    """Clova Speech API로 음성을 텍스트로 변환합니다."""
    _validate_audio(audio_bytes, content_type)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.CLOVA_URL,
                content=audio_bytes,
                headers={
                    "X-CLOVASPEECH-API-KEY": settings.CLOVA_SECRET_KEY,
                    "Content-Type": "application/octet-stream",
                },
                params={"lang": "Kor"},
            )
    except httpx.TimeoutException as exc:
        raise STTError(
            code="STT_FAILED",
            message="Clova Speech API 요청 시간이 초과됐습니다.",
            user_message="음성 인식 서비스가 응답하지 않습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc
    except httpx.RequestError as exc:
        raise STTError(
            code="SERVICE_UNAVAILABLE",
            message="Clova Speech API에 연결할 수 없습니다.",
            user_message="음성 인식 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc

    if response.status_code != 200:
        raise STTError(
            code="STT_FAILED",
            message=f"Clova Speech API 오류: status={response.status_code}, body={response.text}",
            user_message="음성을 인식하지 못했습니다. 다시 말씀해 주세요.",
        )

    payload = response.json()
    text: str | None = payload.get("text")
    if not text:
        raise STTError(
            code="STT_FAILED",
            message="Clova Speech 응답에 텍스트가 없습니다.",
        )

    return text


def _validate_audio(audio_bytes: bytes, content_type: str) -> None:
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise STTError(
            code="VOICE_AUDIO_TOO_LARGE",
            message="음성 파일 크기가 10 MB를 초과합니다.",
        )

    mime = content_type.split(";")[0].strip().lower()
    if mime not in SUPPORTED_CONTENT_TYPES:
        raise STTError(
            code="VOICE_AUDIO_INVALID_FORMAT",
            message="지원하지 않는 오디오 형식입니다.",
        )

    duration = _get_audio_duration(audio_bytes)
    if duration is not None and duration > MAX_AUDIO_DURATION:
        raise STTError(
            code="VOICE_AUDIO_TOO_LONG",
            message="음성은 60초를 초과할 수 없습니다.",
        )


def _get_audio_duration(audio_bytes: bytes) -> float | None:
    try:
        audio = mutagen.File(io.BytesIO(audio_bytes))
        if audio is not None and audio.info is not None:
            return audio.info.length
    except Exception:
        pass
    return None
