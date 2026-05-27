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
    """STT / TTS 서비스에서 발생하는 공통 기반 에러"""

    pass


class STTError(VoiceServiceError):
    """Clova Speech STT 호출 실패 에러"""

    pass


class TTSError(VoiceServiceError):
    """Azure TTS 호출 실패 에러"""

    pass


class BalanceError(AppError):
    """잔액 조회 관련 커스텀 에러 — features/asset/"""
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
class AgentError(AppError):
    """LangGraph 에이전트 초기화·실행 중 발생하는 예외.

    shared/agent/ 모듈 전담. 주요 발생 시점:
        - build_graph() — ChatOpenAI 설정 오류, create_react_agent 초기화 실패
        - Phase 2 이후 — tool 호출 중 예외 (AgentInvokeError 등 서브클래스 추가 예정)
    """

    pass


class HistoryError(AppError):
    """거래 내역 조회 관련 커스텀 에러 — features/asset/"""

    pass