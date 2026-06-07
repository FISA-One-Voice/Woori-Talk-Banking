from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.shared.agent.state import VoiceState
from app.shared.agent.prompts import RAG_SYSTEM_PROMPT
from app.shared.agent.tools.financial_qa import search_financial_docs
from app.shared.agent.tools.market_info import get_exchange_rate, get_base_rate

# =====================================================================
# Dev-D 소유: RAG 에이전트 도메인 액션
# =====================================================================
RAG_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "financial_qa", "exchange_rate", "interest_rate", "event",
})

# =====================================================================
# LLM 초기화 및 RAG 에이전트(React) 조립
# =====================================================================
# 온도(temperature)를 0으로 설정하여 일관되고 보수적인 답변 유도
_llm = ChatOpenAI(model=settings.OPENAI_MODEL, api_key=settings.OPENAI_CHAT_API_KEY, temperature=0)

# search_financial_docs(오픈서치)와 market_info(환율/금리) 툴들을 장착합니다.
rag_agent = create_react_agent(
    model=_llm,
    tools=[search_financial_docs, get_exchange_rate, get_base_rate],
    prompt=RAG_SYSTEM_PROMPT,
    state_schema=VoiceState,  # 반드시 명시: 부모 VoiceState와 스키마를 일치시킴
)

async def rag_node(state: VoiceState) -> dict:
    """부모 그래프(Supervisor)에서 이 노드를 호출할 때 사용될 래퍼입니다.
    
    RAG 에이전트 본체를 실행한 뒤, 아키텍처 원칙에 따라 화면 이동 권한이 없음을 보장하기 위해
    `navigate_to: None`을 하드코딩하여 반환합니다.
    """
    result = await rag_agent.ainvoke(state)
    
    # React Agent가 반환한 메시지 목록에 navigate_to=None을 강제 주입하여 반환
    return {
        "messages": result["messages"],
        "navigate_to": None,
    }
