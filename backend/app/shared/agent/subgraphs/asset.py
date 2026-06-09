"""AssetAgent 서브그래프 (Dev-C).

잔액 조회, 거래 내역 조회, 지출 분석을 처리합니다.
슬롯 수집 없음 · 확인 없음 · ASV 없음 — 단순 조회 전용.

입력 계약 (ASSET_READ): messages, user_id, analytics_period, agent_domain
출력 계약:              messages, navigate_to, analytics_period, collected_slots
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.shared.agent.ROUTING_CONSTANTS import ASSET_NAVIGATE_VALUES
from app.shared.agent.state import VoiceState

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

_ASSET_SYSTEM_PROMPT = """\
당신은 자산 조회 전용 에이전트입니다.
현재 사용자 ID: {user_id}
모든 tool 호출 시 반드시 user_id="{user_id}"를 전달하세요.

[tool 선택 기준]
- query_balance          : 잔액 조회 ("잔액 얼마야", "통장 잔액")
- query_history          : 수입/지출 요약 ("이번달 지출 얼마야", "수입 얼마야")
- query_category         : 카테고리별 지출 ("식비 얼마야", "교통비 알려줘")
- query_top_category     : 최다 지출 카테고리 ("어디에 제일 많이 썼어")
- query_transaction_list : 거래 내역 목록 ("거래내역 보여줘", "최근 내역")
- query_spending_report  : 지출 분석 리포트 ("지출 분석", "소비 분석", "리포트")
- query_compare          : 두 기간 지출 비교 ("이번달 지난달 비교", "이번주 지난주 대비")

[기간 처리 규칙]
- query_history 요청인데 기간이 명시되지 않았으면:
  tool을 호출하지 말고 "어느 기간을 알려드릴까요?" 라고만 답하세요.
- 그 외 모든 tool은 기간이 없으면 "이번달"을 기본값으로 사용해 tool을 호출하세요.

[응답 규칙]
- tool 반환값을 그대로 사용자에게 전달하세요. 내용 추가·요약·수정 금지.
- 마크다운·이모지 사용 금지. 음성(TTS)으로 전달됩니다.
- 숫자는 한국어로 읽히도록 작성하세요. (예: "오십만 원")
"""


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
        system_msg = SystemMessage(content=_ASSET_SYSTEM_PROMPT.format(user_id=user_id))
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
