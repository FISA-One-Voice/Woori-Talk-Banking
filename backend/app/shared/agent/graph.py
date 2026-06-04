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

Design Ref (Issue #21):
    §graph.py — StateGraph 재구성, 4개 노드 정의
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
from app.features.recipients.service import find_recipient_by_voice
from app.shared.agent.prompts import SYSTEM_PROMPT
from app.shared.agent.slot_schema import (
    ACTION_LABELS,
    ASV_REQUIRED_ACTIONS,
    COMPLETE_SCREEN_MAP,
    NO_CONFIRM_ACTIONS,
    RECIPIENT_REQUIRED_ACTIONS,
    REQUIRED_SLOTS,
    SCREEN_MAP,
    SCREEN_ONLY_INTENTS,
    SLOT_QUESTIONS,
    SLOT_SCHEMA,
    VALID_INTENTS,
)
from app.shared.agent.state import VoiceState

logger = logging.getLogger(__name__)


# ── LLM 응답 스키마 ────────────────────────────────────────────────────────────


class IntentResult(BaseModel):
    """intent_node의 LLM 구조화 응답 스키마.

    Attributes:
        intent: 감지된 인텐트. 없으면 None (일반 챗봇 질의).
        extracted_slots: 발화에서 파악한 슬롯 값. 없으면 {}.
        user_confirmed: 사용자가 확인("네", "맞아요")했는지 여부.
        user_cancelled: 사용자가 취소("취소", "아니오")했는지 여부.
        direct_response: 챗봇 직답 또는 슬롯 부족 시 응답 텍스트.
    """

    intent: str | None = None
    extracted_slots: dict = {}
    user_confirmed: bool = False
    user_cancelled: bool = False
    direct_response: str = ""


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────


def _all_slots_filled(pending_action: str, collected_slots: dict) -> bool:
    required = REQUIRED_SLOTS.get(pending_action, [])
    return all(collected_slots.get(slot) for slot in required)


def _missing_slots(pending_action: str, collected_slots: dict) -> list[str]:
    """수집되지 않은 슬롯 이름 목록을 반환한다."""
    required = REQUIRED_SLOTS.get(pending_action, [])
    return [s for s in required if not collected_slots.get(s)]


def _format_confirm_message(pending_action: str, collected_slots: dict) -> str:
    """수집된 슬롯을 기반으로 TTS 친화적 확인 메시지를 생성한다."""
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
    memo = collected_slots.get("memo")
    if memo:
        return f"{summary} {action_label}할까요? 메모 '{memo}'도 함께 저장합니다."
    return f"{summary} {action_label}할까요?"


def _amount_to_korean(amount: int) -> str:
    """금액을 TTS 친화적 한국어 표현으로 변환한다."""
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


# ── 그래프 빌더 ────────────────────────────────────────────────────────────────


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
    # ── LLM 초기화 ──────────────────────────────────────────────────────────────
    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            temperature=0,  # 뱅킹 도메인: 일관성 > 창의성
        )
        # extracted_slots는 자유형 dict이므로 strict JSON schema 모드 비활성화
        llm_structured = llm.with_structured_output(
            IntentResult, method="function_calling"
        )
    except openai.OpenAIError as e:
        raise AgentError(
            code="AGENT_CONFIG_ERROR",
            message="AI 에이전트 설정 오류가 발생했습니다.",
            status_code=500,
        ) from e

    # ── tool registry ───────────────────────────────────────────────────────────
    tool_registry: dict[str, object] = {t.name: t for t in tools}

    def _find_tool_for_action(action: str) -> object | None:
        """액션 이름에 해당하는 tool을 registry에서 찾는다."""
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

    # ── 노드 정의 ────────────────────────────────────────────────────────────────

    def intent_node(state: VoiceState) -> dict:
        """LLM으로 인텐트를 파악하고 슬롯을 추출한다."""
        # ASV 인증 성공 직후: execution_ready=True이면 LLM 호출 없이 즉시 반환
        if state.get("execution_ready"):
            logger.info(
                "[Graph →intent_node] execution_ready=True — LLM skip, pass-through"
            )
            return {}

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
            context_lines.append(
                f"수집된 슬롯: {json.dumps(slots, ensure_ascii=False)}"
            )
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
            "  예) '어떤 거에 제일 많이 지출했어', '뭐에 돈 많이 썼어', '카테고리별 지출 순위' → intent='asset', extracted_slots={'action': 'top_category'}",
            "  예) '이번달 식비 얼마야' → intent='asset', extracted_slots={'action': 'category', 'period': '이번달', 'category': '식비'}",
            "  예) '이번달 지출 수입 얼마야', '지난달 소비 얼마야' → intent='asset', extracted_slots={'action': 'history', 'period': '이번달'}",
            "  예) '최근 7일 거래내역 알려줘', '지난달 내역 말해줘' → intent='asset', extracted_slots={'action': 'history', 'period': '최근7일'} (기간+알려줘/말해줘 조합은 반드시 asset)",
            "  예) '거래내역 보여줘', '내역 보여줘' (기간 없음) → intent='history' (화면 이동만, 음성 응답 없음)",
            "  ★ '알려줘', '말해줘', '얼마야' + 기간('이번달','지난달','최근7일') → 반드시 intent='asset'",
            "  예) '홈 화면', '처음으로', '홈으로 가줘' → intent='home'",
            "- extracted_slots: 발화에서 파악한 슬롯 값.",
            "  asset 인텐트 슬롯: action('balance'|'history'|'category'|'top_category'), period('이번달'|'지난달'|'최근7일'만 허용), category(카테고리명)",
            "  action 선택 기준: balance=잔액조회, history=수입지출요약, category=특정카테고리조회, top_category=어떤카테고리에 많이 썼는지",
            "  '다음달' 등 미래 기간 요청 시 intent를 설정하지 말고 direct_response로 '다음달 데이터는 아직 없습니다. 이번달, 지난달, 최근 7일 중 말씀해 주세요.'라고 안내하시오.",
            "  transfer 슬롯: recipient(수신자명), amount(원화 정수 문자열), memo(메모 문자열, 선택)",
            "  auto_transfer 슬롯: recipient, amount, cycle('monthly'|'weekly'), scheduled_day(숫자), memo(선택)",
            "  transfer_history 인텐트: '이체 내역', '누구한테 보냈어', '자동이체 목록' 등 이체 조회 발화",
            "  예) '엄마에게 오만 원 이체하고 생일축하라고 메모해줘' → intent='transfer', extracted_slots={'recipient':'엄마','amount':'50000','memo':'생일축하'}",
            "  예) '최근 이체 내역 알려줘' → intent='transfer_history'",
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
                "messages": [
                    AIMessage(content="일시적인 오류가 발생했습니다. 다시 말씀해 주세요.")
                ],
            }

        updates: dict = {}

        # ── 취소 처리 ──────────────────────────────────────────────────────────
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
                "messages": [
                    AIMessage(content=result.direct_response or "취소되었습니다.")
                ],
            }

        # ── 확인 수신 처리 ─────────────────────────────────────────────────────
        if state.get("awaiting_confirmation") and result.user_confirmed:
            action = state.get("pending_action", "")
            if action in ASV_REQUIRED_ACTIONS:
                updates = {
                    "awaiting_confirmation": False,
                    "awaiting_asv_audio": True,
                    "messages": [AIMessage(content="목소리로 인증해 주세요.")],
                }
            else:
                updates = {
                    "awaiting_confirmation": False,
                    "execution_ready": True,
                }
            return updates

        if result.intent and result.intent in VALID_INTENTS and not pending:
            new_slots = dict(result.extracted_slots)
            updates["pending_action"] = result.intent
            # asset 인텐트: 액션별 화면 이동 분기
            if result.intent == "asset":
                action = new_slots.get("action")
                if action in ("history", "category", "top_category"):
                    period_val = new_slots.get("period", "")
                    nav = f"asset/history?period={period_val}" if period_val else "asset/history"
                    updates["navigate_to"] = nav
                else:
                    # balance → 자산 홈 화면으로 이동
                    updates["navigate_to"] = "asset"
            else:
                updates["navigate_to"] = SCREEN_MAP.get(result.intent)
            updates["collected_slots"] = new_slots
            updates["recipient_validated"] = False

            # SCREEN_ONLY 인텐트는 execute_node 없이 END → 마지막 메시지가 HumanMessage가 되어
            # TTS가 유저 발화를 그대로 따라하는 문제 방지
            if result.intent in SCREEN_ONLY_INTENTS:
                _nav_msgs: dict[str, str] = {
                    "history": "최근 거래 내역 보여드리겠습니다.",
                    "event": "진행 중인 이벤트 보여드리겠습니다.",
                }
                updates["messages"] = [
                    AIMessage(content=_nav_msgs.get(result.intent, "화면으로 이동합니다."))
                ]

        elif result.extracted_slots and pending:
            existing = dict(state.get("collected_slots", {}))
            existing.update(result.extracted_slots)
            updates["collected_slots"] = existing
            updates["navigate_to"] = None

        if result.direct_response:
            updates["messages"] = [AIMessage(content=result.direct_response)]
        elif "messages" not in updates:
            # intent도 슬롯도 direct_response도 없는 경우 — HumanMessage가 마지막에 남아
            # "죄송합니다" fallback이 나오지 않도록 안내 메시지 추가
            updates["messages"] = [
                AIMessage(content="이체, 잔액 조회, 거래내역 확인 등 필요한 것을 말씀해 주세요.")
            ]

        return updates

    def slot_fill_node(state: VoiceState) -> dict:
        """누락된 첫 번째 슬롯에 대한 질문을 TTS 응답으로 추가한다."""
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
                question = (
                    "매주 무슨 요일에 이체할까요? 월요일부터 일요일 중 말씀해 주세요."
                )
            else:
                question = SLOT_QUESTIONS.get(
                    slot_name, f"{slot_name}을 말씀해 주세요."
                )
        else:
            question = "정보가 모두 수집되었습니다."

        return {"messages": [AIMessage(content=question)]}

    def confirm_node(state: VoiceState) -> dict:
        """슬롯이 완전히 수집되면 확인 메시지를 생성하고 awaiting_confirmation을 설정한다."""
        pending = state.get("pending_action", "")
        slots = state.get("collected_slots", {})
        logger.info("[Graph →confirm_node] pending=%s slots=%s", pending, slots)
        confirm_msg = _format_confirm_message(pending, slots)

        return {
            "awaiting_confirmation": True,
            "messages": [AIMessage(content=confirm_msg)],
        }

    def resolve_node(state: VoiceState) -> dict:
        """recipient 슬롯이 채워진 즉시 수취인 존재 여부를 검증한다."""
        slots = dict(state.get("collected_slots", {}))
        recipient_input = slots.get("recipient", "")
        logger.info(
            "[Graph →resolve_node] recipient=%s user_id=%s",
            recipient_input,
            state.get("user_id"),
        )

        canonical_name: str | None = find_recipient_by_voice(
            state.get("user_id", ""), recipient_input
        )

        if canonical_name is None:
            slots["recipient"] = None
            return {
                "collected_slots": slots,
                "recipient_validated": False,
                "messages": [
                    AIMessage(
                        content=(
                            f"'{recipient_input}'을(를) 찾을 수 없습니다."
                            " 다시 알려주세요."
                        )
                    )
                ],
            }

        slots["recipient"] = canonical_name
        return {
            "collected_slots": slots,
            "recipient_validated": True,
        }

    def route_after_resolve(state: VoiceState) -> str:
        """resolve_node 결과에 따라 다음 노드를 결정한다."""
        slots = state.get("collected_slots", {})
        if not slots.get("recipient"):
            logger.info("[Graph route] resolve_node → slot_fill_node (recipient invalid)")
            return "slot_fill_node"
        pending = state.get("pending_action", "")
        if _missing_slots(pending, slots):
            logger.info(
                "[Graph route] resolve_node → slot_fill_node (missing=%s)",
                _missing_slots(pending, slots),
            )
            return "slot_fill_node"
        logger.info("[Graph route] resolve_node → confirm_node")
        return "confirm_node"

    def execute_node(state: VoiceState) -> dict:
        """수집된 슬롯으로 tool을 직접 호출하고 결과를 TTS 응답으로 추가한다."""
        pending = state.get("pending_action", "")
        slots = dict(state.get("collected_slots", {}))
        logger.info("[Graph →execute_node] pending=%s slots=%s", pending, slots)

        tool_obj = _find_tool_for_action(pending)

        if tool_obj is None:
            logger.warning(
                "execute_node: '%s' 액션에 대한 tool을 찾을 수 없습니다.", pending
            )
            return {
                "pending_action": None,
                "collected_slots": {},
                "awaiting_confirmation": False,
                "awaiting_asv_audio": False,
                "execution_ready": False,
                "recipient_validated": False,
                "asv_retry_count": 0,
                "navigate_to": "home",
                "messages": [
                    AIMessage(
                        content="해당 기능을 아직 사용할 수 없습니다. 홈 화면으로 이동합니다."
                    )
                ],
            }
        else:
            invoke_args = {"user_id": state.get("user_id", ""), **slots}
            try:
                response_text = tool_obj.invoke(invoke_args)
            except Exception as e:
                logger.error("execute_node tool 호출 실패 (%s): %s", pending, e)
                response_text = (
                    "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                )

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

    # ── 조건부 라우팅 ─────────────────────────────────────────────────────────────

    def route_after_intent(state: VoiceState) -> str:
        """intent_node 처리 후 다음 노드를 결정한다."""
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

        # asset 인텐트: 선택 슬롯 추가 요구
        if pending == "asset":
            action = slots.get("action")
            if action in ("history", "category") and not slots.get("period"):
                logger.info("[Graph route] intent_node → slot_fill_node (asset period missing)")
                return "slot_fill_node"
            if action == "category" and not slots.get("category"):
                logger.info("[Graph route] intent_node → slot_fill_node (asset category missing)")
                return "slot_fill_node"

        # 화면 전환 전용 인텐트 (event 등) → 화면이 자체 데이터·TTS 처리
        if pending in SCREEN_ONLY_INTENTS:
            logger.info("[Graph route] intent_node → END (screen-only=%s)", pending)
            return END

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

    # ── StateGraph 빌드 ────────────────────────────────────────────────────────

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
