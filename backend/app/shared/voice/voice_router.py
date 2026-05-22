'''
stt_service, tts_service의 로직을 HTTP로 노출하는 창구 역할입니다.
비즈니스 로직은 없고 요청을 받아서 서비스에 넘기고 결과를 포장해서 돌려줍니다.
'''

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.shared.voice.stt_service import STTError, transcribe_audio
from app.shared.voice.tts_service import TTSError, synthesize_speech


# ── 모델 ────────────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    """POST /api/voice/tts 요청 바디."""

    text: str = Field(..., min_length=1, max_length=1000)
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


class STTResult(BaseModel):
    """STT 변환 성공 시 data 필드에 담기는 결과."""

    transcript: str


class TTSResult(BaseModel):
    """TTS 변환 성공 시 data 필드에 담기는 결과."""

    audio_base64: str
    mime_type: str = "audio/mpeg"


class ApiResponse(BaseModel):

    success: bool
    data: Any = None
    message: str
    error_code: str | None = None


# ── 라우터 ───────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/stt", response_model=ApiResponse)
async def speech_to_text(file: UploadFile) -> ApiResponse:
    """업로드된 음성 파일을 텍스트로 변환합니다.

    Args:
        file: 변환할 음성 파일 (wav, mp3, m4a, flac, ogg 등).

    Returns:
        ApiResponse — data.transcript에 인식된 텍스트 포함.

    Raises:
        HTTPException 400: 용량 초과 또는 지원하지 않는 포맷.
        HTTPException 503: Clova Speech API 장애.
    """
    audio_bytes = await file.read()
    content_type = file.content_type or "audio/wav"

    try:
        transcript = await transcribe_audio(audio_bytes, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    except STTError as exc:
        raise HTTPException(status_code=503, detail={"error": exc.code}) from exc

    return ApiResponse(
        success=True,
        data=STTResult(transcript=transcript).model_dump(),
        message="음성 변환이 완료되었습니다.",
    )


@router.post("/tts", response_model=ApiResponse)
async def text_to_speech(body: TTSRequest) -> ApiResponse:
    """텍스트를 MP3 음성으로 변환합니다.

    Args:
        body: 변환할 텍스트와 재생 속도.

    Returns:
        ApiResponse — data.audio_base64에 MP3 Base64 인코딩 데이터 포함.

    Raises:
        HTTPException 400: tts_speed 범위 초과.
        HTTPException 503: Azure TTS API 장애.
    """
    try:
        audio_bytes = await synthesize_speech(body.text, body.speed)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "TTS_SPEED_OUT_OF_RANGE"},
        ) from exc
    except TTSError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": exc.code},
        ) from exc

    return ApiResponse(
        success=True,
        data=TTSResult(audio_base64=base64.b64encode(audio_bytes).decode()).model_dump(),
        message="음성 변환이 완료되었습니다.",
    )
