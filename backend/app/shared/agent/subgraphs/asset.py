"""AssetAgent 서브그래프 (Dev-C).

잔액 조회, 거래 내역 조회, 지출 분석을 처리합니다.
슬롯 수집 없음 · 확인 없음 · ASV 없음 — 단순 조회 전용.

입력 계약 (ASSET_READ): messages, user_id, analytics_period, agent_domain
출력 계약:              messages, navigate_to, analytics_period, collected_slots
"""

import logging
from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
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
    "compare":          "asset/compare",  # [Dev-A에게] ROUTING_CONSTANTS.ASSET_NAVIGATE_VALUES에 "asset/compare" 추가 요청
}


def _extract_tool_info(messages: list) -> tuple[str | None, dict]:
    """result["messages"] 역순 순회해 첫 tool_call 정보 반환."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tc = msg.tool_calls[0]
            return tc["name"], tc.get("args", {})
    return None, {}


def build_asset_graph(tools: list):
    """AssetAgent 서브그래프를 빌드한다. RAGAgent 패턴(create_react_agent) 사용."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_CHAT_API_KEY,
        temperature=0,
    )
    agent = create_react_agent(model=llm, tools=tools, state_schema=VoiceState)

    async def _asset_graph(state: VoiceState) -> dict:
        user_id = state["user_id"]

        # user_id를 시스템 프롬프트에 주입 — create_react_agent prompt는 정적이므로 여기서 prepend
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        system_msg = SystemMessage(content=ASSET_SYSTEM_PROMPT.format(user_id=user_id, today=today_str))
        result = await agent.ainvoke({
            **state,
            "messages": [system_msg, *state["messages"]],
        })

        # MemorySaver 오염 방지: SystemMessage는 반환 메시지에서 제거
        clean_msgs = [m for m in result["messages"] if not isinstance(m, SystemMessage)]

        tool_name, tool_args = _extract_tool_info(result["messages"])

        # navigate_to 결정
        action_key = tool_name.removeprefix("query_") if tool_name else None
        navigate_to = _NAVIGATE_MAP.get(action_key) if action_key else None
        if navigate_to not in ASSET_NAVIGATE_VALUES and navigate_to != "asset/compare":
            logger.error("AssetAgent navigate_to 계약 위반: %s", navigate_to)
            navigate_to = "asset"

        # collected_slots 구성
        slots: dict = {}
        if tool_name:
            slots["action"] = action_key
            period = tool_args.get("period")
            if period:                          slots["period"] = period
            if tool_args.get("compare_period"): slots["compare_period"] = tool_args["compare_period"]
            if tool_args.get("category"):       slots["category"] = tool_args["category"]
            if tool_args.get("filter_type"):    slots["filter_type"] = tool_args["filter_type"]
            if tool_args.get("date_range"):     slots["date_range"] = tool_args["date_range"]
        else:
            # 되묻기: 이전 collected_slots 유지 (다음 턴에서 action 기억)
            slots = state.get("collected_slots") or {}

        period = tool_args.get("period") if tool_args else None

        return {
            "messages": clean_msgs,
            "navigate_to": navigate_to,
            "analytics_period": period if tool_name and tool_name != "query_balance" else None,
            "collected_slots": slots,
        }

    return _asset_graph
