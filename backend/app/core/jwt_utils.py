# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exception import AuthError
from app.core.config import settings

security = HTTPBearer()


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """입력받은 평문 PIN 번호가 해시값과 일치하는지 검증합니다."""
    pwd_bytes = plain_pin.encode("utf-8")
    hash_bytes = hashed_pin.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def create_access_token(data: dict) -> str:
    """Access Token을 발급합니다."""
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
    """Refresh Token을 발급합니다."""
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
    """JWT 토큰을 디코딩하고 서명을 검증합니다."""
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
    """선택적 인증 의존성. 토큰이 있으면 user_id 반환, 없거나 유효하지 않으면 None 반환."""
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
    """
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or "sub" not in payload:
        raise AuthError(
            code="TOKEN_INVALID",
            message="토큰 위변조 또는 유효하지 않습니다.",
            status_code=401,
        )

    return payload["sub"]
