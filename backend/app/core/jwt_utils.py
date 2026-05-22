# =============================================================================
# backend/app/core/security.py
# =============================================================================
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class AuthError(RuntimeError):
    """인증 및 JWT 토큰 처리 관련 에러"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

security = HTTPBearer()

from app.core.config import settings

def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """입력받은 평문 PIN 번호가 해시값과 일치하는지 검증합니다.
    
    bcrypt 알고리즘을 사용하여 단방향 암호화된 값끼리 안전하게 비교를 수행합니다.

    Args:
        plain_pin: 로그인 시 사용자가 입력한 평문 형태의 PIN 번호.
        hashed_pin: DB(users 테이블)에 저장되어 있는 bcrypt 기반 해시 문자열.

    Returns:
        암호가 일치하면 True, 틀리면 False.
    """
    pwd_bytes = plain_pin.encode('utf-8')
    hash_bytes = hashed_pin.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hash_bytes)

def create_access_token(data: dict) -> str:
    """Access Token을 발급합니다.
    
    사용자 인증이 완료된 후 API 접근 권한을 부여하기 위해 짧은 만료 시간을 가진 토큰을 생성합니다.

    Args:
        data: 토큰 Payload에 들어갈 데이터 (예: {"sub": "user_id"}).

    Returns:
        HS256 알고리즘으로 서명된 JWT 문자열.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Refresh Token을 발급합니다.
    
    Access Token 만료 시 재로그인 없이 토큰을 갱신하기 위해 긴 만료 시간을 가진 토큰을 생성합니다.

    Args:
        data: 토큰 Payload에 들어갈 데이터 (예: {"sub": "user_id"}).

    Returns:
        HS256 알고리즘으로 서명된 JWT 문자열.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict | None:
    """토큰을 디코딩하고 검증합니다. 만료되었거나 유효하지 않으면 None을 반환합니다."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    [FastAPI 의존성 주입]
    요청 헤더의 Bearer 토큰을 검증하고, 유효한 경우 user_id(sub)를 반환합니다.
    API 라우터에서 매개변수로 "Depends(get_current_user_id)" 와 같이 사용합니다.
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload or "sub" not in payload:
        raise AuthError(
            code="TOKEN_INVALID",
            message="토큰 위변조 또는 유효하지 않습니다."
        )
        
    return payload["sub"]
