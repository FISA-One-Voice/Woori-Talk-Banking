import httpx
from sqlalchemy.orm import Session
from app.core.exception import AppError, VoiceServiceError
from app.core.config import settings
from app.models.user import User


async def extract_voice_vector(
    filename: str, audio_bytes: bytes, content_type: str
) -> list[float]:
    """ASV 서버에 오디오 파일을 전송하여 192차원 음성 임베딩 벡터를 추출합니다.

    Args:
        filename: 원본 오디오 파일명.
        audio_bytes: 오디오 파일의 바이너리 데이터.
        content_type: 오디오 파일의 MIME 타입.

    Returns:
        192차원의 실수 리스트(벡터).

    Raises:
        VoiceServiceError: ASV 서버와 통신할 수 없거나, 유효한 벡터를 반환하지 않은 경우.
    """
    try:
        async with httpx.AsyncClient() as client:
            files = {"file": (filename, audio_bytes, content_type)}
            response = await client.post(
                f"{settings.ASV_SERVER_URL}/enroll", files=files, timeout=10.0
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")

            if not embedding or len(embedding) != 192:
                raise VoiceServiceError(
                    code="VOICE_VECTOR_EXTRACT_FAILED",
                    message="ASV 서버에서 유효한 192차원 벡터를 반환하지 않았습니다.",
                    status_code=500,
                )
            return embedding
    except httpx.HTTPStatusError as e:
        raise VoiceServiceError(
            code="VOICE_VECTOR_EXTRACT_FAILED",
            message=f"ASV 서버 오류 (상태 코드: {e.response.status_code})",
            status_code=502,
        )
    except VoiceServiceError:
        raise
    except Exception as e:
        raise VoiceServiceError(
            code="SERVICE_UNAVAILABLE",
            message=f"ASV 서버와 통신할 수 없습니다: {str(e)}",
            status_code=503,
        )


def register_voice_vector(db: Session, user_id: str, vector: list[float]) -> dict:
    """유저 정보에 맞게 192차원 음성 벡터를 DB에 저장합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: 토큰에서 추출한 사용자 고유 ID.
        vector: 등록할 192차원의 실수 리스트.

    Returns:
        성공 여부 및 안내 메시지를 포함한 딕셔너리.

    Raises:
        AppError: 음성 벡터가 192차원이 아니거나(INVALID_REQUEST),
                  해당 유저를 찾을 수 없는 경우(USER_NOT_FOUND) 발생.
    """
    if len(vector) != 192:
        raise AppError(
            code="INVALID_REQUEST",
            message="음성 벡터는 정확히 192차원이어야 합니다.",
            status_code=400,
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise AppError(
            code="USER_NOT_FOUND", message="사용자를 찾을 수 없습니다.", status_code=404
        )

    # DB에 벡터 업데이트
    user.embedding_vector = vector
    db.commit()

    return {
        "success": True,
        "message": "음성 벡터(192차원)가 사용자의 계정에 성공적으로 등록되었습니다.",
    }
