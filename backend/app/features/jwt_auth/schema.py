# =============================================================================
# backend/app/features/jwt_auth/schema.py
# =============================================================================
from pydantic import BaseModel
from typing import Optional

class JwtLoginRequest(BaseModel):
    """
    로그인을 통해 JWT 발급을 요청하는 스키마
    """
    user_id: str

class JwtRefreshRequest(BaseModel):
    """
    JWT 토큰 갱신 요청 스키마
    """
    refresh_token: str

class JwtTokenResponse(BaseModel):
    """
    JWT 발급 완료 응답 스키마
    """
    access_token: str
    refresh_token: Optional[str] = None
    user_id: str
