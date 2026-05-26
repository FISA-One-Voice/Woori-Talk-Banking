from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.voice import service
from app.features.voice.schema import VoiceRegistrationRequest

router = APIRouter(prefix="/voice", tags=["Voice"])

@router.post("/register", response_model=dict)
def register_voice(
    req: VoiceRegistrationRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """사용자의 192차원 음성 벡터를 DB에 등록합니다.

    실제 음성 파일 추출 로직이 연결되기 전, 192차원 벡터 배열을 입력받아 
    현재 로그인된 사용자의 정보에 맞게 DB에 업데이트하는 MOCK 엔드포인트입니다.

    Args:
        req: 192차원 음성 벡터가 포함된 요청 바디.
        db: 데이터베이스 세션.
        user_id: 현재 로그인된 사용자의 고유 ID (JWT 자동 추출).

    Returns:
        등록 성공 여부와 메시지를 포함하는 딕셔너리.
    """
    return service.register_voice_vector(db, user_id, req.embedding_vector)
