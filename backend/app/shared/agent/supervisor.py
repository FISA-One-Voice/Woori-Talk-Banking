"""멀티에이전트 Supervisor 패턴 구현.

Supervisor는 사용자 발화를 도메인(transfer/asset/rag/cancel/unknown)으로
분류하고 해당 서브그래프로 라우팅한다. TransferAgent 소유 세션 상태는 읽기만 하고
수정하지 않는다. 단, cancel_node는 P4 예외로 세션 필드를 직접 초기화한다.

Design Ref: docs/02-design/features/dev-a-supervisor-plan.design.md §4.5
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.exception import EventError
from app.shared.agent.prompts import DOMAIN_CLASSIFY_PROMPT
from app.shared.agent.session_reset import clear_conversation_messages
from app.shared.agent.state import VoiceState
from app.shared.agent.transfer_intent import is_plain_transfer_start

logger = logging.getLogger(__name__)

# ── 키워드 집합 ──────────────────────────────────────────────────────────────────

CANCEL_KEYWORDS: frozenset[str] = frozenset(
    {
        "취소",
        "그만",
        "됐어",
        "멈춰",
        "중단",
        "취소해",
        "취소해줘",
        "그만해",
        "그만해줘",
        "멈춰줘",
        "안할게",
    }
)

NAVIGATION_KEYWORDS: frozenset[str] = frozenset(
    {
        "홈으로",
        "처음으로",
        "홈화면",
        "홈이동",
        "메인화면",
        "홈",
        "처음",
    }
)

# gpt-4o-mini 분류에서 허용되는 도메인 — 예상 외 출력은 "unknown"으로 정규화한다.
# NodeNotFoundError 방지를 위해 이 집합 외 값은 반드시 "unknown"으로 교체해야 한다.
_VALID_DOMAINS: frozenset[str] = frozenset({"transfer", "asset", "rag", "unknown"})

# ── 헬퍼 함수 ────────────────────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    """공백 제거 정규화."""
    return text.replace(" ", "")


def _last_user_text(state: VoiceState) -> str:
    """messages에서 가장 최신 HumanMessage 텍스트를 반환한다."""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _is_cancel_utterance(text: str) -> bool:
    """취소 키워드 포함 여부."""
    return any(kw in _normalize(text) for kw in CANCEL_KEYWORDS)


def _is_navigation_utterance(text: str) -> bool:
    """화면 이동(홈) 키워드 포함 여부."""
    return any(kw in _normalize(text) for kw in NAVIGATION_KEYWORDS)


def _has_active_session(state: VoiceState) -> bool:
    """TransferAgent 진행 중 세션 여부."""
    return bool(
        state.get("pending_action")
        or state.get("awaiting_confirmation")
        or state.get("awaiting_asv_audio")
        or state.get("awaiting_memo_decision")
        or state.get("awaiting_transfer_clarification")
        or state.get("execution_ready")
    )


def _is_domain_switch_utterance(text: str) -> bool:
    """AssetAgent 연속 세션 중 도메인 전환 신호 발화인지 판별."""
    return (
        is_plain_transfer_start(text)
        or _is_cancel_utterance(text)
        or _is_navigation_utterance(text)
    )


async def _llm_classify_domain(text: str) -> str:
    """gpt-4o-mini로 도메인 분류. 실패하거나 예상 외 값이면 'unknown' 반환."""
    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            temperature=0,
        )
        prompt = DOMAIN_CLASSIFY_PROMPT.format(text=text)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        domain = response.content.strip().lower()
        if domain not in _VALID_DOMAINS:
            logger.warning("LLM 분류 결과 비정상: %r → unknown 처리", domain)
            return "unknown"
        return domain
    except Exception:
        logger.exception("LLM 도메인 분류 실패 → unknown 폴백")
        return "unknown"


async def _decide_domain(text: str, state: VoiceState) -> str:
    """우선순위 기반 도메인 결정.

    Args:
        text: 사용자 발화 텍스트.
        state: 현재 VoiceState.

    Returns:
        "transfer" | "asset" | "rag" | "cancel" | "unknown"
        홈 이동 키워드는 활성 세션 유무와 무관하게 cancel로 처리하거나 (세션 있음),
        LLM 분류로 넘어간다 (세션 없음).
    """
    active_session = _has_active_session(state)

    # 1. 홈 이동 키워드 → 세션 유무와 무관하게 항상 cancel
    #    이벤트·RAG 화면처럼 active_session=False 상태에서도 홈 이동이 가능해야 한다.
    if _is_navigation_utterance(text):
        return "cancel"

    # 1-b. 취소 키워드 + 활성 세션 → cancel (진행 중인 작업 포기)
    if _is_cancel_utterance(text) and active_session:
        return "cancel"

    # 2. 활성 세션 → transfer 유지 (pending_action / awaiting_* / execution_ready 포함)
    if active_session:
        return "transfer"

    # 3. asset 연속 발화 — 도메인 전환 신호 없으면 asset 세션 유지
    if state.get("agent_domain") == "asset" and not _is_domain_switch_utterance(text):
        return "asset"

    # 4. 이체 키워드 패스트패스 — 명시적 이체 키워드가 있으면 즉시 "transfer"
    #    슬롯(금액·수취인) 유무와 무관하게 라우팅한다.
    #    슬롯 추출은 subgraph(intent_node)의 책임이므로 supervisor는 도메인만 결정한다.
    if is_plain_transfer_start(text):
        return "transfer"

    # 5. 이벤트 fast-path — PostgreSQL 조회 전용 event 노드로 라우팅
    #    이벤트는 OpenSearch가 아닌 DB에서 조회하므로 rag와 별도 처리
    _EVENT_KEYWORDS = ("이벤트",)
    if any(kw in _normalize(text) for kw in _EVENT_KEYWORDS):
        return "event"

    # ── 계획: asset fast-path (Phase 2 이후) ──────────────────────────────────
    # asset: 잔액·잔고·내역 키워드 → LLM 없이 즉시 "asset"
    #   예) kws = ("잔액", "잔고", "내역", "출금")
    #       if any(kw in _normalize(text) for kw in kws): return "asset"
    # ─────────────────────────────────────────────────────────────────────────

    # 6. gpt-4o-mini LLM 분류 (폴백: "unknown")
    return await _llm_classify_domain(text)


# ── 노드 함수 ─────────────────────────────────────────────────────────────────────


async def supervisor_node(state: VoiceState) -> dict:
    """Supervisor 진입 노드 — 도메인 분류 후 라우팅 또는 인라인 처리.

    unknown은 등록된 서브그래프 노드가 없으므로 이 노드에서 직접 처리한다.
    - unknown : 재질문 TTS 반환 → END (navigate 도메인은 존재하지 않음)
    - cancel  : agent_domain 기록 → cancel_node로 라우팅
    - transfer/asset/rag: agent_domain 기록 → 서브그래프로 라우팅 (Phase 2)
    """
    text = _last_user_text(state)
    domain = await _decide_domain(text, state)
    logger.info("supervisor_node: domain=%s, text=%r", domain, text)

    # unknown: 다시 질문 TTS (서브그래프 없이 인라인 처리)
    if domain == "unknown":
        return {
            "agent_domain": None,
            "messages": [
                AIMessage(content="이해하지 못했습니다. 다시 한번 말씀해 주세요.")
            ],
        }

    # cancel / transfer / asset / rag → route_after_supervisor로 라우팅
    return {"agent_domain": domain}


async def event_node(state: VoiceState) -> dict:
    """이벤트 목록 조회 + 이벤트 화면 이동.

    graph.py execute_node(event) 처리를 Supervisor 레벨 노드로 구현.
    get_event_list는 PostgreSQL에서 조회하므로 rag 에이전트와 분리된다.
    """
    from app.shared.agent.tools.event import get_event_list

    user_id = state.get("user_id", "")
    try:
        response_text = get_event_list.invoke({"user_id": user_id})
    except Exception as e:
        logger.exception("event_node: get_event_list 호출 실패")
        raise EventError(
            code="EVENT_FETCH_ERROR",
            message="이벤트 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
            status_code=500,
            user_message="이벤트 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
        ) from e

    return {
        "messages": [AIMessage(content=response_text)],
        "navigate_to": "event",
    }


async def cancel_node(state: VoiceState) -> dict:
    """세션 전체 초기화 + 홈 이동 TTS 반환.

    P4 예외: 취소 발화 시 서브그래프를 거치지 않고 Supervisor에서 즉시 세션을 정리한다.
    TransferAgent 소유 필드를 직접 초기화하는 유일한 Supervisor 노드.
    활성 세션이 없으면 "홈 화면으로 이동합니다."만 읽어 준다.
    """
    has_session = _has_active_session(state)
    tts = (
        "취소했습니다. 홈 화면으로 이동합니다."
        if has_session
        else "홈 화면으로 이동합니다."
    )
    return {
        "messages": [
            *clear_conversation_messages(),
            AIMessage(content=tts),
        ],
        "navigate_to": "home",
        "pending_action": None,
        "collected_slots": {},
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "execution_ready": False,
        "recipient_validated": False,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "asv_retry_count": 0,
        "last_tx_id": None,
        "last_order_id": None,
        "agent_domain": None,
        "analytics_period": None,
    }


# ── 라우팅 함수 ──────────────────────────────────────────────────────────────────


def route_after_supervisor(state: VoiceState) -> str:
    """supervisor_node 이후 조건부 엣지 함수."""
    domain = state.get("agent_domain")
    if domain == "cancel":
        return "cancel_node"
    if domain == "transfer":
        return "transfer"
    if domain == "asset":
        return "asset"
    if domain == "rag":
        return "rag"
    if domain == "event":
        return "event_node"
    return END


# ── 그래프 빌드 ──────────────────────────────────────────────────────────────────


def build_supervisor():
    """Supervisor StateGraph를 빌드하고 MemorySaver로 컴파일해 반환한다.

    MemorySaver는 이 레벨에만 설정한다. 서브그래프는 checkpointer 없이
    builder.compile()만 호출해야 세션 상태가 분리되지 않는다.
    """
    from app.shared.agent.subgraphs.transfer import build_transfer_graph
    from app.shared.agent.subgraphs.consultation import build_rag_graph
    from app.shared.agent.subgraphs.asset import build_asset_graph
    from app.shared.agent.tools import TRANSFER_TOOLS, RAG_TOOLS, ASSET_TOOLS

    transfer_graph = build_transfer_graph(TRANSFER_TOOLS)
    rag_graph = build_rag_graph(RAG_TOOLS)
    asset_graph = build_asset_graph(ASSET_TOOLS)

    builder = StateGraph(VoiceState)
    builder.add_node("supervisor_node", supervisor_node)
    builder.add_node("cancel_node", cancel_node)
    builder.add_node("event_node", event_node)
    builder.add_node("transfer", transfer_graph)
    builder.add_node("asset", asset_graph)
    builder.add_node("rag", rag_graph)

    builder.set_entry_point("supervisor_node")
    builder.add_conditional_edges("supervisor_node", route_after_supervisor)
    builder.add_edge("cancel_node", END)
    builder.add_edge("event_node", END)
    builder.add_edge("transfer", END)
    builder.add_edge("asset", END)
    builder.add_edge("rag", END)

    return builder.compile(checkpointer=MemorySaver())
