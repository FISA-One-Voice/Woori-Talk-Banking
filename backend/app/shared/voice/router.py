"""
stt_service, tts_service의 로직을 HTTP로 노출하는 창구 역할입니다.
비즈니스 로직은 없고 요청을 받아서 서비스에 넘기고 결과를 포장해서 돌려줍니다.

엔드포인트:
    POST /api/voice         — 통합 음성 파이프라인 (Issue #7)
    POST /api/voice/stt     — STT 단독 변환
    POST /api/voice/tts     — TTS 단독 변환
"""

import base64
import logging

from fastapi import APIRouter, Depends, File, UploadFile

logger = logging.getLogger(__name__)
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
    """음성 파이프라인 통합 엔드포인트 (Issue #7)."""
    audio_bytes = await audio.read()
    raw_ct = audio.content_type or ""
    logger.info("[Voice] received content_type=%r size=%d", raw_ct, len(audio_bytes))
    # React Native FormData가 content_type을 임의로 바꾸는 경우 대응 — WAV로 고정
    content_type = "audio/wav"
    data = await process_voice_pipeline(audio_bytes, user_id, db, content_type)
    return ApiResponse(
        success=True,
        data=data.model_dump(),
        message="음성 처리가 완료되었습니다.",
    )


@router.post("/stt", response_model=ApiResponse)
async def speech_to_text(file: UploadFile) -> ApiResponse:
    """업로드된 음성 파일을 텍스트로 변환합니다."""
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
    """텍스트를 MP3 음성으로 변환합니다."""
    audio_bytes = await synthesize_speech(body.text, body.speed)
    return ApiResponse(
        success=True,
        data=TTSResult(
            audio_base64=base64.b64encode(audio_bytes).decode()
        ).model_dump(),
        message="음성 변환이 완료되었습니다.",
    )
