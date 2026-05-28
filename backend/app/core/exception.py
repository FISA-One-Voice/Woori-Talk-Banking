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
