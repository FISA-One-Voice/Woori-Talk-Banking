from typing import Any

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """POST /api/voice/tts 요청 바디."""

    text: str = Field(..., max_length=1000)
    speed: float = Field(default=1.0)


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
