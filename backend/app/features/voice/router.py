import httpx
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.voice import service
from app.core.exception import AppError

router = APIRouter(prefix="/api/voice", tags=["Voice"])


@router.post("/register", response_model=dict)
async def register_voice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """실제 음성 파일을 받아 ASV 서버에서 192차원 벡터를 추출 후 DB에 등록합니다.

    Args:
        file: 등록할 오디오 파일 (UploadFile).
        db: 데이터베이스 세션.
        user_id: 현재 로그인된 사용자의 고유 ID (JWT 자동 추출).

    Returns:
        등록 성공 여부와 메시지를 포함하는 딕셔너리.

    Raises:
        VoiceServiceError: ASV 모델 통신 오류 또는 차원 수가 192가 아닐 때 발생.
        AppError: 사용자를 찾을 수 없을 때 발생.
    """
    audio_bytes = await file.read()

    # 1. ASV 서버 연동하여 벡터 추출 (service 계층으로 위임, 에러는 자동 전파)
    embedding = await service.extract_voice_vector(
        file.filename, audio_bytes, file.content_type
    )

    # 2. 추출된 벡터를 DB에 저장
    return service.register_voice_vector(db, user_id, embedding)
