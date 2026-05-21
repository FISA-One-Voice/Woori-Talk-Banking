from fastapi import APIRouter, Depends
from app.core.jwt_utils import get_current_user_id
from app.features.jwt_auth.schema import JwtLoginRequest, JwtRefreshRequest
from app.features.jwt_auth import service

router = APIRouter(prefix="/jwt-auth", tags=["JWT Auth"])

@router.post("/login", response_model=dict)
def login(req: JwtLoginRequest):
    """더미 사용자 로그인을 처리하고 JWT 토큰을 발급합니다.
    
    실제 DB 조회 없이 토큰 생성 로직만을 테스트하기 위한 엔드포인트입니다.

    Args:
        req: 더미 로그인 요청 데이터 (user_id).

    Returns:
        발급된 JWT 토큰 정보(access_token, refresh_token)를 포함한 표준 API 응답.
    """
    data = service.login(req)
    return {
        "success": True,
        "data": data.model_dump(),
        "message": "JWT 토큰이 성공적으로 발급되었습니다."
    }

@router.post("/refresh", response_model=dict)
def refresh_token(req: JwtRefreshRequest):
    """만료된 Access Token을 갱신합니다.
    
    기존에 발급받은 Refresh Token이 유효한지 검증하고 새로운 Access Token을 생성하여 반환합니다.

    Args:
        req: 토큰 갱신 요청 데이터 (refresh_token).

    Returns:
        새로 발급된 access_token을 포함한 표준 API 응답.
    """
    data = service.refresh_tokens(req.refresh_token)
    return {
        "success": True,
        "data": data.model_dump(),
        "message": "JWT 토큰이 갱신되었습니다."
    }

@router.put("/logout", response_model=dict)
def logout(user_id: str = Depends(get_current_user_id)):
    """사용자를 로그아웃 처리합니다.
    
    요청 헤더의 Bearer 토큰을 검증하여 유효한 토큰인지 확인한 후 성공 응답을 반환합니다.

    Args:
        user_id: 검증된 JWT 토큰에서 추출한 사용자 ID.

    Returns:
        로그아웃된 user_id를 포함한 표준 API 응답.
    """
    return {
        "success": True,
        "data": {"logged_out_user": user_id},
        "message": "로그아웃 되었습니다. 클라이언트에서 토큰을 삭제해주세요."
    }
