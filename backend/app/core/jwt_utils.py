# =============================================================================
# backend/app/core/security.py
# =============================================================================
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exception import AuthError

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
    pwd_bytes = plain_pin.encode("utf-8")
    hash_bytes = hashed_pin.encode("utf-8")
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
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
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
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    """JWT 토큰을 디코딩하고 서명을 검증합니다.

    Args:
        token: 검증할 JWT 문자열.

    Returns:
        유효한 토큰이면 payload dict, 만료되었거나 유효하지 않으면 None.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_optional_user_id(request: Request) -> Optional[str]:
    """선택적 인증 의존성. 토큰이 있으면 user_id 반환, 없거나 유효하지 않으면 None 반환.

    로그인 없이도 접근 가능한 API에서 '로그인 시 추가 정보 제공' 용도로 사용합니다.
    예) GET /events/{id} — 비로그인 시 has_participated=False, 로그인 시 실제 참여 여부 반환
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    return payload["sub"]


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
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
            message="토큰 위변조 또는 유효하지 않습니다.",
            status_code=401,
            user_message="로그인 정보가 만료되었습니다. 다시 로그인해 주세요.",
        )

    return payload["sub"]
