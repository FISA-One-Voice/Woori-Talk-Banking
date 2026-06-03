"""LangGraph 음성 세션·대화 이력 초기화 헬퍼."""

from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES


def clear_conversation_messages() -> list:
    """MemorySaver에 쌓인 messages를 비운다."""
    return [RemoveMessage(id=REMOVE_ALL_MESSAGES)]
