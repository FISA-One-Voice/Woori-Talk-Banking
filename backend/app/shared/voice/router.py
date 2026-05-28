"""
stt_service, tts_service의 로직을 HTTP로 노출하는 창구 역할입니다.
비즈니스 로직은 없고 요청을 받아서 서비스에 넘기고 결과를 포장해서 돌려줍니다.
"""

import base64

from fastapi import APIRouter, UploadFile

from app.shared.voice.schema import ApiResponse, STTResult, TTSRequest, TTSResult
from app.shared.voice.stt_service import transcribe_audio
from app.shared.voice.tts_service import synthesize_speech

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
    transcript = await transcribe_audio(audio_bytes, content_type)

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
    audio_bytes = await synthesize_speech(body.text, body.speed)

    return ApiResponse(
        success=True,
        data=TTSResult(
            audio_base64=base64.b64encode(audio_bytes).decode()
        ).model_dump(),
        message="음성 변환이 완료되었습니다.",
    )
