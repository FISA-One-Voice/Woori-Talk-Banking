"""AssetAgent 서브그래프 (Dev-C).

잔액 조회, 거래 내역 조회, 지출 분석을 처리합니다.
슬롯 수집 없음 · 확인 없음 · ASV 없음 — 단순 조회 전용.

입력 계약 (ASSET_READ): messages, user_id, analytics_period, agent_domain
출력 계약:              messages, navigate_to, analytics_period
"""

import json
import re

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.database import get_db
from app.core.exception import AppError
from app.features.asset.service import (
    query_balance_tts,
    query_category_tts,
    query_history_tts,
    query_top_category_tts,
    query_transaction_list_tts,
)
from app.shared.agent.ROUTING_CONSTANTS import ASSET_NAVIGATE_VALUES
from app.shared.agent.state import VoiceState
from app.shared.agent.tools.spending_analysis import get_monthly_spending_report

ASSET_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "balance", "history", "spending_analysis", "monthly_report",
})

_PERIOD_TO_DAYS: dict[str, int] = {
    "이번달": 30,
    "지난달": 60,
    "3개월": 90,
}

_NAVIGATE_MAP: dict[str, str] = {
    "balance": "asset",
    "history": "asset/history",
    "category": "asset/history",
    "top_category": "asset/history",
    "transaction_list": "asset/history",
    "spending_analysis": "report",
}

_BALANCE_KEYWORDS = frozenset({"잔액", "얼마 있", "돈 얼마", "통장"})
_HISTORY_KEYWORDS = frozenset({"거래내역", "거래 내역", "내역", "소비 내역"})
_ANALYSIS_KEYWORDS = frozenset({"분석", "리포트", "소비 분석", "지출 분석"})

_QUERY_SYSTEM_PROMPT = """너는 자산 조회 전문 에이전트야.
사용자 발화를 보고 아래 중 하나를 결정해:

- balance: 잔액 조회 ("잔액 얼마야", "돈 얼마 있어", "통장 잔액")
- history: 수입/지출 요약 ("이번달 지출 얼마야", "수입 얼마야", "소비 얼마야")
- category: 특정 카테고리 지출 ("이번달 식비 얼마야", "교통비 알려줘")
- top_category: 가장 많이 쓴 카테고리 ("어디에 제일 많이 썼어")
- transaction_list: 거래 내역 목록 ("거래내역 보여줘", "최근 내역 알려줘")
- spending_analysis: 지출 분석 리포트 ("지출 분석", "소비 분석", "리포트")

다음 JSON만 반환해. 설명 없이:
{"action": "<balance|history|category|top_category|transaction_list|spending_analysis>", "period": "<이번달|지난달|최근7일|null>", "category": "<카테고리명|null>", "filter_type": "<income|expense|both|null>"}

period가 발화에 없으면 "이번달"로 기본값 사용.
category는 "식비", "교통", "쇼핑", "의료비", "문화생활" 중 언급된 것만 채워.
filter_type은 action=history일 때만: income=수입만, expense=지출만, both=둘다."""


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_CHAT_API_KEY,
        temperature=0,
    )


def _last_user_text(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else ""
    return ""


def _parse_llm_action(raw: str) -> dict[str, str | None]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"action": "balance", "period": "이번달", "category": None, "filter_type": None}


def _fast_classify(user_text: str) -> str | None:
    """키워드 패스트패스 — LLM 없이 action 결정. 불명확하면 None 반환."""
    if any(kw in user_text for kw in _BALANCE_KEYWORDS):
        return "balance"
    if any(kw in user_text for kw in _ANALYSIS_KEYWORDS):
        return "spending_analysis"
    if any(kw in user_text for kw in _HISTORY_KEYWORDS):
        return "history"
    return None


async def asset_node(state: VoiceState) -> dict:
    """발화를 분류하고 해당 tool을 실행해 응답을 반환합니다.

    query + execute를 단일 노드로 처리해 VoiceState 임시 필드 오염을 방지합니다.

    Args:
        state: VoiceState. messages, user_id, analytics_period을 읽습니다.

    Returns:
        messages, navigate_to, analytics_period delta dict.
    """
    user_text = _last_user_text(state["messages"])
    user_id = state["user_id"]
    prev_period = state.get("analytics_period") or "이번달"

    # ── 1. action 결정 (패스트패스 우선) ────────────────────────────────────────
    fast = _fast_classify(user_text)
    if fast == "balance":
        action, period, category, filter_type = "balance", None, None, None
    elif fast is not None:
        action, period, category, filter_type = fast, prev_period, None, None
    else:
        llm = _get_llm()
        response = await llm.ainvoke([
            {"role": "system", "content": _QUERY_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ])
        parsed = _parse_llm_action(response.content)
        action = parsed.get("action") or "balance"
        period = parsed.get("period") or prev_period
        category = parsed.get("category")
        filter_type = parsed.get("filter_type")

    # ── 2. service TTS 실행 ───────────────────────────────────────────────────────
    db = next(get_db())
    try:
        if action == "balance":
            tts_result = query_balance_tts(db, user_id)
        elif action == "spending_analysis":
            tts_result = get_monthly_spending_report.invoke(
                {"user_id": user_id, "period": period or "이번달"}
            )
        elif action == "category":
            tts_result = query_category_tts(db, user_id, period, category)
        elif action == "top_category":
            tts_result = query_top_category_tts(db, user_id, period)
        elif action == "transaction_list":
            tts_result = query_transaction_list_tts(db, user_id, period, None)
        else:  # history
            tts_result = query_history_tts(db, user_id, period, None, filter_type)
    except AppError as e:
        tts_result = e.user_message or e.message
    finally:
        db.close()

    # ── 3. navigate_to 결정 ───────────────────────────────────────────────────────
    navigate_to = _NAVIGATE_MAP.get(action, "asset")
    if navigate_to not in ASSET_NAVIGATE_VALUES:
        logger.error("AssetAgent navigate_to 계약 위반: %s", navigate_to)
        navigate_to = "asset"

    # 프론트가 period/action/category를 읽을 수 있도록 collected_slots에 담는다
    asset_slots: dict = {"action": action}
    if period:
        asset_slots["period"] = period
    if category:
        asset_slots["category"] = category
    if filter_type:
        asset_slots["filter_type"] = filter_type

    return {
        "messages": [AIMessage(content=tts_result)],
        "navigate_to": navigate_to,
        "analytics_period": period if action != "balance" else None,
        "collected_slots": asset_slots,
    }


def _build_asset_graph() -> StateGraph:
    builder = StateGraph(VoiceState)
    builder.add_node("asset_node", asset_node)
    builder.set_entry_point("asset_node")
    builder.add_edge("asset_node", END)
    return builder.compile(checkpointer=None)


asset_graph = _build_asset_graph()
