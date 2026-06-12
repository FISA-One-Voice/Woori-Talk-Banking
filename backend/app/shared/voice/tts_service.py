import logging

import httpx

from app.core.config import settings
from app.core.exception import TTSError
from app.core.metrics import external_api_calls_total

logger = logging.getLogger(__name__)

TTS_SPEED_MIN = 0.25
TTS_SPEED_MAX = 4.0


async def synthesize_speech(
    text: str,
    speed: float = 1.0,
    voice_name: str = "ko-KR-SunHiNeural",
) -> bytes:
    """Azure Cognitive Services TTS API로 텍스트를 음성(MP3)으로 변환합니다.

    Args:
        text: 음성으로 변환할 텍스트.
        speed: 재생 속도. 0.25 ~ 4.0 범위. 기본값 1.0. 재생 배속은 프론트엔드 TTS_RATE로 제어.
        voice_name: 사용할 Azure 음성 이름. 기본값 'ko-KR-SunHiNeural'.

    Returns:
        MP3 형식의 음성 바이트 데이터.

    Raises:
        TTSError: text가 공백만 있거나, speed 범위 초과, 또는 API 호출 실패 시.
    """
    if not text.strip():
        raise TTSError(
            code="INVALID_REQUEST",
            message="텍스트가 비어 있습니다.",
            user_message="음성 변환할 내용이 없습니다.",
        )

    if not (TTS_SPEED_MIN <= speed <= TTS_SPEED_MAX):
        raise TTSError(
            code="TTS_SPEED_OUT_OF_RANGE",
            message="TTS 속도는 0.25 ~ 4.0 범위여야 합니다.",
            user_message="음성 속도 설정이 올바르지 않습니다.",
        )

    url = (
        f"https://{settings.AZURE_TTS_REGION}"
        ".tts.speech.microsoft.com/cognitiveservices/v1"
    )
    ssml = _build_ssml(text, voice_name, speed)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                content=ssml.encode("utf-8"),
                headers={
                    "Ocp-Apim-Subscription-Key": settings.AZURE_TTS_KEY,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                },
            )
    except httpx.TimeoutException as exc:
        external_api_calls_total.labels(service="azure_tts", status="error").inc()
        logger.warning(
            "external_api_call",
            extra={
                "event": "external_api_call",
                "service": "azure_tts",
                "status": "error",
            },
        )
        raise TTSError(
            code="SERVICE_UNAVAILABLE",
            message="Azure TTS API 요청 시간이 초과됐습니다.",
            user_message="음성 합성 서비스가 응답하지 않습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc
    except httpx.RequestError as exc:
        external_api_calls_total.labels(service="azure_tts", status="error").inc()
        logger.warning(
            "external_api_call",
            extra={
                "event": "external_api_call",
                "service": "azure_tts",
                "status": "error",
            },
        )
        raise TTSError(
            code="SERVICE_UNAVAILABLE",
            message="Azure TTS API에 연결할 수 없습니다.",
            user_message="음성 합성 서비스에 연결할 수 없습니다.",
        ) from exc

    if response.status_code != 200:
        external_api_calls_total.labels(service="azure_tts", status="error").inc()
        logger.warning(
            "external_api_call",
            extra={
                "event": "external_api_call",
                "service": "azure_tts",
                "status": "error",
            },
        )
        raise TTSError(
            code="SERVICE_UNAVAILABLE",
            message=f"Azure TTS API 오류: status={response.status_code}",
            user_message="음성 합성 중 오류가 발생했습니다.",
        )

    external_api_calls_total.labels(service="azure_tts", status="success").inc()
    logger.info(
        "external_api_call",
        extra={
            "event": "external_api_call",
            "service": "azure_tts",
            "status": "success",
        },
    )
    return response.content


def _build_ssml(text: str, voice_name: str, speed: float) -> str:
    """Azure TTS에 전달할 SSML 문자열을 생성합니다.

    Args:
        text: 변환할 텍스트.
        voice_name: Azure 음성 이름.
        speed: 재생 속도 (0.25 ~ 4.0).

    Returns:
        Azure TTS에 전달할 SSML 문자열.
    """
    rate = _speed_to_rate(speed)
    return (
        "<speak version='1.0' xml:lang='ko-KR'>"
        f"<voice name='{voice_name}'>"
        f"<prosody rate='{rate}'>{text}</prosody>"
        "</voice>"
        "</speak>"
    )


def _speed_to_rate(speed: float) -> str:
    """재생 속도 float을 SSML prosody rate 문자열로 변환합니다."""
    percentage = round((speed - 1.0) * 100)
    if percentage >= 0:
        return f"+{percentage}%"
    return f"{percentage}%"
