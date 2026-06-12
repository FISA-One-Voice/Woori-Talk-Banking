import httpx
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.voice import service
from app.core.exception import AppError
from app.models.user import User

router = APIRouter(prefix="/api/voice", tags=["Voice"])


@router.post("/register", response_model=dict)
async def register_voice(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """3분할 오디오 파일들을 병합하여 ASV 서버에서 192차원 벡터를 추출 후 DB에 등록합니다.

    Args:
        files: 프론트엔드에서 전송된 3개의 오디오 파일 리스트.
        db: 데이터베이스 세션.
        user_id: 현재 로그인된 사용자의 고유 ID (JWT 자동 추출).

    Returns:
        등록 성공 여부와 메시지를 포함하는 딕셔너리.

    Raises:
        VoiceServiceError: 오디오 병합 실패 또는 ASV 서버 통신 오류 발생 시.
        AppError: 사용자를 찾을 수 없을 때 발생.
    """
    files_bytes = [await file.read() for file in files]

    # 1. 병합 및 ASV 서버 연동 (service 계층 위임)
    embedding = await service.extract_voice_vector(files_bytes)

    # 2. 추출된 벡터를 DB에 저장
    return service.register_voice_vector(db, user_id, embedding)
