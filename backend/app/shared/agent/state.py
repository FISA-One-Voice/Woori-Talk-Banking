"""VoiceState — LangGraph 멀티턴 대화 상태 정의 (Issue #21).

MemorySaver를 통해 thread_id=user_id로 세션 간 상태가 유지된다.

Design Ref (Issue #21):
    §state.py — VoiceState TypedDict
"""

from typing import Annotated, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class VoiceState(TypedDict):
    """LangGraph 에이전트 멀티턴 대화 상태.

    MemorySaver를 통해 동일한 thread_id (= user_id) 내에서
    요청 간 상태가 유지됩니다. 새 턴마다 messages만 추가하면
    나머지 슬롯·확인 상태는 자동으로 이어집니다.

    Attributes:
        messages: 대화 이력. add_messages 리듀서로 자동 누적.
        user_id: JWT에서 추출한 사용자 ID. MemorySaver thread_id와 동일.
        pending_action: 진행 중인 액션 이름 ("transfer", "auto_transfer").
            None이면 대기 상태.
        collected_slots: 수집된 슬롯 값.
            예: {"recipient": "엄마", "amount": 100000}
        awaiting_confirmation: True이면 사용자의 "네/아니오" 확인 대기 중.
        awaiting_asv_audio: True이면 다음 오디오 입력이 ASV 검증용임.
            router.py에서 이 값을 확인해 ASV EC2 서버로 라우팅한다.
        asv_retry_count: ASV 검증 실패 횟수. 3회 초과 시 pending_action 취소.
        navigate_to: 프론트엔드 화면 이동 신호 (Expo Router 경로).
            intent 첫 감지 시에만 설정되고, 이후 턴에서는 None.
        execution_ready: True이면 사용자 확인 완료 + ASV 불필요 → execute_node로 즉시 실행.
            intent_node에서 "네" 수신 후 설정. execute_node 완료 후 False로 초기화.
        recipient_validated: True이면 recipient 슬롯이 resolve_node를 통과한 상태.
            새 인텐트 감지 또는 취소 시 False로 초기화.
        last_tx_id: transfer execute_node 성공 시 설정. add_note가 지정 tx에 메모할 때 사용.
    """

    messages: Annotated[list, add_messages]
    user_id: str
    pending_action: str | None
    collected_slots: dict
    awaiting_confirmation: bool
    awaiting_asv_audio: bool
    asv_retry_count: int
    navigate_to: str | None
    execution_ready: bool
    recipient_validated: bool
    last_tx_id: NotRequired[str | None]
