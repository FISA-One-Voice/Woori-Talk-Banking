"""AssetAgent 서브그래프 (Dev-C).

잔액 조회, 거래 내역 조회, 지출 분석을 처리합니다.
슬롯 수집 없음 · 확인 없음 · ASV 없음 — 단순 조회 전용.

입력 계약 (ASSET_READ): messages, user_id, analytics_period, agent_domain
출력 계약:              messages, navigate_to, analytics_period
"""

import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.shared.agent.ROUTING_CONSTANTS import ASSET_NAVIGATE_VALUES
from app.shared.agent.state import VoiceState

ASSET_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "balance", "history", "category", "top_category",
    "transaction_list", "spending_analysis", "compare",
})

_NAVIGATE_MAP: dict[str, str] = {
    "balance": "asset",
    "history": "asset/history",
    "category": "asset/history",
    "top_category": "asset/history",
    "transaction_list": "asset/history",
    "spending_analysis": "report",
    "compare": "asset/compare",  # [Dev-A에게] ROUTING_CONSTANTS.ASSET_NAVIGATE_VALUES에 "asset/compare" 추가 요청 — compare 기능 신규 추가로 전용 화면(frontend/app/asset/compare.tsx)이 생겼고, navigate_to 계약값에 없으면 "asset"으로 폴백되어 화면 이동이 안 됨
}

_BALANCE_KEYWORDS = frozenset({"잔액", "얼마 있", "돈 얼마", "통장"})
_TRANSACTION_LIST_KEYWORDS = frozenset({"거래내역", "거래 내역", "거래 내용"})
_HISTORY_KEYWORDS = frozenset({"소비 내역"})
_ANALYSIS_KEYWORDS = frozenset({"분석", "리포트", "소비 분석", "지출 분석"})

_QUERY_SYSTEM_PROMPT = """너는 자산 조회 전문 에이전트야.
사용자 발화를 보고 아래 중 하나를 결정해:

- balance: 잔액 조회 ("잔액 얼마야", "돈 얼마 있어", "통장 잔액")
- history: 수입/지출 요약 ("이번달 지출 얼마야", "수입 얼마야", "소비 얼마야")
- category: 특정 카테고리 지출 ("이번달 식비 얼마야", "교통비 알려줘")
- top_category: 가장 많이 쓴 카테고리 ("어디에 제일 많이 썼어")
- transaction_list: 거래 내역 목록 ("거래내역 보여줘", "최근 내역 알려줘")
- spending_analysis: 지출 분석 리포트 ("지출 분석", "소비 분석", "리포트")
- compare: 두 기간 지출 비교 ("이번달 지난달 비교", "이번주 지난주 대비", "식비 비교해줘", "이번달 생활비 지난달이랑 비교")

다음 JSON만 반환해. 설명 없이:
{"action": "<balance|history|category|top_category|transaction_list|spending_analysis|compare>", "period": "<이번달|지난달|이번주|지난주|최근N일(예:최근3일)|N월(예:5월)|null>", "compare_period": "<이번달|지난달|이번주|지난주|null>", "category": "<카테고리명|null>", "filter_type": "<income|expense|both|null>"}

period가 발화에 없으면 "이번달"로 기본값 사용. "최근 N일"→"최근N일", "N월달"→"N월" 형식(숫자 그대로)으로 반환해.
action=compare일 때: period=기준기간(최신), compare_period=비교기간(과거). 예) "이번달 지난달 비교" → period=이번달, compare_period=지난달. "이번주 지난주 대비" → period=이번주, compare_period=지난주. 카테고리가 언급되면 category에 채울 것. 예) "식비 비교" → category=식비, "생활비 이번달 지난달 비교" → category=생활비.
category는 "식비", "교통", "쇼핑", "의료비", "문화생활", "생활비", "가족", "기타", "수입" 중 언급된 것만 채워. 없으면 반드시 JSON null(따옴표 없음)로 반환해.
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
            parsed = json.loads(match.group())
            # LLM이 null 대신 문자열 "null"을 반환하는 경우 방어
            for key in ("category", "filter_type", "period", "compare_period"):
                if parsed.get(key) == "null":
                    parsed[key] = None
            return parsed
        except json.JSONDecodeError:
            pass
    return {"action": "balance", "period": "이번달", "category": None, "filter_type": None}


def _fast_classify(user_text: str) -> str | None:
    """키워드 패스트패스 — LLM 없이 action 결정. 불명확하면 None 반환."""
    if any(kw in user_text for kw in _BALANCE_KEYWORDS):
        return "balance"
    # compare는 category/period 추출이 필요해서 항상 LLM으로 처리
    if any(kw in user_text for kw in _ANALYSIS_KEYWORDS):
        return "spending_analysis"
    if any(kw in user_text for kw in _TRANSACTION_LIST_KEYWORDS):
        return "transaction_list"
    if any(kw in user_text for kw in _HISTORY_KEYWORDS):
        return "history"
    return None


def _has_period_keyword(user_text: str) -> bool:
    """발화에 기간 키워드가 명시되어 있는지 확인."""
    if any(kw in user_text for kw in ("이번달", "이번 달", "이달", "지난달", "저번달", "전달", "지난 달", "저번 달")):
        return True
    if re.search(r'최근\s*\d+\s*일', user_text):
        return True
    if re.search(r'\d+\s*월', user_text):
        return True
    return False


def _fast_period(user_text: str) -> str:
    """발화에서 기간 키워드를 추출. 언급 없으면 "이번달" 기본값 사용."""
    if any(kw in user_text for kw in ("지난달", "저번달", "전달", "지난 달", "저번 달")):
        return "지난달"
    m = re.search(r'최근\s*(\d+)\s*일', user_text)
    if m:
        return f"최근{m.group(1)}일"
    m = re.search(r'(\d+)\s*월', user_text)
    if m:
        return f"{m.group(1)}월"
    if any(kw in user_text for kw in ("이번달", "이번 달", "이달")):
        return "이번달"
    return "이번달"


def build_asset_graph(tools: list):
    """AssetAgent 서브그래프를 빌드한다. tools는 외부(supervisor)에서 주입된다."""
    tool_registry: dict[str, object] = {tool.name: tool for tool in tools}

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
        prev_slots = state.get("collected_slots") or {}
        pending_action = prev_slots.get("action") if isinstance(prev_slots, dict) else None

        compare_period: str | None = None

        fast = _fast_classify(user_text)
        if fast == "balance":
            action, period, category, filter_type = "balance", None, None, None
        elif fast is not None:
            action = fast
            period = _fast_period(user_text)
            category, filter_type = None, None
        elif pending_action and pending_action != "balance" and _has_period_keyword(user_text) and not _fast_classify(user_text):
            # 직전 되묻기("어느 기간?") 이후 기간만 답한 경우 — 이전 action 이어받기
            action = pending_action
            period = _fast_period(user_text)
            category = prev_slots.get("category")
            filter_type = prev_slots.get("filter_type")
            if action == "compare":
                compare_period = prev_slots.get("compare_period") or "지난달"
        else:
            llm = _get_llm()
            response = await llm.ainvoke([
                {"role": "system", "content": _QUERY_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ])
            parsed = _parse_llm_action(response.content)
            action = parsed.get("action") or "balance"
            period = parsed.get("period") or prev_period or "이번달"
            category = parsed.get("category")
            filter_type = parsed.get("filter_type")
            if action == "compare":
                compare_period = parsed.get("compare_period") or "지난달"

        # ── 2. service TTS 실행 ───────────────────────────────────────────────────────
        # history 인데 발화에 기간 키워드가 없으면 → 되묻기 (DB 조회 없음)
        if action == "history" and not _has_period_keyword(user_text):
            return {
                "messages": [AIMessage(content="어느 기간을 알려드릴까요?")],
                "navigate_to": "asset/history",
                "analytics_period": None,
                "collected_slots": {"action": "history"},
            }

        tts_result = "죄송합니다. 잠시 후 다시 시도해 주세요."

        if action == "balance":
            tts_result = tool_registry["query_balance"].invoke({"user_id": user_id})
        elif action == "compare":
            tts_result = tool_registry["query_compare"].invoke({
                "user_id": user_id,
                "period": period or "이번달",
                "compare_period": compare_period or "지난달",
                "category": category,
            })
        elif action == "spending_analysis":
            tts_result = tool_registry["query_spending_report"].invoke({
                "user_id": user_id,
                "period": period or "이번달",
            })
        elif action == "category":
            tts_result = tool_registry["query_category"].invoke({
                "user_id": user_id,
                "period": period or "이번달",
                "category": category,
            })
        elif action == "top_category":
            tts_result = tool_registry["query_top_category"].invoke({
                "user_id": user_id,
                "period": period or "이번달",
            })
        elif action == "transaction_list":
            tts_result = tool_registry["query_transaction_list"].invoke({
                "user_id": user_id,
                "period": period or "이번달",
            })
        else:  # history
            tts_result = tool_registry["query_history"].invoke({
                "user_id": user_id,
                "period": period or "이번달",
                "filter_type": filter_type,
            })

        # ── 3. navigate_to 결정 ───────────────────────────────────────────────────────
        navigate_to = _NAVIGATE_MAP.get(action, "asset")
        # "asset/compare"는 ROUTING_CONSTANTS에 미등록 상태 — Dev-A가 ASSET_NAVIGATE_VALUES에 추가하면 아래 예외 조건 제거 가능
        if navigate_to not in ASSET_NAVIGATE_VALUES and navigate_to != "asset/compare":
            logger.error("AssetAgent navigate_to 계약 위반: %s", navigate_to)
            navigate_to = "asset"

        # 프론트가 period/action/category를 읽을 수 있도록 collected_slots에 담는다
        asset_slots: dict = {"action": action}
        if period:
            asset_slots["period"] = period
        if compare_period:
            asset_slots["compare_period"] = compare_period
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

    builder = StateGraph(VoiceState)
    builder.add_node("asset_node", asset_node)
    builder.set_entry_point("asset_node")
    builder.add_edge("asset_node", END)
    return builder.compile(checkpointer=None)
