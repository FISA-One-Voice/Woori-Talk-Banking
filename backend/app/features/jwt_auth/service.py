# =============================================================================
# backend/app/features/jwt_auth/service.py
# =============================================================================
from fastapi import HTTPException
from app.core.jwt_utils import create_access_token, create_refresh_token, decode_token
from app.features.jwt_auth.schema import JwtTokenResponse

def generate_tokens(user_id: str) -> JwtTokenResponse:
    """
    주어진 user_id에 대한 Access/Refresh 토큰을 발급합니다.
    """
    token_data = {"sub": user_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return JwtTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id
    )

def refresh_tokens(refresh_token_str: str) -> JwtTokenResponse:
    """
    기존 리프레시 토큰을 파싱하여 새로운 액세스 토큰을 발급합니다.
    """
    payload = decode_token(refresh_token_str)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail={"error": "TOKEN_INVALID"})
    
    user_id = payload["sub"]
    new_access_token = create_access_token({"sub": user_id})
    
    return JwtTokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token_str,
        user_id=user_id
    )
