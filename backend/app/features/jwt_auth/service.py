from fastapi import HTTPException
from app.core.jwt_utils import create_access_token, create_refresh_token, decode_token
from app.features.jwt_auth.schema import JwtTokenResponse, JwtLoginRequest

def login(req: JwtLoginRequest) -> JwtTokenResponse:
    """사용자 로그인을 목업(Mock) 처리하고 인증 토큰을 발급합니다.
    
    데이터베이스 검증 없이, 요청받은 user_id를 그대로 사용하여 
    접근 토큰(Access Token)과 갱신 토큰(Refresh Token)을 즉시 발급합니다.

    Args:
        req: 테스트용 로그인 요청 데이터 (user_id).

    Returns:
        발급된 JWT 토큰 정보(access_token, refresh_token, user_id)를 포함한 응답 객체.
    """
    token_data = {"sub": req.user_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return JwtTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=req.user_id
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
        raise HTTPException(status_code=401, detail={"error": "TOKEN_INVALID"})
    
    user_id = payload["sub"]
    new_access_token = create_access_token({"sub": user_id})
    
    return JwtTokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token_str,
        user_id=user_id
    )
