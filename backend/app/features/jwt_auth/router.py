# =============================================================================
# backend/app/features/jwt_auth/router.py
# =============================================================================
from fastapi import APIRouter, Depends
from app.core.jwt_utils import get_current_user_id
from app.features.jwt_auth.schema import JwtLoginRequest, JwtRefreshRequest, JwtTokenResponse
from app.features.jwt_auth import service

router = APIRouter(prefix="/jwt-auth", tags=["JWT Auth"])

@router.post("/login", response_model=dict)
def login_and_get_token(req: JwtLoginRequest):
    """
    [이슈 #7] JWT 토큰 발급 (로그인 대체)
    데이터베이스 로직 없이 순수하게 토큰만 발급합니다.
    """
    data = service.generate_tokens(req.user_id)
    return {
        "success": True,
        "data": data.model_dump(),
        "message": "JWT 토큰이 성공적으로 발급되었습니다."
    }

@router.post("/refresh", response_model=dict)
def refresh_token(req: JwtRefreshRequest):
    """
    [이슈 #7] JWT 토큰 갱신
    """
    data = service.refresh_tokens(req.refresh_token)
    return {
        "success": True,
        "data": data.model_dump(),
        "message": "JWT 토큰이 갱신되었습니다."
    }

@router.put("/logout", response_model=dict)
def logout(user_id: str = Depends(get_current_user_id)):
    """
    [이슈 #7] JWT 로그아웃 (토큰 무효화 테스트용)
    """
    return {
        "success": True,
        "data": {"logged_out_user": user_id},
        "message": "로그아웃 되었습니다. 클라이언트에서 토큰을 삭제해주세요."
    }
