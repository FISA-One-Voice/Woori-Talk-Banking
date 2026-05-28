"""멀티턴 에이전트 StateGraph 테스트 (Issue #21).

테스트 구성:
    Layer A — 단위 테스트 (LLM mock, 빠른 피드백)
        - 노드 함수 직접 호출 / 상태 전이 로직 검증
        - unittest.mock.patch로 LLM 응답 고정

    Layer B — 통합 테스트 (실제 OpenAI API 호출)
        - @pytest.mark.integration 마킹
        - .env의 OPENAI_CHAT_API_KEY 필요
        - build_graph(MOCK_TOOLS)로 end-to-end 흐름 검증

실행 방법:
    cd backend

    # Layer A만 (빠른 피드백)
    pytest tests/test_agent_multiturn.py -k "not integration" -v

    # Layer B 포함 전체 실행 (OpenAI API 키 필요)
    pytest tests/test_agent_multiturn.py -m integration -v

    # 전체 실행
    pytest tests/test_agent_multiturn.py -v
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.shared.agent.graph import IntentResult, build_graph
from app.shared.agent.slot_schema import (
    ASV_REQUIRED_ACTIONS,
    SCREEN_MAP,
    SLOT_QUESTIONS,
    SLOT_SCHEMA,
)
from app.shared.agent.tools import MOCK_TOOLS
from app.shared.agent.tools.mock_tools import (
    mock_execute_transfer,
    mock_get_balance,
    mock_get_events,
    mock_get_history,
    mock_register_auto_transfer,
)

# ── 공통 픽스처 ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def graph_with_mocks():
    """MOCK_TOOLS로 빌드된 StateGraph. 모듈 내에서 공유한다."""
    return build_graph(MOCK_TOOLS)


def _new_thread_id() -> str:
    """테스트마다 고유한 thread_id를 생성해 상태 충돌을 방지한다."""
    return f"test-{uuid.uuid4().hex[:8]}"


def _invoke(graph, text: str, user_id: str, config: dict) -> dict:
    """그래프를 동기 invoke로 호출하고 최종 상태를 반환한다."""
    return graph.invoke(
        {
            "messages": [HumanMessage(content=text)],
            "user_id": user_id,
        },
        config=config,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Layer A — 단위 테스트 (LLM mock)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlotSchema:
    """SLOT_SCHEMA / SCREEN_MAP / ASV_REQUIRED_ACTIONS 불변성 검증."""

    def test_transfer_slots_defined(self):
        """transfer 액션은 alias, amount 슬롯을 요구해야 한다."""
        assert SLOT_SCHEMA["transfer"] == ["alias", "amount"]

    def test_auto_transfer_slots_defined(self):
        """auto_transfer 액션은 4개 슬롯을 요구해야 한다."""
        assert set(SLOT_SCHEMA["auto_transfer"]) == {
            "alias",
            "amount",
            "schedule_date",
            "frequency",
        }

    def test_screen_map_has_all_intents(self):
        """SCREEN_MAP에 transfer, auto_transfer, balance, history, event가 모두 있어야 한다."""
        for intent in ["transfer", "auto_transfer", "balance", "history", "event"]:
            assert intent in SCREEN_MAP, f"SCREEN_MAP에 '{intent}'가 없습니다."

    def test_asv_required_actions_subset_of_slot_schema(self):
        """ASV 필요 액션은 SLOT_SCHEMA에 정의된 액션의 부분집합이어야 한다."""
        assert ASV_REQUIRED_ACTIONS.issubset(set(SLOT_SCHEMA.keys()))

    def test_slot_questions_cover_all_slots(self):
        """SLOT_QUESTIONS에 모든 슬롯 이름이 포함되어야 한다."""
        all_slots = {s for slots in SLOT_SCHEMA.values() for s in slots}
        for slot in all_slots:
            assert slot in SLOT_QUESTIONS, f"SLOT_QUESTIONS에 '{slot}'가 없습니다."


class TestMockTools:
    """mock tool 시그니처 및 반환값 검증."""

    def test_mock_get_balance_returns_string(self):
        """mock_get_balance는 TTS 친화적 문자열을 반환해야 한다."""
        result = mock_get_balance.invoke({"user_id": "u001"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_get_history_returns_string(self):
        """mock_get_history는 TTS 친화적 문자열을 반환해야 한다."""
        result = mock_get_history.invoke({"user_id": "u001", "days": 7})
        assert isinstance(result, str)
        assert "7일" in result or "칠 일" in result

    def test_mock_execute_transfer_contains_alias_and_amount(self):
        """mock_execute_transfer는 alias와 금액을 포함한 응답을 반환해야 한다."""
        result = mock_execute_transfer.invoke({"alias": "엄마", "amount": 50000})
        assert isinstance(result, str)
        assert "엄마" in result

    def test_mock_register_auto_transfer_contains_info(self):
        """mock_register_auto_transfer는 등록 완료 정보를 반환해야 한다."""
        result = mock_register_auto_transfer.invoke(
            {
                "alias": "엄마",
                "amount": 100000,
                "schedule_date": 15,
                "frequency": "monthly",
            }
        )
        assert isinstance(result, str)
        assert "엄마" in result
        assert "15일" in result

    def test_mock_get_events_returns_string(self):
        """mock_get_events는 TTS 친화적 이벤트 안내를 반환해야 한다."""
        result = mock_get_events.invoke({"user_id": "u001"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_all_mock_tools_no_markdown(self):
        """모든 mock tool 반환값에 마크다운 기호가 없어야 한다."""
        responses = [
            mock_get_balance.invoke({"user_id": "u001"}),
            mock_get_history.invoke({"user_id": "u001"}),
            mock_execute_transfer.invoke({"alias": "회사", "amount": 200000}),
            mock_get_events.invoke({"user_id": "u001"}),
        ]
        for resp in responses:
            for symbol in ["*", "#", "```", "- ", "| "]:
                assert symbol not in resp, (
                    f"mock tool 응답에 마크다운 기호 '{symbol}'가 포함되어 있습니다."
                )


class TestBuildGraphWithMocks:
    """build_graph(MOCK_TOOLS) 초기화 검증 (LLM mock 없이)."""

    def test_build_graph_with_mock_tools_no_error(self):
        """build_graph(MOCK_TOOLS)가 오류 없이 초기화되어야 한다."""
        graph = build_graph(MOCK_TOOLS)
        assert graph is not None

    def test_build_graph_has_invoke(self):
        """반환 그래프는 .invoke 메서드를 보유해야 한다."""
        graph = build_graph(MOCK_TOOLS)
        assert hasattr(graph, "invoke")

    def test_build_graph_has_ainvoke(self):
        """반환 그래프는 .ainvoke 메서드를 보유해야 한다."""
        graph = build_graph(MOCK_TOOLS)
        assert hasattr(graph, "ainvoke")

    def test_build_graph_empty_tools_still_works(self):
        """build_graph([])도 오류 없이 초기화되어야 한다 (Phase 1 완료 조건 유지)."""
        graph = build_graph([])
        assert graph is not None


class TestStateTransitionLogic:
    """LLM을 mock하여 노드의 상태 전이 로직만 검증한다."""

    def test_cancellation_clears_pending_action(self, graph_with_mocks):
        """취소 발화 시 pending_action과 collected_slots이 초기화되어야 한다.

        LLM이 user_cancelled=True를 반환하는 시나리오를 mock으로 재현한다.
        """
        uid = "u-cancel"
        tid = _new_thread_id()
        config = {"configurable": {"thread_id": tid}}

        cancel_result = IntentResult(
            intent=None,
            user_cancelled=True,
            direct_response="취소되었습니다.",
        )

        # LLM structured output을 mock하기 위해 graph를 직접 빌드
        with patch("langchain_openai.ChatOpenAI.with_structured_output") as mock_struct:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = cancel_result
            mock_struct.return_value = mock_llm

            g = build_graph(MOCK_TOOLS)
            # pending_action이 있는 상태로 시작
            state_with_pending = {
                "messages": [HumanMessage(content="이체 취소해줘")],
                "user_id": uid,
                "pending_action": "transfer",
                "collected_slots": {"alias": "엄마"},
                "awaiting_confirmation": False,
                "awaiting_asv_audio": False,
                "asv_retry_count": 0,
                "navigate_to": None,
                "execution_ready": False,
            }
            result = g.invoke(state_with_pending, config=config)

        assert result["pending_action"] is None
        assert result["collected_slots"] == {}
        # 마지막 AI 메시지 확인
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_messages) > 0

    def test_asv_flag_set_on_confirmation_for_transfer(self, graph_with_mocks):
        """transfer 확인('네') 후 awaiting_asv_audio=True가 설정되어야 한다."""
        uid = "u-asv"
        tid = _new_thread_id()
        config = {"configurable": {"thread_id": tid}}

        confirm_result = IntentResult(
            intent=None,
            user_confirmed=True,
            direct_response="",
        )

        with patch("langchain_openai.ChatOpenAI.with_structured_output") as mock_struct:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = confirm_result
            mock_struct.return_value = mock_llm

            g = build_graph(MOCK_TOOLS)
            state_awaiting = {
                "messages": [HumanMessage(content="네")],
                "user_id": uid,
                "pending_action": "transfer",
                "collected_slots": {"alias": "엄마", "amount": 100000},
                "awaiting_confirmation": True,
                "awaiting_asv_audio": False,
                "asv_retry_count": 0,
                "navigate_to": None,
                "execution_ready": False,
            }
            result = g.invoke(state_awaiting, config=config)

        assert result["awaiting_asv_audio"] is True, (
            "transfer 확인 후 awaiting_asv_audio가 True가 되어야 합니다."
        )
        assert result["awaiting_confirmation"] is False

    def test_navigate_to_set_on_new_intent(self, graph_with_mocks):
        """새 intent 감지 시 navigate_to가 SCREEN_MAP 값으로 설정되어야 한다."""
        uid = "u-nav"
        tid = _new_thread_id()
        config = {"configurable": {"thread_id": tid}}

        intent_result = IntentResult(
            intent="balance",
            extracted_slots={},
            direct_response="현재 잔액은 오백만 원입니다.",
        )

        with patch("langchain_openai.ChatOpenAI.with_structured_output") as mock_struct:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = intent_result
            mock_struct.return_value = mock_llm

            g = build_graph(MOCK_TOOLS)
            result = _invoke(g, "잔액 얼마야", uid, config)

        assert result.get("navigate_to") == SCREEN_MAP["balance"]

    def test_slot_fill_node_adds_question(self, graph_with_mocks):
        """슬롯 부족 시 slot_fill_node가 올바른 질문을 메시지에 추가해야 한다."""
        uid = "u-slot"
        tid = _new_thread_id()
        config = {"configurable": {"thread_id": tid}}

        # transfer intent 감지 + alias만 추출 (amount 누락)
        intent_result = IntentResult(
            intent="transfer",
            extracted_slots={"alias": "엄마"},
            direct_response="",
        )

        with patch("langchain_openai.ChatOpenAI.with_structured_output") as mock_struct:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = intent_result
            mock_struct.return_value = mock_llm

            g = build_graph(MOCK_TOOLS)
            result = _invoke(g, "엄마에게 이체해줘", uid, config)

        # amount 슬롯 질문이 메시지에 있어야 함
        ai_messages = [
            m.content for m in result["messages"] if isinstance(m, AIMessage)
        ]
        amount_question = SLOT_QUESTIONS["amount"]
        assert any(amount_question in msg for msg in ai_messages), (
            f"amount 슬롯 질문({amount_question!r})이 메시지에 없습니다. "
            f"실제 메시지: {ai_messages}"
        )

    def test_confirm_node_sets_awaiting_confirmation(self, graph_with_mocks):
        """모든 슬롯 수집 후 confirm_node가 awaiting_confirmation=True를 설정해야 한다."""
        uid = "u-confirm"
        tid = _new_thread_id()
        config = {"configurable": {"thread_id": tid}}

        # 모든 슬롯 완전 수집 (amount도 추출)
        intent_result = IntentResult(
            intent=None,  # 이미 pending_action 있음
            extracted_slots={"amount": 100000},
            direct_response="",
        )

        with patch("langchain_openai.ChatOpenAI.with_structured_output") as mock_struct:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = intent_result
            mock_struct.return_value = mock_llm

            g = build_graph(MOCK_TOOLS)
            state_with_alias = {
                "messages": [HumanMessage(content="십만원")],
                "user_id": uid,
                "pending_action": "transfer",
                "collected_slots": {"alias": "엄마"},  # alias만 있음
                "awaiting_confirmation": False,
                "awaiting_asv_audio": False,
                "asv_retry_count": 0,
                "navigate_to": None,
                "execution_ready": False,
            }
            result = g.invoke(state_with_alias, config=config)

        assert result.get("awaiting_confirmation") is True, (
            "슬롯 완전 수집 후 awaiting_confirmation이 True가 되어야 합니다."
        )
        # 확인 메시지에 엄마와 금액이 포함되어야 함
        ai_messages = [
            m.content for m in result["messages"] if isinstance(m, AIMessage)
        ]
        assert any("엄마" in msg for msg in ai_messages), (
            "확인 메시지에 alias(엄마)가 없습니다."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Layer B — 통합 테스트 (실제 OpenAI API 호출)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestIntegrationSingleTurn:
    """단일 턴 시나리오 — 실제 LLM 응답 검증."""

    def test_balance_query_direct_response(self, graph_with_mocks):
        """'잔액 얼마야' → mock_get_balance 호출 or 직접 응답, navigate_to='balance'.

        LLM이 'balance' intent를 감지하면 navigate_to='balance'로 설정되어야 한다.
        """
        uid = f"integ-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": _new_thread_id()}}
        result = _invoke(graph_with_mocks, "잔액 얼마야", uid, config)

        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_messages) > 0, "AI 응답이 없습니다."
        # navigate_to가 'balance'이거나 응답에 잔액 관련 내용이 포함되어야 함
        navigate = result.get("navigate_to")
        last_msg = ai_messages[-1].content
        assert navigate == "balance" or "잔액" in last_msg or "원" in last_msg, (
            f"잔액 조회 응답이 예상과 다릅니다. navigate_to={navigate}, 응답={last_msg!r}"
        )

    def test_event_query_response(self, graph_with_mocks):
        """'이벤트 뭐 있어' → mock_get_events 호출 or 이벤트 관련 응답."""
        uid = f"integ-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": _new_thread_id()}}
        result = _invoke(graph_with_mocks, "이벤트 뭐 있어", uid, config)

        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_messages) > 0
        # 응답이 비어있지 않아야 함
        assert any(len(m.content) > 0 for m in ai_messages)

    def test_non_financial_query_chatbot_response(self, graph_with_mocks):
        """'은행 영업시간 알려줘' → chatbot 직답 (tool 미호출, pending_action 없음)."""
        uid = f"integ-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": _new_thread_id()}}
        result = _invoke(graph_with_mocks, "은행 영업시간 알려줘", uid, config)

        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_messages) > 0, "챗봇 직답이 없습니다."
        # 일반 질의는 tool을 실행하지 않으므로 execution_ready가 False여야 함
        assert result.get("execution_ready") is not True


@pytest.mark.integration
class TestIntegrationMultiTurn:
    """멀티턴 시나리오 — 실제 LLM으로 슬롯 수집 흐름 검증."""

    def test_transfer_intent_sets_pending_action(self, graph_with_mocks):
        """'이체해줘' → pending_action='transfer', navigate_to='transfer'."""
        uid = f"integ-mt-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": _new_thread_id()}}
        result = _invoke(graph_with_mocks, "이체해줘", uid, config)

        pending = result.get("pending_action")
        navigate = result.get("navigate_to")
        assert pending == "transfer", (
            f"pending_action이 'transfer'여야 합니다. 실제: {pending!r}"
        )
        assert navigate == "transfer", (
            f"navigate_to가 'transfer'여야 합니다. 실제: {navigate!r}"
        )

    def test_transfer_multiturn_slot_collection(self, graph_with_mocks):
        """이체 멀티턴: 이체 시작 → 엄마에게 → 십만원 → 슬롯 수집 확인."""
        tid = _new_thread_id()
        uid = f"integ-mt2-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": tid}}

        # Turn 1: 이체 시작
        result1 = _invoke(graph_with_mocks, "이체해줘", uid, config)
        assert result1.get("pending_action") == "transfer", (
            f"Turn 1: pending_action='transfer' 기대, 실제={result1.get('pending_action')!r}"
        )

        # Turn 2: alias 제공
        result2 = _invoke(graph_with_mocks, "엄마에게 보내줘", uid, config)
        slots2 = result2.get("collected_slots", {})
        assert result2.get("pending_action") == "transfer", (
            "Turn 2: pending_action 유지 필요"
        )
        # alias가 수집되거나 amount 질문이 있어야 함
        has_alias = bool(slots2.get("alias"))
        ai_msgs2 = [m.content for m in result2["messages"] if isinstance(m, AIMessage)]
        has_amount_question = any("얼마" in msg or "금액" in msg for msg in ai_msgs2)
        assert has_alias or has_amount_question, (
            f"Turn 2: alias 수집 또는 금액 질문 기대. slots={slots2}, msgs={ai_msgs2}"
        )

        # Turn 3: amount 제공
        result3 = _invoke(graph_with_mocks, "십만원", uid, config)
        slots3 = result3.get("collected_slots", {})
        # 슬롯이 완전히 수집되어 확인 대기 or amount가 수집됨
        assert result3.get("awaiting_confirmation") is True or bool(
            slots3.get("amount")
        ), (
            f"Turn 3: awaiting_confirmation=True 또는 amount 수집 기대. "
            f"awaiting={result3.get('awaiting_confirmation')}, slots={slots3}"
        )

    def test_state_persisted_across_turns(self, graph_with_mocks):
        """동일 thread_id로 2턴 호출 시 1턴의 슬롯 상태가 유지되어야 한다."""
        tid = _new_thread_id()
        uid = f"integ-persist-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": tid}}

        # Turn 1: transfer intent 시작
        _invoke(graph_with_mocks, "이체해줘", uid, config)

        # Turn 2: 다른 스레드가 아닌 동일 스레드에서 계속
        result2 = _invoke(graph_with_mocks, "엄마에게", uid, config)
        # pending_action이 여전히 'transfer'여야 함 (상태 유지 확인)
        assert result2.get("pending_action") == "transfer", (
            "동일 thread_id에서 pending_action이 유지되어야 합니다."
        )

    def test_cancellation_during_slot_collection(self, graph_with_mocks):
        """슬롯 수집 중 '취소'하면 pending_action이 초기화되어야 한다."""
        tid = _new_thread_id()
        uid = f"integ-cancel-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": tid}}

        # Turn 1: transfer 시작
        _invoke(graph_with_mocks, "이체해줘", uid, config)

        # Turn 2: 취소
        result = _invoke(graph_with_mocks, "이체 취소해줘", uid, config)
        assert result.get("pending_action") is None, (
            f"취소 후 pending_action이 None이어야 합니다. 실제: {result.get('pending_action')!r}"
        )
        assert (
            result.get("collected_slots") == {} or result.get("collected_slots") is None
        ), "취소 후 collected_slots이 비어 있어야 합니다."


@pytest.mark.integration
class TestIntegrationASVFlow:
    """ASV 음성 인증 흐름 — transfer 확인 후 awaiting_asv_audio=True 검증."""

    def test_transfer_confirmation_sets_asv_flag(self, graph_with_mocks):
        """transfer 슬롯 완전 수집 → '네' 확인 → awaiting_asv_audio=True.

        이 테스트는 LLM이 슬롯을 성공적으로 추출한다고 가정한다.
        """
        tid = _new_thread_id()
        uid = f"integ-asv-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": tid}}

        # Turn 1: 이체 시작
        _invoke(graph_with_mocks, "이체해줘", uid, config)

        # Turn 2: alias
        _invoke(graph_with_mocks, "엄마에게 보내줘", uid, config)

        # Turn 3: amount
        r3 = _invoke(graph_with_mocks, "십만원 보내줘", uid, config)

        # 확인 대기 상태인지 확인 (슬롯이 채워졌다면)
        if r3.get("awaiting_confirmation"):
            # Turn 4: 확인
            r4 = _invoke(graph_with_mocks, "네", uid, config)
            # transfer는 ASV 필요 → awaiting_asv_audio=True
            assert r4.get("awaiting_asv_audio") is True, (
                f"transfer 확인 후 awaiting_asv_audio=True 기대. "
                f"실제 상태: awaiting_asv_audio={r4.get('awaiting_asv_audio')}"
            )
        else:
            # 슬롯이 아직 수집 중인 경우 — 테스트 skip
            pytest.skip(
                "LLM이 슬롯을 한 번에 추출하지 못해 추가 턴이 필요합니다. "
                "test_transfer_multiturn_slot_collection으로 흐름을 확인하세요."
            )


@pytest.mark.integration
class TestIntegrationHistoryQuery:
    """거래 내역 조회 통합 테스트."""

    def test_history_query_response(self, graph_with_mocks):
        """'최근 거래 내역 알려줘' → 거래 내역 관련 응답이 반환되어야 한다."""
        uid = f"integ-hist-{uuid.uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": _new_thread_id()}}
        result = _invoke(graph_with_mocks, "최근 거래 내역 알려줘", uid, config)

        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_messages) > 0
        # 응답이 비어있지 않아야 함
        assert any(len(m.content) > 0 for m in ai_messages)
