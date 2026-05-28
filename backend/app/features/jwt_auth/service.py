from sqlalchemy.orm import Session
from app.core.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_pin,
)
from app.core.exception import AuthError
from app.features.jwt_auth.schema import JwtTokenResponse, JwtLoginRequest
from app.models.user import User


def login(db: Session, req: JwtLoginRequest) -> JwtTokenResponse:
    """사용자 전화번호와 PIN을 검증하고 인증 토큰을 발급합니다.

    실제 데이터베이스(users 테이블)를 조회하여 유효한 사용자인지 확인한 뒤,
    접근 토큰(Access Token)과 갱신 토큰(Refresh Token)을 발급합니다.

    Args:
        db: 데이터베이스 세션.
        req: 로그인 요청 데이터 (전화번호, PIN).

    Returns:
        발급된 JWT 토큰 정보(accessToken, refreshToken, userId)를 포함한 응답 객체.

    Raises:
        HTTPException: 가입되지 않은 전화번호인 경우(USER_NOT_FOUND).
        HTTPException: PIN 번호가 틀린 경우(INVALID_PIN).
    """
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        raise AuthError(
            code="USER_NOT_FOUND",
            message="가입되지 않은 전화번호입니다.",
            status_code=404,
        )

    if not verify_pin(req.pin, user.pin_hash):
        raise AuthError(
            code="UNAUTHORIZED",
            message="비밀번호가 일치하지 않습니다.",
            status_code=401,
        )

    token_data = {"sub": str(user.user_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return JwtTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.user_id),
    )


def refresh_tokens(refresh_token_str: str) -> JwtTokenResponse:
    """리프레시 토큰을 파싱하여 새로운 액세스 토큰을 발급합니다.

    전달된 토큰이 조작되지 않았는지 검증하고, 추출된 유저 ID로 새 토큰을 만듭니다.

    Args:
        refresh_token_str: 클라이언트로부터 전달받은 Refresh Token 문자열.

    Returns:
        새로 발급된 Access Token과 기존 Refresh Token을 포함한 응답 객체.

    Raises:
        HTTPException: 토큰이 유효하지 않거나 만료된 경우(TOKEN_INVALID).
    """
    payload = decode_token(refresh_token_str)
    if not payload or "sub" not in payload:
        raise AuthError(
            code="TOKEN_INVALID",
            message="토큰 위변조 또는 유효하지 않은 리프레시 토큰입니다.",
            status_code=401,
        )

    user_id = payload["sub"]
    new_access_token = create_access_token({"sub": user_id})

    return JwtTokenResponse(
        access_token=new_access_token, refresh_token=refresh_token_str, user_id=user_id
    )
