class VoiceServiceError(Exception):
    """STT / TTS 음성 서비스에서 발생하는 공통 예외 기반 클래스.

    STTError, TTSError 는 이 클래스를 상속합니다.
    main.py 의 전역 핸들러는 이 클래스 하나만 등록하면 하위 예외를 모두 처리합니다.

    Attributes:
        code: 에러 식별 코드 (예: "STT_FAILED", "SERVICE_UNAVAILABLE").
        message: 사람이 읽는 에러 설명.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
