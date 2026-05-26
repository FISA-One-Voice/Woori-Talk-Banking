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


class VoiceServiceError(AppError):
    """STT / TTS 음성 서비스에서 발생하는 공통 예외 기반 클래스.

    STTError, TTSError 는 이 클래스를 상속합니다.
    main.py 의 AppError 핸들러 하나로 하위 예외를 모두 처리합니다.
    """

    pass


class STTError(VoiceServiceError):
    """Clova Speech STT 호출 실패 관련 에러"""

    pass


class TTSError(VoiceServiceError):
    """Azure TTS 호출 실패 관련 에러"""

    pass


class OpenSearchError(AppError):
    """OpenSearch 검색/색인 처리 중 발생하는 에러.

    검색 서비스에서 OpenSearchException 을 이 클래스로 래핑해 raise 합니다.
    main.py 의 AppError 핸들러 하나로 자동 처리됩니다.

    사용 예시 (core/opensearch.py):
        from opensearchpy import OpenSearchException
        from app.core.exception import OpenSearchError

        try:
            result = client.search(...)
        except OpenSearchException as e:
            raise OpenSearchError(
                code="SEARCH_FAILED",
                message="검색 중 오류가 발생했습니다.",
            ) from e
    """

    pass


class OpenSearchIndexError(OpenSearchError):
    """OpenSearch 인덱스 생성 실패 에러."""

    pass
