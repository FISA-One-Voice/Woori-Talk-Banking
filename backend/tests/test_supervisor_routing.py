"""Supervisor 도메인 결정 단위 테스트 — _decide_domain 6개 + build_supervisor 3개.

Design Ref: docs/02-design/features/dev-a-supervisor-plan.design.md §4.6

실행 방법:
    cd backend
    .venv/bin/pytest tests/test_supervisor_routing.py -v

주의:
    LLM 실제 호출이 필요한 케이스(세션 없는 취소)는 _llm_classify_domain을 mock한다.
    나머지 5개는 fast-path 로직만 검증하므로 OpenAI API 키 불필요.
"""

from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage

from app.shared.agent.supervisor import _decide_domain, build_supervisor


# ── build_supervisor() 빌드 검증 ──────────────────────────────────────────────


def test_build_supervisor_returns_compiled_graph() -> None:
    """build_supervisor()가 오류 없이 CompiledStateGraph를 반환한다."""
    graph = build_supervisor()
    assert graph is not None
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


def test_build_supervisor_has_transfer_subgraph_node() -> None:
    """Supervisor 그래프에 TransferAgent 서브그래프 노드('transfer')가 등록되어 있다."""
    graph = build_supervisor()
    assert "transfer" in graph.nodes


def test_build_supervisor_has_required_nodes() -> None:
    """Supervisor 그래프 노드 구성: supervisor_node, cancel_node, transfer 포함."""
    graph = build_supervisor()
    nodes = set(graph.nodes)
    assert {"supervisor_node", "cancel_node", "transfer"}.issubset(nodes)


def _make_state(**kwargs) -> dict:
    """테스트용 최소 VoiceState 딕셔너리."""
    base = {
        "messages": [],
        "user_id": "test-user",
        "pending_action": None,
        "collected_slots": {},
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "asv_retry_count": 0,
        "navigate_to": None,
        "execution_ready": False,
        "recipient_validated": False,
        "last_tx_id": None,
        "last_order_id": None,
        "agent_domain": None,
        "analytics_period": None,
    }
    base.update(kwargs)
    return base


async def test_cancel_during_transfer():
    """이체 진행 중 '취소해줘' → 'cancel' (우선순위 1: 취소 키워드 + 활성 세션)."""
    state = _make_state(pending_action="transfer")
    result = await _decide_domain("취소해줘", state)
    assert result == "cancel"


async def test_cancel_without_session():
    """세션 없을 때 '취소' 단독 발화 → 'cancel' 이 아님 (세션 없으면 도메인 전환 불필요).

    우선순위 1 조건(활성 세션 없음)에 해당하지 않아 LLM으로 넘어간다.
    LLM은 mock으로 'unknown'을 반환하며, 결과가 'cancel'이 아님을 검증한다.
    """
    state = _make_state()
    with patch(
        "app.shared.agent.supervisor._llm_classify_domain",
        new=AsyncMock(return_value="unknown"),
    ):
        result = await _decide_domain("취소", state)
    assert result != "cancel"


async def test_fastpath_active_transfer():
    """'엄마' 발화 + pending_action=transfer → 세션 유지 'transfer' (우선순위 3)."""
    state = _make_state(pending_action="transfer")
    result = await _decide_domain("엄마", state)
    assert result == "transfer"


async def test_fastpath_asv():
    """awaiting_asv_audio=True → 'transfer' (ASV 대기 세션 유지, 우선순위 3)."""
    state = _make_state(awaiting_asv_audio=True)
    result = await _decide_domain("(음성)", state)
    assert result == "transfer"


async def test_fastpath_execution_ready():
    """execution_ready=True → 'transfer' (실행 준비 상태 유지, 우선순위 3)."""
    state = _make_state(execution_ready=True)
    result = await _decide_domain("인증 완료", state)
    assert result == "transfer"


async def test_navigate_keyword_with_active_session():
    """이체 진행 중 '홈으로 가줘' → 'cancel' (홈 이동 키워드 + 활성 세션 = 세션 포기)."""
    state = _make_state(pending_action="transfer")
    result = await _decide_domain("홈으로 가줘", state)
    assert result == "cancel"
