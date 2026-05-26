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
    """
    (MOCK) 사용자 음성 벡터 등록 엔드포인트
    
    실제 음성 파일 추출 로직이 연결되기 전, 192차원 벡터 배열을 입력받아 
    현재 로그인된 사용자의 정보에 맞게 DB에 업데이트하는 기본 로직입니다.
    """
    return service.register_voice_vector(db, user_id, req.embedding_vector)
