import io
import logging

import httpx
import mutagen

from app.core.config import settings
from app.core.exception import STTError

logger = logging.getLogger(__name__)

# CLOVA STT가 지원하는 오디오 MIME 타입, 절대 안바뀌는 값 이므로 frozenset으로 정의
SUPPORTED_CONTENT_TYPES = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/m4a",
        "audio/aac",
        "audio/flac",
        "audio/ogg",
        "audio/mp3",
        "audio/x-caf",
        "audio/caf",
    }
)

# CLOVA STT 파일 용량 상한 (10 MB)
MAX_AUDIO_BYTES = 10 * 1024 * 1024

# CLOVA STT 음성 길이 상한 (60초)
MAX_AUDIO_DURATION = 60.0


async def transcribe_audio(
    audio_bytes: bytes,
    content_type: str = "audio/wav",
) -> str:
    """Clova Speech API로 음성을 텍스트로 변환합니다.

    Args:
        audio_bytes: 변환할 음성 파일의 바이트 데이터.
        content_type: 오디오 파일의 MIME 타입.
            지원 형식: wav, mp3, mp4, m4a, aac, flac, ogg.
            미지정 시 audio/wav로 처리.

    Returns:
        Clova Speech가 인식한 텍스트 문자열.

    Raises:
        STTError: 파일 용량·길이 초과, 지원하지 않는 포맷, 또는 API 호출 실패 시.
    """
    _validate_audio(audio_bytes, content_type)  # API 호출 전에 용량·포맷·길이를 검증

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.CLOVA_URL,
                content=audio_bytes,
                headers={
                    "X-CLOVASPEECH-API-KEY": settings.CLOVA_SECRET_KEY,
                    # 이 계정은 application/octet-stream 만 허용
                    "Content-Type": "application/octet-stream",
                },
            )
    except httpx.TimeoutException as exc:
        raise STTError(
            code="STT_FAILED",
            message="Clova Speech API 요청 시간이 초과됐습니다.",
        ) from exc
    except httpx.RequestError as exc:
        raise STTError(
            code="SERVICE_UNAVAILABLE",
            message="Clova Speech API에 연결할 수 없습니다.",
        ) from exc

    if response.status_code != 200:
        print(f"[STT ERROR] status={response.status_code} body={response.text[:200]} "
              f"content_type={content_type} size={len(audio_bytes)} "
              f"header_hex={audio_bytes[:12].hex()}", flush=True)
        raise STTError(
            code="STT_FAILED",
            message=f"Clova Speech API 오류: status={response.status_code}, body={response.text[:200]}",
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
    """음성 파일 용량·포맷·길이를 검증합니다.

    Args:
        audio_bytes: 검증할 음성 파일 바이트 데이터.
        content_type: 오디오 파일의 MIME 타입.

    Raises:
        STTError: 용량 초과, 지원하지 않는 포맷, 또는 재생 시간 초과인 경우.
    """
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
    """음성 파일의 재생 시간을 초 단위로 반환합니다.

    mutagen이 파싱하지 못하는 포맷이면 None을 반환하고 길이 검증을 건너뜁니다.

    Args:
        audio_bytes: 재생 시간을 구할 음성 파일 바이트 데이터.

    Returns:
        재생 시간(초), 파악 불가 시 None.
    """
    try:
        audio = mutagen.File(io.BytesIO(audio_bytes))
        if audio is not None and audio.info is not None:
            return audio.info.length
    except Exception:
        pass
    return None
