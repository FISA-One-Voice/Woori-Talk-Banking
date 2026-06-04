"""LangGraph messages에서 TTS용 어시스턴트 발화를 추출한다."""

from langchain_core.messages import AIMessage, BaseMessage

_DEFAULT_TTS_FALLBACK = (
    "이체, 잔액 조회, 홈 이동 중 무엇을 도와드릴까요? 말씀해 주세요."
)


def last_assistant_text(messages: list[BaseMessage] | list) -> str | None:
    """대화 이력에서 마지막 AIMessage 내용을 반환한다. 없으면 None."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            return str(content).strip() if content else None
        if getattr(msg, "type", None) == "ai":
            content = msg.content
            return str(content).strip() if content else None
    return None


def tts_text_from_messages(
    messages: list[BaseMessage] | list,
    *,
    fallback: str = _DEFAULT_TTS_FALLBACK,
) -> str:
    """TTS에 사용할 텍스트. HumanMessage(STT)를 그대로 읽지 않도록 AIMessage만 사용한다."""
    assistant = last_assistant_text(messages)
    if assistant:
        return assistant
    return fallback
