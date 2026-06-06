"""TransferAgent 서브그래프 계약 테스트."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from app.core.exception import AgentError
from app.shared.agent.graph import build_graph
from app.shared.agent.subgraphs.transfer import (
    IntentResult,
    TRANSFER_DOMAIN_ACTIONS,
    build_transfer_graph,
    validate_transfer_delta,
)
from app.shared.agent.tools import MOCK_TOOLS, TRANSFER_MOCK_TOOLS


def _thread_config() -> dict:
    """테스트마다 독립 LangGraph thread_id를 만든다."""
    return {"configurable": {"thread_id": f"transfer-{uuid.uuid4().hex[:8]}"}}


def _minimal_transfer_state(text: str) -> dict:
    """TRANSFER_READ 기준 최소 실행 state를 만든다."""
    return {
        "messages": [HumanMessage(content=text)],
        "user_id": "test-user",
        "pending_action": None,
        "collected_slots": {},
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "execution_ready": False,
        "recipient_validated": False,
        "asv_retry_count": 0,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "last_tx_id": None,
        "last_order_id": None,
    }


def test_transfer_domain_actions_are_local_contract() -> None:
    """TransferAgent 담당 action 집합을 검증한다."""
    assert TRANSFER_DOMAIN_ACTIONS == {
        "transfer",
        "auto_transfer",
        "cancel_auto_transfer",
        "add_note",
        "add_auto_transfer_note",
    }


def test_validate_transfer_delta_rejects_forbidden_fields() -> None:
    """TransferAgent는 Dev-A/Dev-C 소유 필드를 반환할 수 없다."""
    with pytest.raises(AgentError):
        validate_transfer_delta({"agent_domain": "transfer"})
    with pytest.raises(AgentError):
        validate_transfer_delta({"analytics_period": "이번달"})
    with pytest.raises(AgentError):
        validate_transfer_delta({"user_id": "test-user"})


def test_validate_transfer_delta_rejects_invalid_navigate_to() -> None:
    """navigate_to는 TRANSFER_NAVIGATE_VALUES 안의 값만 허용한다."""
    with pytest.raises(AgentError):
        validate_transfer_delta({"navigate_to": "transfer/failed"})


def test_build_transfer_graph_has_no_own_checkpointer() -> None:
    """TransferAgent 서브그래프는 부모 checkpointer를 공유한다."""
    graph = build_transfer_graph(TRANSFER_MOCK_TOOLS)
    assert getattr(graph, "checkpointer", None) is None


def test_existing_build_graph_public_api_is_preserved() -> None:
    """기존 voice pipeline이 의존하는 build_graph(tools)를 유지한다."""
    graph = build_graph(MOCK_TOOLS)
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


def test_transfer_intent_sets_pending_action_and_navigate_to() -> None:
    """Transfer LLM 결과가 transfer 상태와 화면 이동을 만든다."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = IntentResult(
        intent="transfer",
        extracted_slots={},
    )
    with patch(
        "langchain_openai.ChatOpenAI.with_structured_output",
        return_value=mock_llm,
    ):
        graph = build_transfer_graph(TRANSFER_MOCK_TOOLS)
        result = graph.invoke(
            _minimal_transfer_state("엄마한테 이체해줘"),
            config=_thread_config(),
        )

    assert result["pending_action"] == "transfer"
    assert result["navigate_to"] == "transfer"


def test_awaiting_asv_audio_ends_without_llm_call() -> None:
    """ASV 대기 중에는 LLM 호출과 실행을 하지 않는다."""
    mock_llm = MagicMock()
    with patch(
        "langchain_openai.ChatOpenAI.with_structured_output",
        return_value=mock_llm,
    ):
        graph = build_transfer_graph(TRANSFER_MOCK_TOOLS)
        state = _minimal_transfer_state("인증용 음성")
        state.update({
            "pending_action": "transfer",
            "awaiting_asv_audio": True,
            "collected_slots": {"recipient": "엄마", "amount": 50000},
        })
        result = graph.invoke(state, config=_thread_config())

    mock_llm.invoke.assert_not_called()
    assert result["awaiting_asv_audio"] is True
    assert result["pending_action"] == "transfer"
    assert result["navigate_to"] is None


def test_execution_ready_routes_to_execute_without_llm_call() -> None:
    """ASV 성공 후 execution_ready=True이면 execute_node로 직행한다."""
    mock_llm = MagicMock()
    with patch(
        "langchain_openai.ChatOpenAI.with_structured_output",
        return_value=mock_llm,
    ):
        graph = build_transfer_graph(TRANSFER_MOCK_TOOLS)
        state = _minimal_transfer_state("인증 완료")
        state.update({
            "pending_action": "transfer",
            "execution_ready": True,
            "recipient_validated": True,
            "collected_slots": {"recipient": "엄마", "amount": 50000},
        })
        result = graph.invoke(state, config=_thread_config())

    mock_llm.invoke.assert_not_called()
    assert result["pending_action"] is None
    assert result["execution_ready"] is False
    assert result["navigate_to"] == "transfer/complete"
