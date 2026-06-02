"""
stt_service, tts_service의 로직을 HTTP로 노출하는 창구 역할입니다.
"""

import base64
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.shared.voice.schema import (
    ApiResponse,
    STTResult,
    TTSRequest,
    TTSResult,
)
from app.shared.voice.service import process_voice_pipeline
from app.shared.voice.stt_service import transcribe_audio
from app.shared.voice.tts_service import synthesize_speech

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/voice", response_model=ApiResponse)
async def voice_pipeline(
    audio: UploadFile = File(..., description="음성 파일 (wav/mp3/m4a 등)"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ApiResponse:
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/wav"
    data = await process_voice_pipeline(audio_bytes, user_id, db, content_type)
    return ApiResponse(
        success=True,
        data=data.model_dump(),
        message="음성 처리가 완료되었습니다.",
    )


@router.post("/stt", response_model=ApiResponse)
async def speech_to_text(file: UploadFile) -> ApiResponse:
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
    audio_bytes = await synthesize_speech(body.text, body.speed)
    return ApiResponse(
        success=True,
        data=TTSResult(
            audio_base64=base64.b64encode(audio_bytes).decode()
        ).model_dump(),
        message="음성 변환이 완료되었습니다.",
    )