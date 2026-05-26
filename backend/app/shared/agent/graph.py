# Design Ref: §3.1 — build_graph() 핵심 로직. Phase 1: create_react_agent 기반.
# Design Ref: §2.2 — Phase 2.5(Issue #21)에서 이 함수 내부만 StateGraph로 교체.
"""LangGraph 에이전트 그래프 빌드 모듈.

공개 인터페이스:
    build_graph(tools) → CompiledGraph

Phase 1 구현: langgraph-prebuilt 의 create_react_agent 사용.
Phase 2.5 교체 예정: Issue #21 — StateGraph + MemorySaver + VoiceState.

호출부(shared/voice/router.py, Issue #7)는 이 함수 시그니처에만 의존합니다.
내부 구현이 바뀌어도 호출부는 수정이 필요하지 않습니다.
"""

import openai
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph  # 실제 반환 타입
from langgraph.prebuilt import create_react_agent

# NOTE: create_react_agent 는 LangGraph v1.0 에서 deprecated.
# 대안: from langchain.agents import create_agent
# 단, Issue #21 에서 StateGraph 로 전체 교체 예정이므로 그대로 유지.
from app.core.config import settings
from app.core.exception import AgentError
from app.shared.agent.prompts import SYSTEM_PROMPT


def build_graph(tools: list) -> CompiledStateGraph:
    """모든 tool을 받아 LangGraph 그래프를 빌드한다.

    Phase 1 골격 구현. 빈 tool 리스트([])도 허용하므로
    Phase 2 tool이 완성되기 전에도 에이전트 초기화가 가능하다.

    Args:
        tools: LangChain @tool 데코레이터로 정의된 함수 목록.
               빈 리스트([])도 허용 — Phase 1 골격 초기화 목적.
               Phase 2 완료 후 ALL_TOOLS 를 전달한다.

    Returns:
        .invoke() / .ainvoke() 호출 가능한 컴파일된 LangGraph 그래프.
        voice/router.py 에서 아래와 같이 사용한다:

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=transcript)]},
                config={"configurable": {"thread_id": user_id}},
            )
            response_text = result["messages"][-1].content

    Raises:
        AgentError(code="AGENT_CONFIG_ERROR"): OPENAI_CHAT_API_KEY 미설정·형식 오류 등
            ChatOpenAI 설정 단계에서 openai.OpenAIError 가 발생한 경우.
        AgentError(code="AGENT_INIT_FAILED"): create_react_agent 초기화 중
            예기치 못한 예외가 발생한 경우 (잘못된 tool 형식 등).

    Note:
        temperature=0 — 뱅킹 도메인 특성상 일관된 응답이 창의성보다 중요.
        OPENAI_MODEL — 환경변수로 모델 교체 가능 (기본: gpt-4o-mini).

    Phase 2.5 교체 계획 (Issue #21):
        이 함수 내부를 StateGraph + MemorySaver 로 교체한다.
        시그니처(tools: list) → CompiledGraph 는 변경하지 않는다.
    """
    # Plan SC: build_graph([]) 호출 시 오류 없이 초기화 (Issue #5 완료 조건)
    # api_key를 명시적으로 전달 — settings(config.py → .env)가 키 관리의 단일 출처.
    # 전달하지 않으면 OpenAI SDK가 os.environ을 직접 읽어 settings 우회 발생.
    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            temperature=0,  # 뱅킹 도메인: 일관성 > 창의성
        )
    except openai.OpenAIError as e:
        raise AgentError(
            code="AGENT_CONFIG_ERROR",
            message="AI 에이전트 설정 오류가 발생했습니다.",
            status_code=500,
        ) from e

    # Design Ref: §2.2 — Phase 1은 create_react_agent (단순 ReAct 루프)
    try:
        graph = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )
    except Exception as e:
        raise AgentError(
            code="AGENT_INIT_FAILED",
            message="AI 에이전트를 초기화하지 못했습니다.",
            status_code=500,
        ) from e

    return graph
