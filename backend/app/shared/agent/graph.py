"""LangGraph 에이전트 그래프 빌드 모듈 — Phase 2.5 StateGraph 구현.

공개 인터페이스 (Issue #5에서 고정, 변경 없음):
    build_graph(tools) → CompiledStateGraph

Phase 2.5 구현 (Issue #21): create_react_agent → StateGraph + MemorySaver 교체.
노드 구성:
    intent_node:    LLM으로 인텐트 파악 + 슬롯 추출 + 확인 감지
    slot_fill_node: 누락 슬롯 질문 생성 (TTS 템플릿)
    confirm_node:   슬롯 완전 수집 후 확인 메시지 생성
    execute_node:   tool 직접 호출 (mock 또는 실제)

호출부(shared/voice/router.py, Issue #7)는 이 함수 시그니처에만 의존한다.
내부 구현이 교체되어도 호출부는 수정이 필요하지 않다.
"""

import json
import logging

import openai
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.core.config import settings
from app.core.exception import AgentError
from app.shared.agent.prompts import SYSTEM_PROMPT
from app.shared.agent.slot_schema import (
    ACTION_LABELS,
    ASV_REQUIRED_ACTIONS,
    COMPLETE_SCREEN_MAP,
    NO_CONFIRM_ACTIONS,
    RECIPIENT_REQUIRED_ACTIONS,
    REQUIRED_SLOTS,
    SCREEN_MAP,
    SLOT_QUESTIONS,
    SLOT_SCHEMA,
    VALID_INTENTS,
)
from app.shared.agent.state import VoiceState

logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """intent_node의 LLM 구조화 응답 스키마."""

    intent: str | None = None
    extracted_slots: dict = {}
    user_confirmed: bool = False
    user_cancelled: bool = False
    direct_response: str = ""


def _all_slots_filled(pending_action: str, collected_slots: dict) -> bool:
    required = REQUIRED_SLOTS.get(pending_action, [])
    return all(collected_slots.get(slot) for slot in required)


def _missing_slots(pending_action: str, collected_slots: dict) -> list[str]:
    required = REQUIRED_SLOTS.get(pending_action, [])
    return [s for s in required if not collected_slots.get(s)]


def _format_confirm_message(pending_action: str, collected_slots: dict) -> str:
    action_label = ACTION_LABELS.get(pending_action, pending_action)
    parts: list[str] = []

    recipient = collected_slots.get("recipient")
    amount = collected_slots.get("amount")
    cycle = collected_slots.get("cycle")
    scheduled_day = collected_slots.get("scheduled_day")

    if recipient:
        parts.append(f"{recipient}에게")
    if cycle:
        freq_label = "매월" if cycle == "monthly" else "매주"
        parts.append(freq_label)
    if scheduled_day:
        parts.append(f"{scheduled_day}일")
    if amount:
        try:
            parts.append(_amount_to_korean(int(amount)))
        except (ValueError, TypeError):
            parts.append(str(amount))

    summary = " ".join(parts)
    return f"{summary} {action_label}할까요?"


def _amount_to_korean(amount: int) -> str:
    if amount <= 0:
        return "영 원"
    units = [
        (100_000_000, "억"),
        (10_000, "만"),
        (1_000, "천"),
        (100, "백"),
        (10, "십"),
    ]
    parts: list[str] = []
    remaining = amount
    for unit_val, unit_name in units:
        if remaining >= unit_val:
            cnt = remaining // unit_val
            remaining %= unit_val
            parts.append(f"{cnt}{unit_name}")
    if remaining > 0:
        parts.append(str(remaining))
    return "".join(parts) + " 원"


def build_graph(tools: list) -> CompiledStateGraph:
    """모든 tool을 받아 LangGraph StateGraph를 빌드한다.

    Args:
        tools: LangChain @tool 데코레이터로 정의된 함수 목록.

    Returns:
        MemorySaver가 연결된 CompiledStateGraph.

    Raises:
        AgentError(code="AGENT_CONFIG_ERROR"): OPENAI_CHAT_API_KEY 미설정 오류.
        AgentError(code="AGENT_INIT_FAILED"): 그래프 컴파일 중 예기치 못한 오류.
    """
    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            temperature=0,
        )
        llm_structured = llm.with_structured_output(
            IntentResult, method="function_calling"
        )
    except openai.OpenAIError as e:
        raise AgentError(
            code="AGENT_CONFIG_ERROR",
            message="AI 에이전트 설정 오류가 발생했습니다.",
            status_code=500,
        ) from e

    tool_registry: dict[str, object] = {t.name: t for t in tools}

    def _find_tool_for_action(action: str) -> object | None:
        candidates = [
            f"mock_execute_{action}",
            f"mock_register_{action}",
            f"mock_get_{action}",
            f"mock_query_{action}",
            f"execute_{action}",
            f"register_{action}",
            f"query_{action}",
            f"{action}_tool",
        ]
        for name in candidates:
            if name in tool_registry:
                return tool_registry[name]
        for name, tool_obj in tool_registry.items():
            if action in name:
                return tool_obj
        return None

    def intent_node(state: VoiceState) -> dict:
        logger.info(
            "[Graph →intent_node] pending=%s slots=%s await_confirm=%s",
            state.get("pending_action"),
            state.get("collected_slots", {}),
            state.get("awaiting_confirmation", False),
        )
        context_lines = [SYSTEM_PROMPT, "", "=== 현재 대화 상태 ==="]
        pending = state.get("pending_action")
        slots = state.get("collected_slots", {})

        if pending:
            missing = _missing_slots(pending, slots)
            context_lines.append(f"진행 중인 액션: {pending}")
            context_lines.append(f"수집된 슬롯: {json.dumps(slots, ensure_ascii=False)}")
            context_lines.append(f"누락된 슬롯: {missing}")

        if state.get("awaiting_confirmation"):
            context_lines.append("대기 상태: 사용자 확인('네'/'아니오') 대기 중")

        context_lines += [
            "",
            "=== 응답 지침 ===",
            "다음 JSON 스키마로 응답하시오:",
            "{",
            f'  "intent": null | {list(VALID_INTENTS)},',
            '  "extracted_slots": {},',
            '  "user_confirmed": false,',
            '  "user_cancelled": false,',
            '  "direct_response": ""',
            "}",
            "",
            "규칙:",
            f"- 유효한 인텐트 목록: {list(VALID_INTENTS)}",
            "- intent: 금융 작업 유형이 파악되면 반드시 설정. 슬롯 채우기 진행 중이면 null.",
            "  예) '이체해줘' → intent='transfer'",
            "  예) '잔액 얼마야' → intent='asset', extracted_slots={'action': 'balance'}",
            "  예) '이번달 식비 얼마야' → intent='asset', extracted_slots={'action': 'category', 'period': '이번달', 'category': '식비'}",
            "  예) '최근 거래 내역' → intent='asset', extracted_slots={'action': 'history', 'period': '최근7일'}",
            "- extracted_slots: 발화에서 파악한 슬롯 값.",
            "  asset 인텐트 슬롯: action('balance'|'history'|'category'), period('이번달'|'지난달'|'최근7일'), category(카테고리명), date_range(ISO YYYY-MM-DD)",
            "  transfer 슬롯: recipient(수신자명), amount(원화 정수 문자열)",
            "- user_confirmed: '네', '맞아요', '그렇게 해줘' 등 확인 발화 시 true",
            "- user_cancelled: '취소', '아니오', '됐어' 등 취소 발화 시 true",
            "- direct_response: 비금융 챗봇 답변에만 사용. intent 설정 시 반드시 빈 문자열.",
            "- TTS 출력: 마크다운 없이 자연스러운 한국어 구어체만 사용",
        ]

        system_content = "\n".join(context_lines)
        chat_messages: list = [{"role": "system", "content": system_content}]
        for msg in state.get("messages", []):
            if hasattr(msg, "type"):
                role = "user" if msg.type == "human" else "assistant"
                chat_messages.append({"role": role, "content": msg.content})

        try:
            result: IntentResult = llm_structured.invoke(chat_messages)
            logger.info(
                "[Agent] intent=%s slots=%s confirmed=%s cancelled=%s",
                result.intent,
                result.extracted_slots,
                result.user_confirmed,
                result.user_cancelled,
            )
        except Exception as e:
            logger.warning("intent_node LLM 호출 실패: %s", e)
            return {
                "messages": [AIMessage(content="일시적인 오류가 발생했습니다. 다시 말씀해 주세요.")],
            }

        updates: dict = {}

        if result.user_cancelled:
            return {
                "pending_action": None,
                "collected_slots": {},
                "awaiting_confirmation": False,
                "awaiting_asv_audio": False,
                "asv_retry_count": 0,
                "navigate_to": None,
                "execution_ready": False,
                "recipient_validated": False,
                "messages": [AIMessage(content=result.direct_response or "취소되었습니다.")],
            }

        if state.get("awaiting_confirmation") and result.user_confirmed:
            action = state.get("pending_action", "")
            if action in ASV_REQUIRED_ACTIONS:
                return {
                    "awaiting_confirmation": False,
                    "awaiting_asv_audio": True,
                    "messages": [AIMessage(content="목소리로 인증해 주세요.")],
                }
            else:
                return {
                    "awaiting_confirmation": False,
                    "execution_ready": True,
                }

        if result.intent and result.intent in VALID_INTENTS and not pending:
            new_slots = dict(result.extracted_slots)
            updates["pending_action"] = result.intent
            updates["navigate_to"] = SCREEN_MAP.get(result.intent)
            updates["collected_slots"] = new_slots
            updates["recipient_validated"] = False

        elif result.extracted_slots and pending:
            existing = dict(state.get("collected_slots", {}))
            existing.update(result.extracted_slots)
            updates["collected_slots"] = existing
            updates["navigate_to"] = None

        if result.direct_response:
            updates["messages"] = [AIMessage(content=result.direct_response)]

        return updates

    def slot_fill_node(state: VoiceState) -> dict:
        pending = state.get("pending_action", "")
        slots = state.get("collected_slots", {})
        missing = _missing_slots(pending, slots)
        logger.info("[Graph →slot_fill_node] pending=%s missing=%s", pending, missing)

        # asset 인텐트: history/category 액션인데 period 없으면 기간 질문
        if (
            pending == "asset"
            and slots.get("action") in ("history", "category")
            and not slots.get("period")
        ):
            question = "며칠 동안의 내역을 보시겠습니까? 이번달, 지난달, 최근 칠일 중 말씀해 주세요."
        elif missing:
            slot_name = missing[0]
            if slot_name == "scheduled_day" and slots.get("cycle") == "weekly":
                question = "매주 무슨 요일에 이체할까요? 월요일부터 일요일 중 말씀해 주세요."
            else:
                question = SLOT_QUESTIONS.get(slot_name, f"{slot_name}을 말씀해 주세요.")
        else:
            question = "정보가 모두 수집되었습니다."

        return {"messages": [AIMessage(content=question)]}

    def confirm_node(state: VoiceState) -> dict:
        pending = state.get("pending_action", "")
        slots = state.get("collected_slots", {})
        logger.info("[Graph →confirm_node] pending=%s slots=%s", pending, slots)
        confirm_msg = _format_confirm_message(pending, slots)
        return {
            "awaiting_confirmation": True,
            "messages": [AIMessage(content=confirm_msg)],
        }

    def resolve_node(state: VoiceState) -> dict:
        slots = dict(state.get("collected_slots", {}))
        recipient_input = slots.get("recipient", "")
        logger.info("[Graph →resolve_node] recipient=%s", recipient_input)
        user_id = state.get("user_id", "")

        resolver = tool_registry.get("lookup_recipient") or tool_registry.get("mock_lookup_recipient")

        if resolver is None:
            logger.warning("resolve_node: lookup_recipient 툴 미등록, 검증 생략")
            return {"recipient_validated": True}

        try:
            canonical_name: str | None = resolver.invoke(
                {"user_id": user_id, "recipient": recipient_input}
            )
        except Exception as e:
            logger.error("resolve_node 수취인 조회 실패: %s", e)
            canonical_name = None

        if canonical_name is None:
            slots["recipient"] = None
            return {
                "collected_slots": slots,
                "recipient_validated": False,
                "messages": [
                    AIMessage(content=f"'{recipient_input}'을(를) 찾을 수 없습니다. 다시 알려주세요.")
                ],
            }

        slots["recipient"] = canonical_name
        return {"collected_slots": slots, "recipient_validated": True}

    def route_after_resolve(state: VoiceState) -> str:
        slots = state.get("collected_slots", {})
        if not slots.get("recipient"):
            return "slot_fill_node"
        pending = state.get("pending_action", "")
        if _missing_slots(pending, slots):
            return "slot_fill_node"
        return "confirm_node"

    def execute_node(state: VoiceState) -> dict:
        pending = state.get("pending_action", "")
        slots = dict(state.get("collected_slots", {}))
        logger.info("[Graph →execute_node] pending=%s slots=%s", pending, slots)

        tool_obj = _find_tool_for_action(pending)

        if tool_obj is None:
            response_text = "해당 기능을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."
            logger.warning("execute_node: '%s' 액션에 대한 tool을 찾을 수 없습니다.", pending)
        else:
            invoke_args = {"user_id": state.get("user_id", ""), **slots}
            try:
                response_text = tool_obj.invoke(invoke_args)
            except Exception as e:
                logger.error("execute_node tool 호출 실패 (%s): %s", pending, e)
                response_text = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

        updates: dict = {
            "pending_action": None,
            "collected_slots": {},
            "awaiting_confirmation": False,
            "awaiting_asv_audio": False,
            "execution_ready": False,
            "messages": [AIMessage(content=response_text)],
        }
        if pending in COMPLETE_SCREEN_MAP:
            updates["navigate_to"] = COMPLETE_SCREEN_MAP[pending]
        return updates

    def route_after_intent(state: VoiceState) -> str:
        if state.get("awaiting_asv_audio"):
            logger.info("[Graph route] intent_node → END (awaiting_asv_audio)")
            return END

        if state.get("execution_ready"):
            logger.info("[Graph route] intent_node → execute_node (execution_ready)")
            return "execute_node"

        pending = state.get("pending_action")
        if not pending:
            logger.info("[Graph route] intent_node → END (no pending_action)")
            return END

        slots = state.get("collected_slots", {})

        if (
            pending in RECIPIENT_REQUIRED_ACTIONS
            and slots.get("recipient")
            and not state.get("recipient_validated")
        ):
            logger.info("[Graph route] intent_node → resolve_node")
            return "resolve_node"

        missing = _missing_slots(pending, slots)

        if missing:
            logger.info("[Graph route] intent_node → slot_fill_node (missing=%s)", missing)
            return "slot_fill_node"

        # asset 인텐트: history/category는 period 슬롯 추가 요구
        if pending == "asset":
            action = slots.get("action")
            if action in ("history", "category") and not slots.get("period"):
                logger.info("[Graph route] intent_node → slot_fill_node (asset period missing)")
                return "slot_fill_node"

        if pending not in SLOT_SCHEMA:
            logger.info("[Graph route] intent_node → execute_node (no slots required)")
            return "execute_node"

        if pending in NO_CONFIRM_ACTIONS:
            logger.info("[Graph route] intent_node → execute_node (no confirm needed)")
            return "execute_node"

        if not state.get("awaiting_confirmation"):
            logger.info("[Graph route] intent_node → confirm_node (all slots filled)")
            return "confirm_node"

        logger.info("[Graph route] intent_node → END (awaiting_confirmation)")
        return END

    try:
        builder = StateGraph(VoiceState)

        builder.add_node("intent_node", intent_node)
        builder.add_node("slot_fill_node", slot_fill_node)
        builder.add_node("resolve_node", resolve_node)
        builder.add_node("confirm_node", confirm_node)
        builder.add_node("execute_node", execute_node)

        builder.set_entry_point("intent_node")
        builder.add_conditional_edges("intent_node", route_after_intent)
        builder.add_conditional_edges("resolve_node", route_after_resolve)
        builder.add_edge("slot_fill_node", END)
        builder.add_edge("confirm_node", END)
        builder.add_edge("execute_node", END)

        checkpointer = MemorySaver()
        graph = builder.compile(checkpointer=checkpointer)

    except Exception as e:
        raise AgentError(
            code="AGENT_INIT_FAILED",
            message="AI 에이전트를 초기화하지 못했습니다.",
            status_code=500,
        ) from e

    return graph
