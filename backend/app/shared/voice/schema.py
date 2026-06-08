from typing import Any

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """POST /api/voice/tts 요청 바디."""

    text: str = Field(..., max_length=1000)
    speed: float = Field(default=1.0)


class STTResult(BaseModel):
    """STT 변환 성공 시 data 필드에 담기는 결과."""

    transcript: str


class TTSResult(BaseModel):
    """TTS 변환 성공 시 data 필드에 담기는 결과."""

    audio_base64: str
    mime_type: str = "audio/mpeg"


class ASVResult(BaseModel):
    """ASV EC2 서버(POST /verify) 호출 결과.

    Attributes:
        verified: True이면 본인 인증 성공 (is_same_speaker).
        score: 코사인 유사도 점수 (0.0 ~ 1.0). 임계값 기본값: 0.6404.
    """

    verified: bool
    score: float



class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    message: str
    code: str | None = None


class VoiceResponseData(BaseModel):
    """POST /api/voice 통합 응답 data 필드 (Issue #21).

    Issue #7(음성 파이프라인)에서 router.py가 이 스키마를 사용해
    표준 봉투(ApiResponse)로 반환한다.

    Attributes:
        audio: base64 인코딩된 MP3 오디오. Issue #7에서 실제 TTS 결과가 채워진다.
        navigate_to: 프론트엔드 화면 이동 신호 (Expo Router 경로). 없으면 None.
            예: "transfer", "balance", "auto-transfer"
        collected_slots: 현재까지 수집된 슬롯 현황. 프론트엔드 단계 판단에 사용.
            예: {"recipient": "엄마", "amount": 100000}
        awaiting_confirmation: True이면 사용자의 "네/아니오" 텍스트 확인 대기 중.
        awaiting_asv_audio: True이면 다음 오디오 입력이 ASV 검증용임.
            프론트엔드는 "목소리로 인증해 주세요" 오버레이를 표시한다.
        awaiting_memo_decision: True이면 이체 직후 메모 제안에 대한 응답 대기 중.
        awaiting_transfer_clarification: True이면 전화·계좌만 말한 뒤 송금 여부 확인 대기 중.

    Usage (Issue #7 router.py):
        data = VoiceResponseData(
            audio=base64_mp3,
            navigate_to=result["navigate_to"],
            collected_slots=result["collected_slots"],
            awaiting_confirmation=result["awaiting_confirmation"],
            awaiting_asv_audio=result["awaiting_asv_audio"],
        )
        return ApiResponse(success=True, data=data.model_dump(), message=tts_text)
    """

    audio: str = ""
    """base64 인코딩된 MP3. Issue #7에서 실제 TTS 결과로 채워진다."""

    navigate_to: str | None = None
    """이동할 화면 이름 (Expo Router 경로). 없으면 null."""

    collected_slots: dict = {}
    """현재까지 수집된 슬롯. 프론트엔드 stepResolver에서 단계 판단에 사용."""

    awaiting_confirmation: bool = False
    """True이면 '네' 또는 '아니오' 응답 대기 중."""

    awaiting_asv_audio: bool = False
    """True이면 다음 입력이 ASV 음성 인증용. ASV_REQUIRED_ACTIONS에서만 True."""

    awaiting_memo_decision: bool = False
    """True이면 이체 완료 후 메모 제안에 대한 음성 응답 대기 중."""

    awaiting_transfer_clarification: bool = False
    """True이면 송금 의도 확인(네/아니오) 응답 대기 중."""

    transcript: str | None = None
    """STT 변환 결과 텍스트. 정상 흐름에서만 채워지며 ASV 인증 흐름에서는 None."""

    pending_action: str | None = None
    """현재 진행 중인 액션 이름 (e.g. 'transfer', 'auto_transfer', 'cancel_auto_transfer').
    프론트엔드가 액션별로 다른 UI/단계를 렌더링할 때 사용."""
