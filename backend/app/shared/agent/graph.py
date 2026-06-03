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
import uuid

import openai
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.core.config import settings
from app.core.exception import AgentError
from app.features.recipients.service import (
    classify_recipient_input,
    find_recipient_by_voice,
    match_by_registered_account,
)
from app.features.recipients.schema import ResolvedRecipient
from app.features.transfer.service import _mask_account
from app.shared.agent.prompts import SYSTEM_PROMPT
from app.shared.agent.memo_decision import (
    build_memo_decision_update,
    last_user_text,
)
from app.shared.agent.session_reset import clear_conversation_messages
from app.shared.agent.transfer_intent import (
    build_bare_transfer_start_update,
    is_plain_transfer_start,
    should_use_bare_transfer_fast_start,
)
from app.shared.agent.transfer_clarification import (
    _recipient_hint_from_state,
    build_transfer_clarification_offer,
    build_transfer_clarification_response,
    should_offer_transfer_clarification,
)
from app.shared.voice.message_utils import _DEFAULT_TTS_FALLBACK
from app.shared.agent.slot_schema import (
    ACTION_LABELS,
    ACTIONS_WITH_YES_NO_CONFIRM,
    ASV_REQUIRED_ACTIONS,
    CONFIRM_YES_NO_SUFFIX,
    COMPLETE_SCREEN_MAP,
    MEMO_OFFER_SUFFIX,
    RECIPIENT_REQUIRED_ACTIONS,
    SCREEN_MAP,
    SCREEN_ONLY_INTENTS,
    SLOT_QUESTIONS,
    SLOT_QUESTIONS_BY_ACTION,
    SLOT_SCHEMA,
    VALID_INTENTS,
    transfer_missing_slots,
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
    if pending_action == "transfer":
        return len(transfer_missing_slots(collected_slots)) == 0
    required = SLOT_SCHEMA.get(pending_action, [])
    return all(collected_slots.get(slot) for slot in required)


def _missing_slots(pending_action: str, collected_slots: dict) -> list[str]:
    """수집되지 않은 슬롯 이름 목록을 반환한다."""
    if pending_action == "transfer":
        return transfer_missing_slots(collected_slots)
    required = SLOT_SCHEMA.get(pending_action, [])
    missing = []
    for s in required:
        val = collected_slots.get(s)
        if s == "scheduled_day":
            cycle = collected_slots.get("cycle")
            valid = False
            if val is not None:
                try:
                    n = int(val)
                    if cycle == "monthly":
                        valid = 1 <= n <= 31
                    elif cycle == "weekly":
                        valid = 0 <= n <= 6
                    else:
                        valid = True
                except (TypeError, ValueError):
                    pass
            if not valid:
                missing.append(s)
        else:
            if not val:
                missing.append(s)
    return missing


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
            row = match_by_registered_account(
                db, uuid.UUID(user_id), recipient_input
            )
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
    """수집된 슬롯을 기반으로 TTS 친화적 확인 메시지를 생성한다.

    Args:
        pending_action: 진행 중인 액션.
        collected_slots: 수집된 슬롯 dict.

    Returns:
        예: "엄마에게 오만 원 이체할까요?"
    """
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
    _DOW_LABELS = ["월", "화", "수", "목", "금", "토", "일"]
    if cycle == "monthly":
        parts.append("매월")
        if scheduled_day is not None:
            parts.append(f"{scheduled_day}일")
    elif cycle == "weekly":
        parts.append("매주")
        if scheduled_day is not None:
            try:
                parts.append(f"{_DOW_LABELS[int(scheduled_day)]}요일")
            except (IndexError, ValueError):
                parts.append(f"{scheduled_day}요일")
    if amount:
        try:
            parts.append(_amount_to_korean(int(amount)))
        except (ValueError, TypeError):
            parts.append(str(amount))

    summary = " ".join(parts)
    msg = f"{summary} {action_label}할까요?"
    if pending_action in ACTIONS_WITH_YES_NO_CONFIRM:
        msg += CONFIRM_YES_NO_SUFFIX
    return msg


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

    Phase 1 시그니처(tools: list) → CompiledStateGraph를 그대로 유지하므로
    voice/router.py(Issue #7) 호출부는 수정 없이 동작한다.

    Args:
        tools: LangChain @tool 데코레이터로 정의된 함수 목록.
               빈 리스트([])도 허용 — Phase 1 골격 초기화 목적.
               MOCK_TOOLS 또는 실제 tool을 전달한다.

    Returns:
        MemorySaver가 연결된 CompiledStateGraph.
        thread_id=user_id로 ainvoke() 호출 시 멀티턴 상태 유지.

    Raises:
        AgentError(code="AGENT_CONFIG_ERROR"): OPENAI_CHAT_API_KEY 미설정 오류.
        AgentError(code="AGENT_INIT_FAILED"): 그래프 컴파일 중 예기치 못한 오류.

    Usage:
        graph = build_graph(ALL_TOOLS)
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=text)], "user_id": uid},
            config={"configurable": {"thread_id": uid}},
        )
        response_text = result["messages"][-1].content

    Phase 2.5 내부 구현 (Issue #21):
        StateGraph + MemorySaver + VoiceState 기반.
        노드: intent_node → slot_fill_node / confirm_node / execute_node
    """
    # ── LLM 초기화 ──────────────────────────────────────────────────────────────
    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_CHAT_API_KEY,
            temperature=0,  # 뱅킹 도메인: 일관성 > 창의성
        )
        # extracted_slots는 자유형 dict이므로 OpenAI strict JSON schema 모드
        # (기본값)가 additionalProperties:false를 요구해 거부한다.
        # function_calling 방식은 이 제약이 없으므로 해당 method를 사용한다.
        llm_structured = llm.with_structured_output(
            IntentResult, method="function_calling"
        )
    except openai.OpenAIError as e:
        raise AgentError(
            code="AGENT_CONFIG_ERROR",
            message="AI 에이전트 설정 오류가 발생했습니다.",
            status_code=500,
        ) from e

    # ── tool registry: 액션 이름 → tool 함수 매핑 ───────────────────────────────
    # SLOT_SCHEMA에 정의된 액션과 tool 이름(함수명)으로 매핑한다.
    # 실제 tool 이름은 "mock_execute_transfer" 또는 "execute_transfer" 패턴을 따른다.
    tool_registry: dict[str, object] = {t.name: t for t in tools}

    # 액션 → tool 이름 매핑 (mock과 실제 tool 모두 지원)
    # tool 이름 패턴: "mock_{action}" 또는 "{action}_tool"
    def _find_tool_for_action(action: str) -> object | None:
        """액션 이름에 해당하는 tool을 registry에서 찾는다."""
        candidates = [
            action,
            f"mock_execute_{action}",
            f"mock_register_{action}",
            f"mock_get_{action}",
            f"execute_{action}",
            f"register_{action}",
            f"{action}_tool",
        ]
        for name in candidates:
            if name in tool_registry:
                return tool_registry[name]
        # 액션명으로 직접 탐색 (부분 일치)
        for name, tool_obj in tool_registry.items():
            if action in name:
                return tool_obj
        return None

    # ── 노드 정의 ────────────────────────────────────────────────────────────────

    def intent_node(state: VoiceState) -> dict:
        """LLM으로 인텐트를 파악하고 슬롯을 추출한다.

        처리 시나리오:
        1. 취소 발화("취소", "아니오") → 상태 초기화
        2. awaiting_confirmation=True + "네" + ASV 필요 → awaiting_asv_audio=True
        3. awaiting_confirmation=True + "네" + ASV 불필요 → execution_ready=True
        4. execution_ready=True → LLM 없이 즉시 통과 (execute_node로 라우팅)
        5. 새 인텐트 감지 → pending_action, navigate_to, 초기 슬롯 설정
        6. 슬롯 채우기 → collected_slots 업데이트
        7. 일반 챗봇 질의 → direct_response를 AIMessage로 추가
        """
        # ASV 인증 성공 직후: execution_ready=True이면 LLM 호출 없이 즉시 반환.
        # route_after_intent가 execute_node로 라우팅한다.
        if state.get("execution_ready"):
            logger.info(
                "[Graph →intent_node] execution_ready=True"
                " — LLM skip, pass-through to execute_node"
            )
            return {}

        if state.get("awaiting_memo_decision"):
            user_text = last_user_text(state.get("messages", []))
            note_action = (
                "add_auto_transfer_note"
                if state.get("last_order_id")
                else "add_note"
            )
            logger.info(
                "[Graph →intent_node] awaiting_memo_decision"
                " user_text=%s note_action=%s",
                user_text,
                note_action,
            )
            return build_memo_decision_update(user_text, note_action=note_action)

        if state.get("pending_action") == "add_note":
            user_text = last_user_text(state.get("messages", []))
            logger.info(
                "[Graph →intent_node] pending=add_note (memo recovery) user_text=%s",
                user_text,
            )
            return build_memo_decision_update(user_text)

        if state.get("awaiting_transfer_clarification"):
            user_text = last_user_text(state.get("messages", []))
            draft = _recipient_hint_from_state(
                state.get("draft_recipient") or "",
                state.get("collected_slots"),
            )
            logger.info(
                "[Graph →intent_node] awaiting_transfer_clarification"
                " user_text=%s draft=%s",
                user_text,
                draft,
            )
            return build_transfer_clarification_response(user_text, draft)

        logger.info(
            "[Graph →intent_node] pending=%s slots=%s"
            " await_confirm=%s await_asv=%s await_memo=%s exec_ready=%s",
            state.get("pending_action"),
            state.get("collected_slots", {}),
            state.get("awaiting_confirmation", False),
            state.get("awaiting_asv_audio", False),
            state.get("awaiting_memo_decision", False),
            state.get("execution_ready", False),
        )

        user_text = last_user_text(state.get("messages", []))
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
            logger.info(
                "[Graph →intent_node] transfer_clarification offer (pre-LLM) text=%s",
                user_text,
            )
            return build_transfer_clarification_offer(user_text)

        # 현재 상태 컨텍스트를 시스템 프롬프트에 추가
        context_lines = [
            SYSTEM_PROMPT,
            "",
            "=== 현재 대화 상태 ===",
        ]
        pending = state.get("pending_action")
        slots = state.get("collected_slots", {})

        if pending:
            missing = _missing_slots(pending, slots)
            context_lines.append(f"진행 중인 액션: {pending}")
            context_lines.append(
                f"수집된 슬롯: {json.dumps(slots, ensure_ascii=False)}"
            )
            context_lines.append(f"누락된 슬롯: {missing}")
            if missing:
                context_lines.append(
                    f"★ 슬롯 채우기 진행 중 — intent는 반드시 null로 설정하고,"
                    f" 누락 슬롯 {missing}의 값만 extracted_slots에 포함할 것."
                    " 이미 수집된 슬롯은 extracted_slots에 절대 포함하지 말 것."
                    " 사용자 발화가 새 인텐트처럼 보여도 절대 intent를 설정하지 말 것."
                )

        if state.get("awaiting_confirmation"):
            context_lines.append(
                "★ 대기 상태: 사용자 확인('네'/'아니오') 대기 중."
                " '네', '응', '맞아', '그렇게 해줘' → user_confirmed=true 반드시 설정."
                " '취소', '됐어', '하지 마' → user_cancelled=true 반드시 설정."
                " '아니' 단독 또는 '아니 + [새 값]' 패턴은 슬롯 수정으로 처리:"
                " user_cancelled=false 유지하고 extracted_slots에 바꿀 슬롯만 설정."
                " 예: '아니 6만원으로'→{\"amount\":60000},"
                " '아니 화요일로'→{\"scheduled_day\":1},"
                " '아니 10일로'→{\"scheduled_day\":10},"
                " '아니 월요일마다'→{\"cycle\":\"weekly\",\"scheduled_day\":0}."
                " 수정할 슬롯이 불명확하면 direct_response에 무엇을 바꿀지 질문할 것."
            )

        if state.get("awaiting_memo_decision"):
            context_lines.append(
                "대기 상태: 이체 완료 후 메모 제안에 대한 응답 대기 중"
                " (카테고리 말하기 또는 건너뛰기)"
            )

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
            "- intent: 진행 중인 액션이 없을 때만 설정."
            " 진행 중인 액션이 있으면 반드시 null.",
            "  transfer    : 일회성 이체 ('이체해줘', '보내줘', '송금해줘',"
            " '송금하고 싶어', '이체하고 싶어', '돈 보내고 싶어')",
            "  ★ 이체·송금 의도가 보이면 슬롯 없어도 반드시 intent=transfer.",
            "  auto_transfer: 정기·반복 이체 ("
            "'자동이체', '자동 송금', '정기 이체', '정기 송금',"
            " '매달', '매월', '한달에 한번', '한달에 한번씩', '월 1회', '월마다',"
            " '매주', '주마다', '일주일에 한번', '일주일마다', '주 1회',"
            " '정기적으로', '주기적으로', '반복해서', '계속', '꾸준히',"
            " '자동으로 보내줘', '고정으로 보내줘', 'N일마다',"
            " '격주', '격월')",
            "  balance     : 잔액·거래내역 조회 ('잔액 얼마야', '내역 보여줘')",
            "  home        : 홈 화면 이동 ('홈 화면', '처음으로', '홈으로 가줘')",
            "  ★ '매달', '매주', '자동이체', '한달에', '주마다', '매월', '정기',"
            " '반복', '주기', '계속', '꾸준히', '고정' 키워드가 있으면 반드시 auto_transfer.",
            "- extracted_slots: 발화에서 파악한 슬롯 값 (없으면 {})."
            " 금액 슬롯 키는 'amount', 값은 원화 정수 문자열"
            " (예: '3만원'→'30000', '오만원'→'50000')."
            " 수신자 슬롯 키는 'recipient', 값은 발화에서 언급한"
            " 이름·별명·전화번호 그대로"
            " (예: '엄마에게'→recipient='엄마', '친구한테'→recipient='친구',"
            " '010 1234 5678로'→recipient='010 1234 5678').",
            "- cycle 슬롯: 반드시 'monthly' 또는 'weekly' 영문으로 설정"
            " ('매월'·'한달에한번'→'monthly',"
            " '매주'·'일주일에한번'·'7일마다'→'weekly')."
            " ★ '7일마다', '일주일마다','주마다','매주','일주일마다 한번씩' 등은 cycle=weekly로만 설정하고"
            " scheduled_day는 설정하지 말 것 (요일 미명시).",
            "- scheduled_day: 사용자가 날짜·요일을 명시한 경우에만 추출할 것."
            " '한달에 한번', '매월', '매주' 등 주기만 말하고"
            " 날짜·요일을 언급하지 않으면 scheduled_day를 절대 설정하지 말 것."
            " monthly일 때 날짜 정수(1-31). '15일'→15, '말일'→31."
            " ★ 자동이체에서 'N월마다'는 달(月)이 아닌 날짜로 해석:"
            " '10월마다'→scheduled_day=10, '5월마다'→scheduled_day=5."
            " weekly일 때도 scheduled_day에 요일 정수(0=월,1=화,2=수,3=목,4=금,5=토,6=일)를 저장."
            " '월요일'→scheduled_day=0, '수요일'→scheduled_day=2, '금요일'→scheduled_day=4.",
            "  bank_name: 은행명 (예: '우리은행 1101234567890'→bank_name='우리은행',"
            " recipient='1101234567890').",
            "- user_confirmed: '네', '맞아요', '그렇게 해줘' 등 확인 발화 시 true",
            "- user_cancelled: '취소', '아니오', '됐어', '하지 마' 등 취소 발화 시 true",
            "- direct_response: 비금융 챗봇 답변(영업시간, 상품 안내 등)에만 사용.",
            "  ★ intent가 설정된 경우 반드시 빈 문자열('')로 설정할 것.",
            "  ★ 누락 슬롯 질문('누구에게?', '얼마?')을 절대 여기에 쓰지 말 것."
            " 슬롯 수집은 시스템이 자동으로 처리한다.",
            "  ★ 전화·계좌만 말하고 이체 의도가 없으면 direct_response는 비우고"
            " 사용자 발화를 그대로 반복하지 말 것 (송금 여부는 시스템이 질문한다).",
            "- TTS 출력: 마크다운 없이 자연스러운 한국어 구어체만 사용",
        ]

        system_content = "\n".join(context_lines)

        # 대화 이력 메시지 구성
        chat_messages: list = [{"role": "system", "content": system_content}]
        for msg in state.get("messages", []):
            if hasattr(msg, "type"):
                role = "user" if msg.type == "human" else "assistant"
                chat_messages.append({"role": role, "content": msg.content})

        # LLM 호출 (structured output)
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
                    AIMessage(
                        content="일시적인 오류가 발생했습니다. 다시 말씀해 주세요."
                    )
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
                "navigate_to": "home",
                "execution_ready": False,
                "recipient_validated": False,
                "last_tx_id": None,
                "last_order_id": None,
                "awaiting_memo_decision": False,
                "awaiting_transfer_clarification": False,
                "draft_recipient": None,
                "messages": [
                    *clear_conversation_messages(),
                    AIMessage(
                        content=result.direct_response
                        or "취소되었습니다. 홈 화면으로 이동합니다."
                    ),
                ],
            }

        # ── 확인 수신 처리 ─────────────────────────────────────────────────────
        if state.get("awaiting_confirmation") and result.user_confirmed:
            action = state.get("pending_action", "")
            if action in ASV_REQUIRED_ACTIONS:
                # ASV 음성 인증 필요 → 다음 오디오를 ASV 검증으로 처리
                updates = {
                    "awaiting_confirmation": False,
                    "awaiting_asv_audio": True,
                    "navigate_to": SCREEN_MAP.get(action),
                    "messages": [AIMessage(content="목소리로 인증해 주세요.")],
                }
            else:
                # ASV 불필요 → execute_node로 직행
                updates = {
                    "awaiting_confirmation": False,
                    "execution_ready": True,
                }
            return updates

        # ── 확인 단계에서 슬롯 수정 ────────────────────────────────────────────────
        # "6만원으로 바꿔줘" 등 슬롯 수정 발화 → awaiting_confirmation 해제 후 재확인
        if state.get("awaiting_confirmation") and result.extracted_slots:
            existing = dict(state.get("collected_slots", {}))
            existing.update(result.extracted_slots)  # 기존 슬롯 포함 전체 교체 허용
            logger.info(
                "[Graph →intent_node] 확인 단계 슬롯 수정: %s", result.extracted_slots
            )
            return {
                "collected_slots": existing,
                "awaiting_confirmation": False,
                "recipient_validated": (
                    False
                    if "recipient" in result.extracted_slots
                    else state.get("recipient_validated", False)
                ),
            }

        # ── 확인 단계에서 응답 불명확 ────────────────────────────────────────────
        # extracted_slots도 비어있고 confirmed/cancelled도 False인 경우
        # → TTS로 "네 또는 아니오" 재안내
        if state.get("awaiting_confirmation") and not result.direct_response:
            return {
                "messages": [
                    AIMessage(
                        content="네 또는 아니오로 말씀해 주세요."
                        " 변경하실 내용이 있으면 말씀해 주시면 반영해 드립니다."
                    )
                ]
            }

        # ── 홈 이동 처리 ─────────────────────────────────────────────────────────
        # 진행 중인 모든 액션 상태를 초기화하고 홈으로 이동
        if result.intent == "home":
            return {
                "pending_action": None,
                "collected_slots": {},
                "awaiting_confirmation": False,
                "awaiting_asv_audio": False,
                "execution_ready": False,
                "recipient_validated": False,
                "asv_retry_count": 0,
                "last_tx_id": None,
                "awaiting_memo_decision": False,
                "awaiting_transfer_clarification": False,
                "draft_recipient": None,
                "navigate_to": "home",
                "messages": [
                    *clear_conversation_messages(),
                    AIMessage(content="홈 화면으로 이동합니다."),
                ],
            }

        user_text = last_user_text(state.get("messages", []))
        restart_transfer = _should_restart_transfer_flow(
            result.intent, pending, user_text, state
        )

        # ── 새 인텐트 감지 ──────────────────────────────────────────────────────
        # 확인·ASV 대기 중에는 인텐트 감지를 무시 (슬롯 초기화 방지)
        # 다른 인텐트이거나 transfer 재시작 케이스일 때 슬롯·상태 초기화
        if (
            result.intent
            and result.intent in VALID_INTENTS
            and not state.get("awaiting_confirmation")
            and not state.get("awaiting_asv_audio")
            and (result.intent != pending or restart_transfer)
        ):
            updates = {
                "pending_action": result.intent,
                "navigate_to": SCREEN_MAP.get(result.intent),
                "collected_slots": dict(result.extracted_slots),
                "recipient_validated": False,
                "awaiting_confirmation": False,
                "awaiting_asv_audio": False,
                "execution_ready": False,
                "asv_retry_count": 0,
                "awaiting_memo_decision": False,
                "awaiting_transfer_clarification": False,
                "draft_recipient": None,
                "last_tx_id": None if result.intent == "transfer" else state.get("last_tx_id"),
            }
            if result.intent == "transfer":
                updates["messages"] = [
                    *clear_conversation_messages(),
                    HumanMessage(content=user_text),
                ]
            # 화면 전환 전용 인텐트: 화면이 자체 TTS를 처리하므로 간단한 안내만 추가
            if result.intent in SCREEN_ONLY_INTENTS:
                screen_name = SCREEN_MAP.get(result.intent, result.intent)
                updates["messages"] = [
                    AIMessage(content=f"{screen_name} 화면으로 이동합니다.")
                ]

        # ── 슬롯 보충 ──────────────────────────────────────────────────────────
        elif result.extracted_slots and pending:
            existing = dict(state.get("collected_slots", {}))
            missing_now = _missing_slots(pending, existing)
            for key, val in result.extracted_slots.items():
                # 이미 채워진 슬롯은 덮어쓰지 않음 (LLM 오파싱 방어)
                if key in missing_now or existing.get(key) is None:
                    existing[key] = val
            updates["collected_slots"] = existing
            updates["navigate_to"] = None  # 슬롯 채우기 중 화면 이동 없음
            if pending == "add_note" and existing.get("memo"):
                updates["execution_ready"] = True

        # ── 챗봇 직접 응답 (인텐트 없음) ───────────────────────────────────────
        pending_after = updates.get("pending_action") or state.get("pending_action")
        if should_offer_transfer_clarification(
            user_text,
            pending_action=pending_after,
            awaiting_memo_decision=state.get("awaiting_memo_decision", False),
            awaiting_transfer_clarification=state.get(
                "awaiting_transfer_clarification", False
            ),
            awaiting_confirmation=state.get("awaiting_confirmation", False),
            awaiting_asv_audio=state.get("awaiting_asv_audio", False),
        ):
            updates = {**updates, **build_transfer_clarification_offer(user_text)}
        elif result.direct_response:
            updates["messages"] = [AIMessage(content=result.direct_response)]
        elif (
            not updates.get("messages")
            and not pending_after
            and not is_plain_transfer_start(user_text)
        ):
            updates["messages"] = [AIMessage(content=_DEFAULT_TTS_FALLBACK)]

        return updates

    def slot_fill_node(state: VoiceState) -> dict:
        """누락된 첫 번째 슬롯에 대한 질문을 TTS 응답으로 추가한다."""
        pending = state.get("pending_action", "")
        slots = state.get("collected_slots", {})
        missing = _missing_slots(pending, slots)
        logger.info("[Graph →slot_fill_node] pending=%s missing=%s", pending, missing)

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

        return {
            # navigate_to는 intent_node가 이미 설정/초기화한다.
            # - 새 intent 첫 감지 턴: intent_node가 SCREEN_MAP 값을 설정 → 보존
            # - 슬롯 채우기 진행 턴: intent_node의 elif 분기가 None으로 초기화 → 보존
            "messages": [AIMessage(content=question)],
        }

    def confirm_node(state: VoiceState) -> dict:
        """슬롯이 완전히 수집되면 확인 메시지를 생성하고 awaiting_confirmation을 설정한다."""
        pending = state.get("pending_action", "")
        slots = state.get("collected_slots", {})
        logger.info("[Graph →confirm_node] pending=%s slots=%s", pending, slots)
        confirm_msg = _format_confirm_message(pending, slots)

        return {
            "awaiting_confirmation": True,
            "navigate_to": SCREEN_MAP.get(pending),
            "messages": [AIMessage(content=confirm_msg)],
        }

    def resolve_node(state: VoiceState) -> dict:
        """recipient 슬롯이 채워진 즉시 수취인 존재 여부를 검증한다.

        성공 시 recipient_validated=True, 실패 시 recipient 슬롯 초기화 후 재수집 유도.
        """
        slots = dict(state.get("collected_slots", {}))
        recipient_input = str(slots.get("recipient", ""))
        bank_name = slots.get("bank_name")
        user_id = state.get("user_id", "")
        kind = classify_recipient_input(recipient_input) if recipient_input else "name"

        logger.info(
            "[Graph →resolve_node] recipient=%s bank=%s kind=%s user_id=%s",
            recipient_input,
            bank_name,
            kind,
            user_id,
        )

        try:
            resolved = find_recipient_by_voice(
                user_id,
                recipient_input,
                bank_name=str(bank_name) if bank_name else None,
            )
        except Exception as e:
            logger.error("resolve_node 수취인 조회 실패: %s", e)
            resolved = None

        if resolved is not None:
            _enrich_slots_from_resolved(slots, resolved, recipient_input, user_id)
            return {
                "collected_slots": slots,
                "recipient_validated": True,
            }

        if kind == "account" and not bank_name:
            return {
                "collected_slots": slots,
                "recipient_validated": False,
            }

        # 전화·계좌 힌트는 슬롯을 비우지 않는다 (금액만 추가 수집 또는 재시도).
        if kind in ("phone", "account"):
            return {
                "collected_slots": slots,
                "recipient_validated": False,
                "navigate_to": None,
                "messages": [
                    AIMessage(
                        content=(
                            f"'{recipient_input}'은(는) 등록된 수취인이 아닙니다."
                            " 수신인 이름이나 별명, 계좌번호를 다시 말씀해 주세요."
                        )
                    )
                ],
            }

        slots["recipient"] = None
        return {
            "collected_slots": slots,
            "recipient_validated": False,
            "navigate_to": SCREEN_MAP.get("transfer"),
            "messages": [
                AIMessage(
                    content=(
                        f"'{recipient_input}'은(는) 등록되지 않은 수취인입니다. "
                        "누구에게 보낼까요?"
                    )
                )
            ],
        }

    def route_after_resolve(state: VoiceState) -> str:
        """resolve_node 결과에 따라 다음 노드를 결정한다."""
        slots = state.get("collected_slots", {})
        pending = state.get("pending_action", "")
        missing = _missing_slots(pending, slots)

        if not slots.get("recipient"):
            # 수취인 미등록 → resolve_node의 실패 메시지를 TTS로 전달하고 END
            # slot_fill_node로 넘기면 "누구에게 보낼까요?"가 실패 메시지를 덮어씀
            logger.info(
                "[Graph route] resolve_node → END (recipient not found)"
            )
            return END

        if not state.get("recipient_validated"):
            # 조회 실패: 금액만 빠진 상태로 slot_fill 가면 안 됨 (미검증 수취인).
            if missing == ["amount"]:
                logger.info(
                    "[Graph route] resolve_node → END (unvalidated, lookup failed)"
                )
                return END
            if missing:
                logger.info(
                    "[Graph route] resolve_node → slot_fill_node (missing=%s)",
                    missing,
                )
                return "slot_fill_node"
            logger.info("[Graph route] resolve_node → END (unvalidated)")
            return END

        if missing:
            logger.info(
                "[Graph route] resolve_node → slot_fill_node (missing=%s)", missing
            )
            return "slot_fill_node"
        logger.info("[Graph route] resolve_node → confirm_node")
        return "confirm_node"

    def execute_node(state: VoiceState) -> dict:
        """수집된 슬롯으로 tool을 직접 호출하고 결과를 TTS 응답으로 추가한다.

        화면에 서비스 실행을 위임하지 않는다.
        tool(mock 또는 실제)을 직접 invoke()한다.
        """
        pending = state.get("pending_action", "")
        slots = dict(state.get("collected_slots", {}))
        logger.info("[Graph →execute_node] pending=%s slots=%s", pending, slots)

        # tool 탐색
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
                "awaiting_memo_decision": False,
                "navigate_to": "home",
                "messages": [
                    AIMessage(
                        content=(
                            "해당 기능을 아직 사용할 수 없습니다."
                            " 홈 화면으로 이동합니다."
                        )
                    )
                ],
            }
        else:
            from app.shared.agent.tools.transfer import run_execute_transfer

            invoke_args = {"user_id": state.get("user_id", ""), **slots}
            new_last_tx_id: str | None = state.get("last_tx_id")
            new_last_order_id: str | None = state.get("last_order_id")
            completed_slots: dict = {}
            note_consumed = False
            awaiting_memo_next = False
            response_text = ""

            try:
                if pending == "transfer" and tool_obj.name == "execute_transfer":
                    response_text, tx_id = run_execute_transfer(
                        user_id=invoke_args["user_id"],
                        recipient=str(invoke_args.get("recipient", "")),
                        amount=int(invoke_args.get("amount", 0)),
                        collected_slots=slots,
                    )
                    if tx_id:
                        new_last_tx_id = tx_id
                        awaiting_memo_next = True
                        response_text = response_text + MEMO_OFFER_SUFFIX
                        # 영수증은 프론트 prevSlots로 처리; 세션 슬롯은 비움
                        completed_slots = {}
                elif pending == "transfer":
                    response_text = tool_obj.invoke(invoke_args)
                elif pending == "auto_transfer":
                    result_raw = tool_obj.invoke(invoke_args)
                    try:
                        result_data = json.loads(result_raw)
                    except Exception:
                        result_data = {}
                    response_text = result_data.get(
                        "tts_text", "자동이체 등록 중 오류가 발생했습니다."
                    )
                    if result_data.get("success"):
                        order_id = result_data.get("order_id")
                        if order_id:
                            new_last_order_id = order_id
                            awaiting_memo_next = True
                            response_text = response_text + MEMO_OFFER_SUFFIX
                        completed_slots = {}
                elif pending == "add_note":
                    tx_id = slots.get("tx_id") or state.get("last_tx_id")
                    if not tx_id:
                        response_text = (
                            "메모를 추가할 이체 내역을 찾을 수 없습니다."
                            " 이체를 먼저 완료해 주세요."
                        )
                    else:
                        response_text = tool_obj.invoke(
                            {
                                "user_id": invoke_args["user_id"],
                                "memo": str(invoke_args.get("memo", "")),
                                "tx_id": str(tx_id),
                            }
                        )
                        if "추가되었습니다" in response_text:
                            note_consumed = True
                elif pending == "add_auto_transfer_note":
                    order_id = slots.get("order_id") or state.get("last_order_id")
                    if not order_id:
                        response_text = (
                            "메모를 추가할 자동이체 내역을 찾을 수 없습니다."
                            " 자동이체 등록을 먼저 완료해 주세요."
                        )
                    else:
                        response_text = tool_obj.invoke(
                            {
                                "user_id": invoke_args["user_id"],
                                "memo": str(invoke_args.get("memo", "")),
                                "order_id": str(order_id),
                            }
                        )
                        if "추가되었습니다" in response_text:
                            note_consumed = True
                else:
                    response_text = tool_obj.invoke(invoke_args)
            except Exception as e:
                logger.error("execute_node tool 호출 실패 (%s): %s", pending, e)
                response_text = (
                    "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                )
                new_last_tx_id = state.get("last_tx_id")
                new_last_order_id = state.get("last_order_id")
                completed_slots = {}

        updates: dict = {
            "pending_action": None,
            "collected_slots": completed_slots,
            "awaiting_confirmation": False,
            "awaiting_asv_audio": False,
            "awaiting_memo_decision": awaiting_memo_next,
            "execution_ready": False,
            "recipient_validated": False,
            "messages": [AIMessage(content=response_text)],
            "last_tx_id": None if note_consumed else new_last_tx_id,
            "last_order_id": None if note_consumed else new_last_order_id,
        }
        if note_consumed:
            updates["awaiting_memo_decision"] = False
            updates["navigate_to"] = "home"
            updates["messages"] = [
                *clear_conversation_messages(),
                AIMessage(content=response_text),
            ]
        # transfer/auto_transfer 등 완료 화면이 있는 액션만 navigate_to 덮어씀.
        if pending in COMPLETE_SCREEN_MAP:
            updates["navigate_to"] = COMPLETE_SCREEN_MAP[pending]
        return updates

    # ── 조건부 라우팅 ─────────────────────────────────────────────────────────────

    def route_after_intent(state: VoiceState) -> str:
        """intent_node 처리 후 다음 노드를 결정한다."""
        # ASV 대기 중 → END (다음 요청은 router.py가 ASV 분기 처리)
        if state.get("awaiting_asv_audio"):
            logger.info("[Graph route] intent_node → END (awaiting_asv_audio)")
            return END

        # 메모 제안 응답 대기 → END (다음 발화로 intent_node에서 처리)
        if state.get("awaiting_memo_decision"):
            logger.info("[Graph route] intent_node → END (awaiting_memo_decision)")
            return END

        if state.get("awaiting_transfer_clarification"):
            logger.info(
                "[Graph route] intent_node → END (awaiting_transfer_clarification)"
            )
            return END

        # 확인 완료 + 즉시 실행 가능 → execute_node
        if state.get("execution_ready"):
            logger.info("[Graph route] intent_node → execute_node (execution_ready)")
            return "execute_node"

        pending = state.get("pending_action")
        if not pending:
            # 인텐트 없음 → 챗봇 직답 (메시지는 이미 intent_node에서 추가됨)
            logger.info("[Graph route] intent_node → END (no pending_action)")
            return END

        slots = state.get("collected_slots", {})

        # recipient 슬롯이 채워졌지만 아직 검증하지 않았으면 즉시 resolve_node로
        if (
            pending in RECIPIENT_REQUIRED_ACTIONS
            and slots.get("recipient")
            and not state.get("recipient_validated")
        ):
            logger.info(
                "[Graph route] intent_node → resolve_node (recipient unvalidated)"
            )
            return "resolve_node"

        if pending == "add_note":
            logger.info(
                "[Graph route] intent_node → END (add_note — memo_decision only)"
            )
            return END

        missing = _missing_slots(pending, slots)

        if missing:
            logger.info(
                "[Graph route] intent_node → slot_fill_node (missing=%s)", missing
            )
            return "slot_fill_node"

        # 화면 전환 전용 인텐트 (event 등) → 화면이 자체 데이터·TTS 처리
        if pending in SCREEN_ONLY_INTENTS:
            logger.info(
                "[Graph route] intent_node → END (screen-only=%s)",
                pending,
            )
            return END

        # 슬롯 없는 단순 조회 액션 (balance, history) → 확인 없이 즉시 실행
        if pending not in SLOT_SCHEMA:
            logger.info("[Graph route] intent_node → execute_node (no slots required)")
            return "execute_node"

        if not state.get("awaiting_confirmation"):
            # 슬롯 완전 수집, 아직 확인 안 받음 → 확인 요청
            logger.info("[Graph route] intent_node → confirm_node (all slots filled)")
            return "confirm_node"

        # awaiting_confirmation=True → 사용자 응답 대기 중 → END
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
