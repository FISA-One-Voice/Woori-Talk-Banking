import httpx

from app.core.config import settings

TTS_SPEED_MIN = 0.25
TTS_SPEED_MAX = 4.0


class TTSError(RuntimeError):
    """Azure TTS API 호출 또는 응답 파싱 중 발생하는 예외."""


async def synthesize_speech(
    text: str,
    speed: float = 1.0,
    voice_name: str = "ko-KR-SunHiNeural",
) -> bytes:
    """Azure Cognitive Services TTS API로 텍스트를 음성(MP3)으로 변환합니다.

    Args:
        text: 음성으로 변환할 텍스트.
        speed: 재생 속도. 0.25 ~ 4.0 범위. 기본값 1.0.
        voice_name: 사용할 Azure 음성 이름. 기본값 'ko-KR-SunHiNeural'.

    Returns:
        MP3 형식의 음성 바이트 데이터.

    Raises:
        ValueError: speed가 허용 범위를 벗어난 경우.
        TTSError: Azure TTS API 호출 실패 시.
    """
    if not (TTS_SPEED_MIN <= speed <= TTS_SPEED_MAX):
        raise ValueError("TTS_SPEED_OUT_OF_RANGE")

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
        raise TTSError("Azure TTS API 요청 시간이 초과됐습니다.") from exc
    except httpx.RequestError as exc:
        raise TTSError("Azure TTS API에 연결할 수 없습니다.") from exc

    if response.status_code != 200:
        raise TTSError(f"Azure TTS API 오류: status={response.status_code}")

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
