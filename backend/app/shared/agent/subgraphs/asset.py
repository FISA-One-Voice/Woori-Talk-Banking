"""AssetAgent 서브그래프 (Dev-C).

잔액 조회, 거래 내역 조회, 지출 분석을 처리합니다.
슬롯 수집 없음 · 확인 없음 · ASV 없음 — 단순 조회 전용.

입력 계약 (ASSET_READ): messages, user_id, analytics_period, agent_domain
출력 계약:              messages, navigate_to, analytics_period, collected_slots
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.metrics import agent_node_executions_total, agent_tool_duration_seconds
from app.shared.agent.ROUTING_CONSTANTS import ASSET_NAVIGATE_VALUES
from app.shared.agent.prompts import ASSET_SYSTEM_PROMPT
from app.shared.agent.state import VoiceState

KST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)

_NAVIGATE_MAP: dict[str, str] = {
    "balance":          "asset",
    "history":          "asset/history",
    "category":         "asset/history",
    "top_category":     "asset/history",
    "transaction_list": "asset/history",
    "spending_report":  "report",
    "compare":          "asset/compare",
}


class AssetIntent(BaseModel):
    """자산 조회 인텐트 슬롯 스키마."""

    tool: str = Field(
        description=(
            "balance|history|category|top_category"
            "|transaction_list|spending_report|compare"
        )
    )
    period: str = Field(
        default="이번달",
        description="사용자가 말한 기간 그대로. 기본값도 항상 반환, 생략 금지",
    )
    filter_type: str | None = Field(default=None, description="expense|income|null")
    category: str | None = Field(default=None)
    compare_period: str = Field(default="지난달")
    date_range: str | None = Field(
        default=None, description="YYYY-MM-DD, 특정 날짜 조회 시"
    )
    direct_response: str | None = Field(
        default=None, description="history 기간 되묻기 TTS 텍스트"
    )


def _chat_messages_for_llm(state: VoiceState, system_content: str) -> list[dict]:
    """LangChain 메시지 이력을 OpenAI chat 메시지 형식으로 변환한다."""
    chat_messages: list[dict] = [{"role": "system", "content": system_content}]
    for message in state.get("messages", []):
        if hasattr(message, "type"):
            role = "user" if message.type == "human" else "assistant"
            chat_messages.append({"role": role, "content": message.content})
    return chat_messages


def build_asset_graph(tools: list):
    """AssetAgent 서브그래프를 빌드한다. with_structured_output 패턴 사용."""
    tool_map = {t.name.removeprefix("query_"): t for t in tools}
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_CHAT_API_KEY,
        temperature=0,
    )
    llm_structured = llm.with_structured_output(AssetIntent)

    async def _asset_graph(state: VoiceState) -> dict:
        user_id = state["user_id"]
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        system_content = ASSET_SYSTEM_PROMPT.format(user_id=user_id, today=today_str)
        chat_msgs = _chat_messages_for_llm(state, system_content)

        intent: AssetIntent = llm_structured.invoke(chat_msgs)
        logger.info(
            "[Asset →intent] tool=%s period=%s filter_type=%s direct_response=%s",
            intent.tool, intent.period, intent.filter_type, bool(intent.direct_response),
        )

        # history 기간 되묻기
        if intent.direct_response:
            return {
                "messages": [AIMessage(content=intent.direct_response)],
                "navigate_to": None,
                "analytics_period": None,
                "collected_slots": state.get("collected_slots") or {},
            }

        # 도구 호출 인자 구성 — period는 항상 명시적으로 전달
        invoke_args: dict = {"user_id": user_id}

        if intent.tool == "balance":
            pass  # user_id만 필요
        elif intent.tool == "history":
            invoke_args["period"] = intent.period
            if intent.filter_type:
                invoke_args["filter_type"] = intent.filter_type
        elif intent.tool == "category":
            invoke_args["period"] = intent.period
            if intent.category:
                invoke_args["category"] = intent.category
        elif intent.tool == "top_category":
            invoke_args["period"] = intent.period
        elif intent.tool == "transaction_list":
            invoke_args["period"] = intent.period
            if intent.date_range:
                invoke_args["date_range"] = intent.date_range
        elif intent.tool == "spending_report":
            invoke_args["period"] = intent.period
        elif intent.tool == "compare":
            invoke_args["period"] = intent.period
            invoke_args["compare_period"] = intent.compare_period
            if intent.category:
                invoke_args["category"] = intent.category

        if intent.tool not in tool_map:
            logger.error("AssetAgent 알 수 없는 tool: %s", intent.tool)
            return {
                "messages": [AIMessage(content="죄송합니다. 요청을 처리할 수 없습니다.")],
                "navigate_to": "asset",
                "analytics_period": None,
                "collected_slots": {},
            }

        _tool_start = time.monotonic()
        _tool_success = True
        logger.info(
            "agent_tool_call_start",
            extra={"event": "agent_tool_call_start", "tool": intent.tool, "action": intent.tool, "user_id": user_id},
        )
        try:
            tts_text: str = tool_map[intent.tool].invoke(invoke_args)
        except Exception:
            _tool_success = False
            raise
        finally:
            _duration_ms = int((time.monotonic() - _tool_start) * 1000)
            logger.info(
                "agent_tool_call_end",
                extra={
                    "event": "agent_tool_call_end",
                    "tool": intent.tool,
                    "action": intent.tool,
                    "user_id": user_id,
                    "duration_ms": _duration_ms,
                    "success": _tool_success,
                },
            )
            agent_node_executions_total.labels(node=intent.tool).inc()
            agent_tool_duration_seconds.labels(node=intent.tool).observe(_duration_ms / 1000)

        # navigate_to 결정
        navigate_to = _NAVIGATE_MAP.get(intent.tool, "asset")
        valid = navigate_to in ASSET_NAVIGATE_VALUES or navigate_to == "asset/compare"
        if not valid:
            logger.error("AssetAgent navigate_to 계약 위반: %s", navigate_to)
            navigate_to = "asset"

        # collected_slots — period 항상 포함
        slots: dict = {"action": intent.tool, "period": intent.period}
        if intent.filter_type:
            slots["filter_type"] = intent.filter_type
        if intent.category:
            slots["category"] = intent.category
        if intent.tool == "compare":
            slots["compare_period"] = intent.compare_period
        if intent.date_range:
            slots["date_range"] = intent.date_range

        return {
            "messages": [AIMessage(content=tts_text)],
            "navigate_to": navigate_to,
            "analytics_period": intent.period if intent.tool != "balance" else None,
            "collected_slots": slots,
            "tool_execution_ms": _duration_ms,
        }

    return _asset_graph
