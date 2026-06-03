"""bare 송금 발화 — 좁은 fast path 단위·그래프 테스트."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.shared.agent.graph import IntentResult, build_graph
from app.shared.agent.slot_schema import SLOT_QUESTIONS
from app.shared.agent.tools import MOCK_TOOLS
from app.shared.agent.transfer_intent import (
    build_bare_transfer_start_update,
    should_use_bare_transfer_fast_start,
)


class TestBareTransferFastStartDetection:
    def test_bare_utterances_use_fast_path(self):
        assert should_use_bare_transfer_fast_start("송금하고 싶어")
        assert should_use_bare_transfer_fast_start("이체 하고 싶어")
        assert should_use_bare_transfer_fast_start("이체해줘")
        assert should_use_bare_transfer_fast_start("돈 보내고 싶어")

    def test_compound_utterances_skip_fast_path(self):
        assert not should_use_bare_transfer_fast_start("이도원한테 4500원 보내고 싶어")
        assert not should_use_bare_transfer_fast_start("이도헌에게 4천원을 보내고싶어")
        assert not should_use_bare_transfer_fast_start("010 1111 0003으로 돈 보내고 싶어")

    def test_auto_transfer_not_bare(self):
        assert not should_use_bare_transfer_fast_start("자동이체 등록")

    def test_build_start_sets_transfer_pending(self):
        update = build_bare_transfer_start_update("송금하고 싶어")
        assert update["pending_action"] == "transfer"
        assert update["navigate_to"] == "transfer"
        assert update["collected_slots"] == {}


class TestBareTransferFastStartGraph:
    @pytest.fixture(scope="class")
    def graph_with_mocks(self):
        return build_graph(MOCK_TOOLS)

    def test_bare_start_without_llm(self, graph_with_mocks):
        """bare 발화는 LLM 없이 transfer + 수취인 질문."""
        tid = f"test-bare-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": tid}}
        uid = "u-bare-fast"

        with patch("langchain_openai.ChatOpenAI.with_structured_output") as mock_struct:
            mock_llm = MagicMock()
            mock_struct.return_value = mock_llm

            result = graph_with_mocks.invoke(
                {
                    "messages": [HumanMessage(content="송금하고 싶어")],
                    "user_id": uid,
                },
                config=config,
            )

            mock_llm.invoke.assert_not_called()

        assert result.get("pending_action") == "transfer"
        assert result.get("navigate_to") == "transfer"
        ai_msgs = [m.content for m in result["messages"] if isinstance(m, AIMessage)]
        assert any(SLOT_QUESTIONS["recipient"] in msg for msg in ai_msgs)
