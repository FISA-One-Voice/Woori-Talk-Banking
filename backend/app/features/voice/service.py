from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User

def register_voice_vector(db: Session, user_id: str, vector: list[float]) -> dict:
    """
    유저 정보에 맞게 192차원 음성 벡터를 DB에 저장합니다.
    """
    if len(vector) != 192:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="음성 벡터는 정확히 192차원이어야 합니다."
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )

    # DB에 벡터 업데이트
    user.embedding_vector = vector
    db.commit()
    
    return {
        "success": True,
        "message": "음성 벡터(192차원)가 사용자의 계정에 성공적으로 등록되었습니다."
    }
