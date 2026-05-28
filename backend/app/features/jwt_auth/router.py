from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.jwt_auth.schema import JwtLoginRequest, JwtRefreshRequest
from app.features.jwt_auth import service

router = APIRouter(prefix="/jwt-auth", tags=["JWT Auth"])


@router.post("/login", response_model=dict)
def login(req: JwtLoginRequest, db: Session = Depends(get_db)):
    """사용자 로그인을 처리하고 JWT 토큰을 발급합니다.

    전화번호와 PIN 번호를 DB의 정보와 대조하여 유효성을 검사합니다.

    Args:
        req: 로그인 요청 데이터 (phone, pin).
        db: 데이터베이스 세션 (의존성 주입).

    Returns:
        발급된 JWT 토큰 정보(accessToken, refreshToken)를 포함한 표준 API 응답.
    """
    data = service.login(db, req)
    return {
        "success": True,
        "data": data.model_dump(by_alias=True),
        "message": "로그인 성공 및 토큰이 발급되었습니다.",
    }


@router.post("/refresh", response_model=dict)
def refresh_token(req: JwtRefreshRequest):
    """만료된 Access Token을 갱신합니다.

    기존에 발급받은 Refresh Token이 유효한지 검증하고 새로운 Access Token을 생성하여 반환합니다.

    Args:
        req: 토큰 갱신 요청 데이터 (refreshToken).

    Returns:
        새로 발급된 accessToken을 포함한 표준 API 응답.
    """
    data = service.refresh_tokens(req.refresh_token)
    return {
        "success": True,
        "data": data.model_dump(by_alias=True),
        "message": "JWT 토큰이 갱신되었습니다.",
    }


@router.put("/logout", response_model=dict)
def logout(user_id: str = Depends(get_current_user_id)):
    """사용자를 로그아웃 처리합니다.

    요청 헤더의 Bearer 토큰을 검증하여 유효한 토큰인지 확인한 후 성공 응답을 반환합니다.

    Args:
        user_id: 검증된 JWT 토큰에서 추출한 사용자 ID.

    Returns:
        로그아웃된 userId를 포함한 표준 API 응답.
    """
    return {
        "success": True,
        "data": {"userId": user_id},
        "message": "로그아웃 되었습니다. 클라이언트에서 토큰을 삭제해주세요.",
    }
