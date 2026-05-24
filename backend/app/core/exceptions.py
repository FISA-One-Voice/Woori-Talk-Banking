class AppError(Exception):
    """모든 커스텀 에러의 최상위 부모 클래스입니다."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class AuthError(AppError):
    """인증 및 JWT 토큰 처리 관련 커스텀 에러"""
    pass
