class AuthError(RuntimeError):
    """인증 및 JWT 토큰 처리 관련 에러"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
