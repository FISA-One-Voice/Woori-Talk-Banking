import logging
import time

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.shared.agent.state import VoiceState
from app.shared.agent.prompts import RAG_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

RAG_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "financial_qa", "exchange_rate", "interest_rate",
})


def build_rag_graph(tools: list):
    """RAG 에이전트 그래프를 빌드한다. tools는 외부(supervisor)에서 주입된다."""
    llm = ChatOpenAI(model=settings.OPENAI_MODEL, api_key=settings.OPENAI_CHAT_API_KEY, temperature=0)
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=RAG_SYSTEM_PROMPT,
        state_schema=VoiceState,
    )

    async def _rag_graph(state: VoiceState) -> dict:
        user_id = state.get("user_id", "")
        logger.info("[RAG] invoke start user_id=%s", user_id)
        t0 = time.monotonic()
        result = await agent.ainvoke(state)
        tool_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "[RAG] invoke complete user_id=%s messages=%d duration_ms=%d",
            user_id, len(result.get("messages", [])), tool_ms,
        )
        return {
            "messages": result["messages"],
            "navigate_to": None,
            "tool_execution_ms": None,
        }

    return _rag_graph
