"""
stt_service, tts_service의 로직을 HTTP로 노출하는 창구 역할입니다.
비즈니스 로직은 없고 요청을 받아서 서비스에 넘기고 결과를 포장해서 돌려줍니다.

엔드포인트:
    POST /api/voice         — 통합 음성 파이프라인 (Issue #7)
    POST /api/voice/stt     — STT 단독 변환
    POST /api/voice/tts     — TTS 단독 변환
"""

import base64

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import decode_token
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

# 토큰 없이도 동작하는 임시 인증 의존성 (개발용)
_optional_bearer = HTTPBearer(auto_error=False)


def _get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
) -> str:
    """JWT가 있으면 검증 후 user_id 반환, 없으면 개발용 고정 ID 반환."""
    if credentials is None:
        return "dev-user"
    payload = decode_token(credentials.credentials)
    if payload and "sub" in payload:
        return payload["sub"]
    return "dev-user"


@router.post("/voice", response_model=ApiResponse)
async def voice_pipeline(
    audio: UploadFile = File(..., description="음성 파일 (wav/mp3/m4a 등)"),
    user_id: str = Depends(_get_optional_user_id),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """음성 파이프라인 통합 엔드포인트 (Issue #7).

    STT → LangGraph 에이전트 → TTS 흐름을 조율하며,
    ASV 인증이 필요한 경우 anti-spoofing + ASV EC2 병렬 호출로 분기한다.

    LangGraph MemorySaver 기반 멀티턴 상태(thread_id=user_id)를 유지하므로
    프론트엔드는 별도의 상태 플래그 없이 오디오만 전송하면 된다.

    Args:
        audio: 업로드된 음성 파일 (multipart/form-data).
        user_id: JWT Bearer 토큰에서 추출한 사용자 ID.
        db: DB 세션 (ASV 흐름에서 users.embedding_vector 조회에 사용).

    Returns:
        ApiResponse — data 필드에 VoiceResponseData 포함:
            - audio: base64 인코딩된 MP3 TTS 응답
            - navigate_to: 화면 이동 신호 (Expo Router 경로, 없으면 null)
            - collected_slots: 현재 수집된 슬롯 현황
            - awaiting_confirmation: True이면 '네/아니오' 대기 중
            - awaiting_asv_audio: True이면 다음 오디오가 ASV 검증용

    Raises:
        401 Unauthorized: JWT 토큰이 없거나 유효하지 않은 경우.
        400 Bad Request: 오디오 형식 오류 또는 용량 초과.
        422 Unprocessable Entity: 사용자 음성 미등록.
        502 Bad Gateway: ASV EC2 서버 통신 오류.
        503 Service Unavailable: STT/TTS 외부 API 장애.
    """
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
