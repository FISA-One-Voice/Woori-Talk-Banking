"""TransferAgent 서브그래프.

이체, 자동이체, 자동이체 해지, 메모 추가 도메인만 처리한다.
Supervisor 그래프의 MemorySaver를 공유해야 하므로 독립 checkpointer를 만들지 않는다.
"""

import json
import logging
import uuid

import openai
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.core.config import settings
from app.core.exception import AgentError
from app.features.recipients.schema import ResolvedRecipient
from app.features.recipients.service import (
    classify_recipient_input,
    find_recipient_by_voice,
    match_by_registered_account,
)
from app.features.transfer.service import _mask_account
from app.shared.agent.ROUTING_CONSTANTS import (
    TRANSFER_NAVIGATE_VALUES,
    TRANSFER_READ,
)
from app.shared.agent.memo_decision import (
    build_memo_decision_update,
    last_user_text,
)
from app.shared.agent.prompts import SYSTEM_PROMPT, TRANSFER_INTENT_PROMPT
from app.shared.agent.session_reset import clear_conversation_messages
from app.shared.agent.slot_schema import (
    ACTION_LABELS,
    ACTIONS_WITH_YES_NO_CONFIRM,
    ASV_REQUIRED_ACTIONS,
    COMPLETE_SCREEN_MAP,
    CONFIRM_YES_NO_SUFFIX,
    FAILED_SCREEN_MAP,
    MEMO_OFFER_SUFFIX,
    RECIPIENT_REQUIRED_ACTIONS,
    SCREEN_MAP,
    SLOT_QUESTIONS,
    SLOT_QUESTIONS_BY_ACTION,
    SLOT_SCHEMA,
    TRANSFER_FAILED_HOME_SUFFIX,
    transfer_missing_slots,
)
from app.shared.agent.state import VoiceState
from app.shared.agent.transfer_clarification import (
    _recipient_hint_from_state,
    build_transfer_clarification_offer,
    build_transfer_clarification_response,
    should_offer_transfer_clarification,
)
from app.shared.agent.transfer_intent import (
    is_plain_transfer_start,
    should_use_bare_transfer_fast_start,
)
from app.shared.voice.message_utils import _DEFAULT_TTS_FALLBACK

logger = logging.getLogger(__name__)

TRANSFER_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "transfer",
    "auto_transfer",
    "cancel_auto_transfer",
    "add_note",
    "add_auto_transfer_note",
})

TRANSFER_WRITE: frozenset[str] = frozenset({
    "messages",
    "navigate_to",
    "pending_action",
    "collected_slots",
    "awaiting_confirmation",
    "awaiting_asv_audio",
    "execution_ready",
    "recipient_validated",
    "asv_retry_count",
    "awaiting_memo_decision",
    "awaiting_transfer_clarification",
    "draft_recipient",
    "last_tx_id",
    "last_order_id",
})


class IntentResult(BaseModel):
    """TransferAgent intent_node의 구조화 응답."""

    intent: str | None = None
    extracted_slots: dict = {}
    user_confirmed: bool = False
    user_cancelled: bool = False
    direct_response: str = ""


def validate_transfer_delta(delta: dict) -> dict:
    """TransferAgent 출력 계약을 검증한다.

    Args:
        delta: 노드가 반환할 상태 변경 dict.

    Returns:
        검증을 통과한 delta.

    Raises:
        AgentError: 허용되지 않은 필드나 화면 이동 값이 포함된 경우.
    """
    invalid_fields = set(delta) - TRANSFER_WRITE
    if invalid_fields:
        raise AgentError(
            code="AGENT_CONTRACT_VIOLATION",
            message="TransferAgent가 허용되지 않은 상태 필드를 반환했습니다.",
            status_code=500,
            user_message="이체 처리 중 일시적인 오류가 발생했습니다.",
        )

    if "navigate_to" in delta and delta["navigate_to"] not in TRANSFER_NAVIGATE_VALUES:
        raise AgentError(
            code="AGENT_CONTRACT_VIOLATION",
            message="TransferAgent가 허용되지 않은 화면 이동 값을 반환했습니다.",
            status_code=500,
            user_message="이체 처리 중 일시적인 오류가 발생했습니다.",
        )
    return delta


def _clean_transfer_delta(delta: dict) -> dict:
    """ASV 소유권 규칙을 적용한 뒤 출력 계약을 검증한다."""
    cleaned = dict(delta)
    if cleaned.get("awaiting_asv_audio") is False:
        cleaned.pop("awaiting_asv_audio")
    return validate_transfer_delta(cleaned)


def _is_transfer_restart_utterance(text: str) -> bool:
    """홈 등에서 새 송금을 시작하는 발화인지."""
    return is_plain_transfer_start(text)


def _should_restart_transfer_flow(
    intent: str | None,
    pending: str | None,
    user_text: str,
    state: dict,
) -> bool:
    """이전 transfer 세션이 남아 있어도 동일 intent로 새 송금을 시작한다."""
    if intent != "transfer" or pending != "transfer":
        return False
    if state.get("awaiting_confirmation") or state.get("awaiting_asv_audio"):
        return False
    return _is_transfer_restart_utterance(user_text)


def _all_slots_filled(pending_action: str, collected_slots: dict) -> bool:
    """pending_action에 필요한 슬롯이 모두 수집되었는지 확인한다."""
    return len(_missing_slots(pending_action, collected_slots)) == 0


def _missing_slots(pending_action: str, collected_slots: dict) -> list[str]:
    """수집되지 않은 슬롯 이름 목록을 반환한다."""
    if pending_action == "transfer":
        return transfer_missing_slots(collected_slots)

    required = SLOT_SCHEMA.get(pending_action, [])
    missing = []
    for slot_name in required:
        value = collected_slots.get(slot_name)
        if slot_name == "scheduled_day":
            if not _valid_scheduled_day(value, collected_slots.get("cycle")):
                missing.append(slot_name)
        elif not value:
            missing.append(slot_name)
    return missing


def _valid_scheduled_day(value: object, cycle: object) -> bool:
    """자동이체 주기에 맞는 scheduled_day 값인지 확인한다."""
    if value is None or cycle is None:
        return False
    try:
        day = int(value)
    except (TypeError, ValueError):
        return False
    if cycle == "monthly":
        return 1 <= day <= 31
    if cycle == "weekly":
        return 0 <= day <= 6
    return False


def _enrich_slots_from_resolved(
    slots: dict,
    resolved: ResolvedRecipient,
    recipient_input: str,
    user_id: str,
) -> dict:
    """resolve 결과를 collected_slots에 반영한다."""
    from app.core.database import get_db

    display = resolved.recipient_name or "수취인"
    if resolved.recipient_id and classify_recipient_input(recipient_input) == "account":
        db = next(get_db())
        try:
            row = match_by_registered_account(db, uuid.UUID(user_id), recipient_input)
            if row and row.alias:
                display = row.alias
        finally:
            db.close()

    slots["recipient"] = display
    slots["bank_name"] = resolved.bank_name
    slots["account_number"] = resolved.account_number
    if resolved.recipient_id:
        slots["recipient_id"] = str(resolved.recipient_id)
    return slots


def _format_confirm_message(pending_action: str, collected_slots: dict) -> str:
    """수집된 슬롯을 기반으로 TTS 친화적 확인 메시지를 생성한다."""
    action_label = ACTION_LABELS.get(pending_action, pending_action)
    parts: list[str] = []

    recipient = collected_slots.get("recipient")
    bank_name = collected_slots.get("bank_name")
    account_number = collected_slots.get("account_number")
    amount = collected_slots.get("amount")
    cycle = collected_slots.get("cycle")
    scheduled_day = collected_slots.get("scheduled_day")

    if bank_name and account_number:
        masked = _mask_account(str(account_number))
        target = f"{recipient}님 " if recipient else ""
        parts.append(f"{target}{bank_name} 계좌 {masked}로")
    elif recipient:
        parts.append(f"{recipient}에게")

    parts.extend(_format_cycle_parts(cycle, scheduled_day))
    if amount:
        try:
            parts.append(_amount_to_korean(int(amount)))
        except (TypeError, ValueError):
            parts.append(str(amount))

    message = f"{' '.join(parts)} {action_label}할까요?"
    if pending_action in ACTIONS_WITH_YES_NO_CONFIRM:
        message += CONFIRM_YES_NO_SUFFIX
    return message


def _format_cycle_parts(cycle: object, scheduled_day: object) -> list[str]:
    """자동이체 주기 슬롯을 확인 메시지 조각으로 변환한다."""
    dow_labels = ["월", "화", "수", "목", "금", "토", "일"]
    parts: list[str] = []
    if cycle == "monthly":
        parts.append("매월")
        if scheduled_day is not None:
            parts.append(f"{scheduled_day}일")
    elif cycle == "weekly":
        parts.append("매주")
        if scheduled_day is not None:
            try:
                parts.append(f"{dow_labels[int(scheduled_day)]}요일")
            except (IndexError, ValueError):
                parts.append(f"{scheduled_day}요일")
    return parts


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
            count = remaining // unit_val
            remaining %= unit_val
            parts.append(f"{count}{unit_name}")
    if remaining > 0:
        parts.append(str(remaining))
    return "".join(parts) + " 원"


def _build_bare_transfer_start_update(user_text: str) -> dict:
    """수취인·금액 없는 송금 시작 발화를 transfer 상태로 변환한다."""
    return {
        "pending_action": "transfer",
        "navigate_to": SCREEN_MAP["transfer"],
        "collected_slots": {},
        "recipient_validated": False,
        "awaiting_confirmation": False,
        "execution_ready": False,
        "asv_retry_count": 0,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "last_tx_id": None,
        "messages": [
            *clear_conversation_messages(),
            HumanMessage(content=user_text),
        ],
    }


def _build_system_content(state: VoiceState) -> str:
    """TransferAgent intent LLM에 전달할 시스템 프롬프트를 만든다."""
    context_lines = [SYSTEM_PROMPT, TRANSFER_INTENT_PROMPT, "", "=== 현재 대화 상태 ==="]
    pending = state.get("pending_action")
    slots = state.get("collected_slots", {})

    if pending:
        missing = _missing_slots(pending, slots)
        context_lines.append(f"진행 중인 액션: {pending}")
        context_lines.append(f"수집된 슬롯: {json.dumps(slots, ensure_ascii=False)}")
        context_lines.append(f"누락된 슬롯: {missing}")
        if missing:
            context_lines.append(
                f"슬롯 채우기 진행 중입니다. intent는 null로 두고, "
                f"누락 슬롯 {missing}의 값만 extracted_slots에 포함하십시오."
            )

    if state.get("awaiting_confirmation"):
        context_lines.append(
            "대기 상태: 사용자 확인 대기 중입니다. "
            "'네', '응', '맞아', '그렇게 해줘'는 user_confirmed=true입니다. "
            "'아니 6만원으로'처럼 수정 값이 있으면 user_cancelled=false로 두고 "
            "extracted_slots에 수정할 슬롯만 넣으십시오."
        )

    context_lines.extend(_transfer_response_rules())
    return "\n".join(context_lines)


def _transfer_response_rules() -> list[str]:
    """TransferAgent 구조화 응답 규칙을 반환한다."""
    return [
        "",
        "=== 응답 지침 ===",
        "다음 JSON 스키마로 응답하시오:",
        "{",
        f'  "intent": null | {sorted(TRANSFER_DOMAIN_ACTIONS)},',
        '  "extracted_slots": {},',
        '  "user_confirmed": false,',
        '  "user_cancelled": false,',
        '  "direct_response": ""',
        "}",
        "- intent는 진행 중인 액션이 없을 때만 설정하십시오.",
        "- transfer: 일회성 이체, 송금, 보내줘 요청입니다.",
        "- auto_transfer: 자동이체, 정기 이체, 매월, 매주 요청입니다.",
        "- cancel_auto_transfer: 자동이체 해지 요청입니다.",
        "- add_note/add_auto_transfer_note: 직전 이체·자동이체 메모 추가 요청입니다.",
        "- amount는 원화 정수 문자열로 추출하십시오.",
        "- recipient는 이름, 별명, 전화번호, 계좌번호를 발화 그대로 추출하십시오.",
        "- cycle은 monthly 또는 weekly만 사용하십시오.",
        "- scheduled_day는 날짜 또는 요일을 명시한 경우에만 추출하십시오.",
        "- bank_name은 사용자가 은행명을 말한 경우에만 추출하십시오.",
        "- TransferAgent가 처리하지 않는 요청은 intent=null로 두십시오.",
    ]


def _chat_messages_for_llm(state: VoiceState, system_content: str) -> list[dict]:
    """LangChain 메시지 이력을 OpenAI chat 메시지 형식으로 변환한다."""
    chat_messages: list[dict] = [{"role": "system", "content": system_content}]
    for message in state.get("messages", []):
        if hasattr(message, "type"):
            role = "user" if message.type == "human" else "assistant"
            chat_messages.append({"role": role, "content": message.content})
    return chat_messages


def _find_tool_for_action(action: str, tool_registry: dict[str, object]) -> object | None:
    """액션 이름에 해당하는 tool을 registry에서 찾는다."""
    candidates = [
        action,
        f"mock_execute_{action}",
        f"mock_register_{action}",
        f"execute_{action}",
        f"register_{action}",
        f"{action}_tool",
    ]
    for name in candidates:
        if name in tool_registry:
            return tool_registry[name]
    for name, tool_obj in tool_registry.items():
        if action in name:
            return tool_obj
    return None


def _normalize_scheduled_day(slots: dict, extracted_slots: dict) -> dict:
    """STT가 '6일'을 '61'로 인식하는 scheduled_day 오류를 보정한다."""
    normalized = dict(slots)
    for key, value in extracted_slots.items():
        if key == "scheduled_day" and value is not None:
            try:
                day_int = int(value)
            except (TypeError, ValueError):
                day_int = None
            if day_int is not None and 32 <= day_int <= 91 and day_int % 10 == 1:
                value = day_int // 10
        normalized[key] = value
    return normalized


def _build_new_intent_update(result: IntentResult, user_text: str) -> dict:
    """새 Transfer 도메인 intent 감지 시 초기 상태 delta를 만든다."""
    updates = {
        "pending_action": result.intent,
        "navigate_to": SCREEN_MAP.get(result.intent),
        "collected_slots": dict(result.extracted_slots),
        "recipient_validated": False,
        "awaiting_confirmation": False,
        "execution_ready": False,
        "asv_retry_count": 0,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "last_tx_id": None if result.intent == "transfer" else None,
    }
    if result.intent == "transfer":
        updates["messages"] = [
            *clear_conversation_messages(),
            HumanMessage(content=user_text),
        ]
    return updates


def _merge_slot_update(state: VoiceState, extracted_slots: dict) -> dict:
    """진행 중 액션의 누락 슬롯만 보충한다."""
    pending = state.get("pending_action")
    existing = dict(state.get("collected_slots", {}))
    missing_now = _missing_slots(pending or "", existing)
    allowed_updates = {}
    for key, value in extracted_slots.items():
        # scheduled_day·cycle은 항상 업데이트 허용 (상호 의존적, 사용자 수정 가능)
        if (
            key in ("scheduled_day", "cycle")
            or key in missing_now
            or existing.get(key) is None
        ):
            allowed_updates[key] = value
    # cycle이 변경됐고 이번 턴에 scheduled_day를 새로 제공하지 않았다면
    # 기존 scheduled_day는 새 cycle에서 무효할 수 있으므로 초기화한다
    old_cycle = existing.get("cycle")
    new_cycle = allowed_updates.get("cycle")
    if (
        new_cycle is not None
        and new_cycle != old_cycle
        and "scheduled_day" not in allowed_updates
    ):
        existing.pop("scheduled_day", None)
    updated_slots = _normalize_scheduled_day(existing, allowed_updates)
    updates: dict = {"collected_slots": updated_slots, "navigate_to": None}
    if pending == "add_note" and updated_slots.get("memo"):
        updates["execution_ready"] = True
    return updates


def build_transfer_graph(tools: list) -> CompiledStateGraph:
    """TransferAgent StateGraph를 빌드한다.

    Args:
        tools: TransferAgent에서 사용할 LangChain tool 목록.

    Returns:
        부모 Supervisor checkpointer를 공유하는 CompiledStateGraph.

    Raises:
        AgentError: LLM 설정 또는 그래프 초기화에 실패한 경우.
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
    except openai.OpenAIError as exc:
        raise AgentError(
            code="AGENT_CONFIG_ERROR",
            message="TransferAgent 설정 오류가 발생했습니다.",
            status_code=500,
            user_message="AI 서비스에 일시적인 문제가 발생했습니다.",
        ) from exc

    tool_registry: dict[str, object] = {tool.name: tool for tool in tools}

    def intent_node(state: VoiceState) -> dict:
        """Transfer 도메인 intent와 슬롯을 추출한다."""
        if state.get("execution_ready") or state.get("awaiting_asv_audio"):
            return _clean_transfer_delta({"navigate_to": None})

        if state.get("awaiting_memo_decision"):
            note_action = (
                "add_auto_transfer_note" if state.get("last_order_id") else "add_note"
            )
            delta = build_memo_decision_update(
                last_user_text(state.get("messages", [])), note_action=note_action
            )
            return _clean_transfer_delta(delta)

        if state.get("pending_action") == "add_note":
            delta = build_memo_decision_update(last_user_text(state.get("messages", [])))
            return _clean_transfer_delta(delta)

        if state.get("awaiting_transfer_clarification"):
            user_text = last_user_text(state.get("messages", []))
            draft = _recipient_hint_from_state(
                state.get("draft_recipient") or "", state.get("collected_slots")
            )
            return _clean_transfer_delta(
                build_transfer_clarification_response(user_text, draft)
            )

        user_text = last_user_text(state.get("messages", []))
        if should_use_bare_transfer_fast_start(user_text):
            return _clean_transfer_delta(_build_bare_transfer_start_update(user_text))

        if should_offer_transfer_clarification(
            user_text,
            pending_action=state.get("pending_action"),
            awaiting_memo_decision=state.get("awaiting_memo_decision", False),
            awaiting_transfer_clarification=state.get(
                "awaiting_transfer_clarification", False
            ),
            awaiting_confirmation=state.get("awaiting_confirmation", False),
            awaiting_asv_audio=state.get("awaiting_asv_audio", False),
        ):
            return _clean_transfer_delta(build_transfer_clarification_offer(user_text))

        result = llm_structured.invoke(
            _chat_messages_for_llm(state, _build_system_content(state))
        )
        return _clean_transfer_delta(_build_intent_update(state, result, user_text))

    def slot_fill_node(state: VoiceState) -> dict:
        """누락된 첫 번째 슬롯에 대한 질문을 추가한다."""
        pending = state.get("pending_action", "")
        slots = state.get("collected_slots", {})
        missing = _missing_slots(pending, slots)

        if missing:
            slot_name = missing[0]
            action_questions = SLOT_QUESTIONS_BY_ACTION.get(pending, {})
            if slot_name in action_questions:
                question = action_questions[slot_name]
            elif slot_name == "scheduled_day" and slots.get("cycle") == "weekly":
                question = "매주 무슨 요일에 이체할까요? 월요일부터 일요일 중 말씀해 주세요."
            else:
                question = SLOT_QUESTIONS.get(slot_name, f"{slot_name}을 말씀해 주세요.")
        else:
            question = "정보가 모두 수집되었습니다."

        return _clean_transfer_delta({"messages": [AIMessage(content=question)]})

    def confirm_node(state: VoiceState) -> dict:
        """슬롯 수집 완료 후 사용자 확인 메시지를 생성한다."""
        pending = state.get("pending_action", "")
        confirm_message = _format_confirm_message(
            pending, state.get("collected_slots", {})
        )
        return _clean_transfer_delta({
            "awaiting_confirmation": True,
            "navigate_to": SCREEN_MAP.get(pending),
            "messages": [AIMessage(content=confirm_message)],
        })

    def resolve_node(state: VoiceState) -> dict:
        """recipient 슬롯을 등록 수취인 또는 직접 계좌 정보로 검증한다."""
        slots = dict(state.get("collected_slots", {}))
        recipient_input = str(slots.get("recipient", ""))
        bank_name = slots.get("bank_name")
        user_id = state.get("user_id", "")
        kind = classify_recipient_input(recipient_input) if recipient_input else "name"

        resolved = find_recipient_by_voice(
            user_id,
            recipient_input,
            bank_name=str(bank_name) if bank_name else None,
        )
        if resolved is not None:
            _enrich_slots_from_resolved(slots, resolved, recipient_input, user_id)
            return _clean_transfer_delta({
                "collected_slots": slots,
                "recipient_validated": True,
            })

        if kind == "account" and not bank_name:
            return _clean_transfer_delta({
                "collected_slots": slots,
                "recipient_validated": False,
                "navigate_to": None,
            })

        if kind in ("phone", "account"):
            return _clean_transfer_delta({
                "collected_slots": slots,
                "recipient_validated": False,
                "navigate_to": None,
                "messages": [
                    AIMessage(
                        content=(
                            f"'{recipient_input}'은(는) 등록된 수취인이 아닙니다. "
                            "수신인 이름이나 별명, 계좌번호를 다시 말씀해 주세요."
                        )
                    )
                ],
            })

        pending_action = state.get("pending_action", "transfer")
        slots["recipient"] = None
        return _clean_transfer_delta({
            "collected_slots": slots,
            "recipient_validated": False,
            "navigate_to": SCREEN_MAP.get(pending_action),
            "messages": [
                AIMessage(
                    content=(
                        f"'{recipient_input}'은(는) 등록되지 않은 수취인입니다. "
                        "누구에게 보낼까요?"
                    )
                )
            ],
        })

    def execute_node(state: VoiceState) -> dict:
        """수집된 슬롯으로 Transfer 도메인 tool을 호출한다."""
        pending = state.get("pending_action", "")
        slots = dict(state.get("collected_slots", {}))
        tool_obj = _find_tool_for_action(pending, tool_registry)
        if tool_obj is None:
            raise AgentError(
                code="TRANSFER_TOOL_NOT_FOUND",
                message=f"'{pending}' 액션에 대한 tool을 찾을 수 없습니다.",
                status_code=500,
                user_message="해당 이체 기능을 아직 사용할 수 없습니다.",
            )
        return _clean_transfer_delta(_execute_transfer_tool(state, tool_obj, slots))

    def route_after_intent(state: VoiceState) -> str:
        """intent_node 이후 다음 노드를 결정한다."""
        if state.get("awaiting_asv_audio"):
            return END
        if state.get("awaiting_memo_decision"):
            return END
        if state.get("awaiting_transfer_clarification"):
            return END
        if state.get("execution_ready"):
            return "execute_node"

        pending = state.get("pending_action")
        if not pending:
            return END

        slots = state.get("collected_slots", {})
        if (
            pending in RECIPIENT_REQUIRED_ACTIONS
            and slots.get("recipient")
            and not state.get("recipient_validated")
        ):
            return "resolve_node"

        missing = _missing_slots(pending, slots)
        if missing:
            return "slot_fill_node"
        if pending not in SLOT_SCHEMA:
            return "execute_node"
        if not state.get("awaiting_confirmation"):
            return "confirm_node"
        return END

    def route_after_resolve(state: VoiceState) -> str:
        """resolve_node 이후 다음 노드를 결정한다."""
        slots = state.get("collected_slots", {})
        pending = state.get("pending_action", "")
        missing = _missing_slots(pending, slots)

        if not slots.get("recipient"):
            return END
        if not state.get("recipient_validated"):
            if missing == ["amount"]:
                return END
            if missing:
                return "slot_fill_node"
            return END
        if missing:
            return "slot_fill_node"
        return "confirm_node"

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
        return builder.compile(checkpointer=None)
    except Exception as exc:
        raise AgentError(
            code="TRANSFER_AGENT_INIT_FAILED",
            message="TransferAgent를 초기화하지 못했습니다.",
            status_code=500,
            user_message="AI 서비스에 일시적인 문제가 발생했습니다.",
        ) from exc


def _build_intent_update(
    state: VoiceState,
    result: IntentResult,
    user_text: str,
) -> dict:
    """LLM intent 결과를 TransferAgent 상태 delta로 변환한다."""
    if state.get("awaiting_confirmation") and result.user_confirmed:
        action = state.get("pending_action", "")
        if action in ASV_REQUIRED_ACTIONS:
            return {
                "awaiting_confirmation": False,
                "awaiting_asv_audio": True,
                "navigate_to": SCREEN_MAP.get(action),
                "messages": [AIMessage(content="목소리로 인증해 주세요.")],
            }
        return {"awaiting_confirmation": False, "execution_ready": True}

    if state.get("awaiting_confirmation") and result.extracted_slots:
        existing = dict(state.get("collected_slots", {}))
        existing.update(result.extracted_slots)
        return {
            "collected_slots": existing,
            "awaiting_confirmation": False,
            "recipient_validated": (
                False
                if "recipient" in result.extracted_slots
                else state.get("recipient_validated", False)
            ),
            "navigate_to": None,
        }

    if state.get("awaiting_confirmation") and not result.direct_response:
        return {
            "messages": [
                AIMessage(
                    content=(
                        CONFIRM_YES_NO_SUFFIX.strip()
                        + " 변경하실 내용이 있으면 말씀해 주시면 반영해 드립니다."
                    )
                )
            ],
            "navigate_to": None,
        }

    pending = state.get("pending_action")
    restart_transfer = _should_restart_transfer_flow(
        result.intent, pending, user_text, state
    )
    if (
        result.intent
        and result.intent in TRANSFER_DOMAIN_ACTIONS
        and not state.get("awaiting_confirmation")
        and not state.get("awaiting_asv_audio")
        and (result.intent != pending or restart_transfer)
    ):
        return _build_new_intent_update(result, user_text)

    if result.extracted_slots and pending:
        return _merge_slot_update(state, result.extracted_slots)

    if result.direct_response:
        return {"messages": [AIMessage(content=result.direct_response)], "navigate_to": None}

    pending_after = pending or result.intent
    if not pending_after and not is_plain_transfer_start(user_text):
        return {"messages": [AIMessage(content=_DEFAULT_TTS_FALLBACK)], "navigate_to": None}
    return {"navigate_to": None}


def _execute_transfer_tool(state: VoiceState, tool_obj: object, slots: dict) -> dict:
    """pending_action에 맞는 tool을 호출하고 완료 delta를 만든다."""
    from app.shared.agent.tools.transfer import run_execute_transfer

    pending = state.get("pending_action", "")
    invoke_args = {"user_id": state.get("user_id", ""), **slots}
    last_tx_id: str | None = state.get("last_tx_id")
    last_order_id: str | None = state.get("last_order_id")
    completed_slots: dict = {}
    note_consumed = False
    awaiting_memo_next = False
    post_execute_navigate: str | None = None

    try:
        if pending == "transfer" and tool_obj.name == "execute_transfer":
            response_text, tx_id = run_execute_transfer(
                user_id=invoke_args["user_id"],
                recipient=str(invoke_args.get("recipient", "")),
                amount=int(invoke_args.get("amount", 0)),
                collected_slots=slots,
            )
            order_id = None
            note_consumed = False
        else:
            response_text, tx_id, order_id, note_consumed = _invoke_tool_by_action(
                pending, tool_obj, invoke_args, slots, state
            )
    except Exception as exc:
        raise AgentError(
            code="TRANSFER_TOOL_FAILED",
            message="TransferAgent tool 호출에 실패했습니다.",
            status_code=500,
            user_message="이체 처리 중 일시적인 오류가 발생했습니다.",
        ) from exc

    if pending == "transfer":
        if tx_id:
            last_tx_id = tx_id
            awaiting_memo_next = True
            response_text = response_text + MEMO_OFFER_SUFFIX
            completed_slots = {"tx_id": tx_id}
            post_execute_navigate = COMPLETE_SCREEN_MAP["transfer"]
        elif tool_obj.name != "execute_transfer":
            completed_slots = {}
            post_execute_navigate = COMPLETE_SCREEN_MAP["transfer"]
        else:
            completed_slots = {**slots, "transfer_error_message": response_text}
            post_execute_navigate = "home"
    elif pending == "auto_transfer" and order_id:
        last_order_id = order_id
        awaiting_memo_next = True
        response_text = response_text + MEMO_OFFER_SUFFIX

    if post_execute_navigate == FAILED_SCREEN_MAP.get("transfer"):
        response_text = response_text.rstrip() + TRANSFER_FAILED_HOME_SUFFIX
        completed_slots["transfer_error_message"] = response_text

    updates: dict = {
        "pending_action": None,
        "collected_slots": completed_slots,
        "awaiting_confirmation": False,
        "awaiting_memo_decision": awaiting_memo_next,
        "execution_ready": False,
        "recipient_validated": False,
        "messages": [AIMessage(content=response_text)],
        "last_tx_id": None if note_consumed else last_tx_id,
        "last_order_id": None if note_consumed else last_order_id,
    }
    if note_consumed:
        updates["awaiting_memo_decision"] = False
        updates["navigate_to"] = "home"
        updates["messages"] = [
            *clear_conversation_messages(),
            AIMessage(content=response_text),
        ]
    elif post_execute_navigate is not None:
        updates["navigate_to"] = post_execute_navigate
    elif pending in COMPLETE_SCREEN_MAP:
        updates["navigate_to"] = COMPLETE_SCREEN_MAP[pending]
    return updates


def _invoke_tool_by_action(
    pending: str,
    tool_obj: object,
    invoke_args: dict,
    slots: dict,
    state: VoiceState,
) -> tuple[str, str | None, str | None, bool]:
    """액션별 tool 호출 결과를 표준 tuple로 반환한다."""
    response_text = ""
    tx_id: str | None = None
    order_id: str | None = None
    note_consumed = False

    if pending == "transfer":
        response_text = tool_obj.invoke(invoke_args)
    elif pending == "auto_transfer":
        result_raw = tool_obj.invoke(invoke_args)
        result_data = json.loads(result_raw) if isinstance(result_raw, str) else {}
        response_text = result_data.get("tts_text", "자동이체 등록 중 오류가 발생했습니다.")
        if result_data.get("success"):
            order_id = result_data.get("order_id")
    elif pending == "add_note":
        response_text = _invoke_add_note(tool_obj, invoke_args, slots, state)
        note_consumed = "추가되었습니다" in response_text
    elif pending == "add_auto_transfer_note":
        response_text = _invoke_add_auto_transfer_note(tool_obj, invoke_args, slots, state)
        note_consumed = "추가되었습니다" in response_text
    else:
        response_text = tool_obj.invoke(invoke_args)
    return response_text, tx_id, order_id, note_consumed


def _invoke_add_note(
    tool_obj: object,
    invoke_args: dict,
    slots: dict,
    state: VoiceState,
) -> str:
    """직전 이체 거래에 메모를 추가한다."""
    tx_id = slots.get("tx_id") or state.get("last_tx_id")
    if not tx_id:
        return "메모를 추가할 이체 내역을 찾을 수 없습니다. 이체를 먼저 완료해 주세요."
    return tool_obj.invoke({
        "user_id": invoke_args["user_id"],
        "memo": str(invoke_args.get("memo", "")),
        "tx_id": str(tx_id),
    })


def _invoke_add_auto_transfer_note(
    tool_obj: object,
    invoke_args: dict,
    slots: dict,
    state: VoiceState,
) -> str:
    """직전 자동이체 주문에 메모를 추가한다."""
    order_id = slots.get("order_id") or state.get("last_order_id")
    if not order_id:
        return "메모를 추가할 자동이체 내역을 찾을 수 없습니다. 자동이체 등록을 먼저 완료해 주세요."
    return tool_obj.invoke({
        "user_id": invoke_args["user_id"],
        "memo": str(invoke_args.get("memo", "")),
        "order_id": str(order_id),
    })
