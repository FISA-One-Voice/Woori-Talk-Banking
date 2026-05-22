import httpx

from app.core.config import settings

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
    }
)

# CLOVA STT 파일 용량 상한 (10 MB)
MAX_AUDIO_BYTES = 10 * 1024 * 1024


class STTError(RuntimeError):
    """Clova Speech API 호출 또는 응답 파싱 중 발생하는 예외."""


async def transcribe_audio(
    audio_bytes: bytes,
    content_type: str = "audio/wav",
) -> str:
    """Clova Speech API로 음성을 텍스트로 변환합니다.

    Args:
        audio_bytes: 변환할 음성 파일의 바이트 데이터.
        content_type: 오디오 파일의 MIME 타입.

    Returns:
        Clova Speech가 인식한 텍스트 문자열.

    Raises:
        ValueError: 파일 용량이 10 MB를 초과하거나 지원하지 않는 포맷인 경우.
        STTError: Clova Speech API 호출 또는 응답 파싱 실패 시.
    """
    _validate_audio(audio_bytes, content_type)  # API 호출 전에 용량·포맷을 검증

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
        raise STTError("Clova Speech API 요청 시간이 초과됐습니다.") from exc
    except httpx.RequestError as exc:
        raise STTError("Clova Speech API에 연결할 수 없습니다.") from exc

    if response.status_code != 200:
        raise STTError(f"Clova Speech API 오류: status={response.status_code}")

    payload = response.json()
    text: str | None = payload.get("text")
    if not text:
        raise STTError("Clova Speech 응답에 텍스트가 없습니다.")

    return text


def _validate_audio(audio_bytes: bytes, content_type: str) -> None:
    """테스트 용이성을 위하여, 음성 파일 용량·포맷을 검증합니다.

    Args:
        audio_bytes: 검증할 음성 파일 바이트 데이터.
        content_type: 오디오 파일의 MIME 타입.

    Raises:
        ValueError: 용량 초과 또는 지원하지 않는 포맷인 경우.
    """
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError("VOICE_AUDIO_TOO_LARGE")

    mime = content_type.split(";")[0].strip().lower()
    if mime not in SUPPORTED_CONTENT_TYPES:
        raise ValueError("VOICE_AUDIO_INVALID_FORMAT")
