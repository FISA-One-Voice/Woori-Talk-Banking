class AppError(Exception):
    """모든 커스텀 에러의 최상위 부모 클래스입니다."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        user_message: str | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.user_message = user_message if user_message is not None else message
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


class ASVError(VoiceServiceError):
    """ai/asv/ 화자 인증 서버(CAM++) HTTP 호출 실패 관련 에러.
    ASV 서버가 반환한 에러 응답을 메인 백엔드에서 re-raise할 때 사용한다.
    code / message 는 ASV 서버 응답의 동일 필드를 그대로 전달한다.
    status_code 는 upstream 오류이므로 502를 기본값으로 사용한다.
    """

    pass


class BalanceError(AppError):
    """잔액 조회 관련 커스텀 에러 — features/asset/

    코드 목록:
        ACCOUNT_NOT_FOUND  계좌 없음 (404)
    """

    pass


class HistoryError(AppError):
    """거래 내역 조회 관련 커스텀 에러 — features/asset/

    코드 목록:
        TX_NOT_FOUND       거래·지출 내역 없음 (404)
        INVALID_PERIOD     유효하지 않은 조회 기간 (400)
        MISSING_CATEGORY   카테고리 미지정 (400)
    """

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


class RecipientError(AppError):
    """수취인 조회·등록 관련 에러"""

    pass


class AgentError(AppError):
    """LangGraph 에이전트 초기화·실행 중 발생하는 예외.
    shared/agent/ 모듈 전담. 주요 발생 시점:
        - build_graph() — ChatOpenAI 설정 오류, create_react_agent 초기화 실패
        - Phase 2 이후 — tool 호출 중 예외 (AgentInvokeError 등 서브클래스 추가 예정)
    """

    pass
class EventError(AppError):
    """이벤트 기능(features/event/) 관련 커스텀 에러 기반 클래스."""

    pass


class EventNotFoundError(EventError):
    """이벤트를 찾을 수 없을 때 발생합니다."""

    pass


class AlreadyParticipatedError(EventError):
    """이미 참여한 이벤트에 다시 참여할 때 발생합니다."""

    pass


class TransferError(AppError):
    """이체 처리 중 발생하는 에러.

    코드 목록:
        INVALID_ACCOUNT_FORMAT     계좌번호 형식 오류 (400)
        TRANSFER_ACCOUNT_NOT_FOUND 출금 계좌 없음 (404)
        TRANSFER_PENDING           동일 key 이체 진행 중 (409)
        IDEMPOTENCY_KEY_USED       동일 key가 이미 실패 처리됨 (409)
        INSUFFICIENT_BALANCE       잔액 부족 (400)
        TRANSACTION_NOT_FOUND      트랜잭션 없음 (404)
    """

    pass


class AutoTransferError(AppError):
    """자동이체 등록·실행 중 발생하는 예외."""


class MarketError(AppError):
    """시장 지표(환율, 금리) 조회 관련 커스텀 에러 — features/market/"""

    pass
