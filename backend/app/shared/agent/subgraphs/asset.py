"""AssetAgent 서브그래프 — 잔액/내역 조회 및 지출 분석 (Dev-C 담당).

입력 계약 (ASSET_READ):
    messages, user_id, analytics_period, agent_domain

출력 계약:
    messages, navigate_to, analytics_period

절대 하지 않는 것:
    pending_action, awaiting_*, collected_slots 수정
"""

import logging

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.core.exception import AppError
from app.features.asset.service import (
    get_asset_summary,
    get_expense_summary,
    get_transaction_history,
)
from app.shared.agent.ROUTING_CONSTANTS import ASSET_NAVIGATE_VALUES
from app.shared.agent.memo_decision import last_user_text
from app.shared.agent.state import VoiceState
from app.shared.agent.tools.spending_analysis import get_monthly_spending_report

logger = logging.getLogger(__name__)

# Dev-C 소유 — Supervisor는 import하지 않음
ASSET_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "balance", "history",
    "spending_analysis", "monthly_report",
})

# ── LLM 구조화 응답 스키마 ────────────────────────────────────────────────────

class AssetQueryIntent(BaseModel):
    """asset_node LLM 분류 결과."""

    action: str  # "balance"|"history"|"category"|"top_category"|"transaction_list"|"spending_analysis"
    period: str | None = None   # "이번달" | "지난달" | "최근7일" | None
    category: str | None = None
    filter_type: str | None = None  # "income" | "expense" | "both"


# ── 잔액 fast-path 키워드 (LLM 없이 즉시 실행) ──────────────────────────────

_BALANCE_FAST_KEYWORDS: frozenset[str] = frozenset({
    "잔액", "얼마있어", "얼마 있어", "얼마야", "총자산", "전체잔액",
})


def _is_balance_fast_path(text: str) -> bool:
    """LLM 없이 잔액 조회로 즉시 처리할 수 있는 발화인지 판별한다."""
    t = text.replace(" ", "")
    return any(kw in t for kw in _BALANCE_FAST_KEYWORDS) and len(text) <= 15


def _period_to_days(period: str | None) -> int:
    if period == "최근7일":
        return 7
    if period == "지난달":
        return 60
    return 30  # 이번달 기본값


def _normalize_period(period: str | None) -> str | None:
    if not period:
        return None
    p = period.replace(" ", "")
    if p in ("최근7일", "최근칠일", "7일"):
        return "최근7일"
    if p in ("지난달", "저번달", "전달"):
        return "지난달"
    if p in ("이번달", "이달", "이번월"):
        return "이번달"
    return None


def _format_amount(amount: int) -> str:
    if amount >= 100_000_000:
        eok = amount // 100_000_000
        man = (amount % 100_000_000) // 10_000
        return f"{eok}억 {man:,}만원" if man else f"{eok}억원"
    if amount >= 10_000:
        return f"{amount // 10_000:,}만원"
    return f"{amount:,}원"


# ── LLM 분류 ─────────────────────────────────────────────────────────────────

def _classify_intent(user_text: str, prev_period: str | None) -> AssetQueryIntent:
    """LLM으로 자산 조회 의도를 분류한다."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_CHAT_API_KEY,
        temperature=0,
    )
    llm_structured = llm.with_structured_output(AssetQueryIntent, method="function_calling")

    prev = f" (이전 기간: {prev_period})" if prev_period else ""
    prompt = (
        f"사용자 발화에서 자산 조회 의도를 파악하라.{prev}\n\n"
        "action 선택 기준:\n"
        "- balance: 잔액·전체 자산 조회\n"
        "- history: 수입/지출 금액 요약 (얼마 썼어, 수입/지출 알려줘)\n"
        "- category: 특정 카테고리 지출 (식비, 교통비 등)\n"
        "- top_category: 가장 많이 쓴 카테고리 (어디에 제일 많이 썼어)\n"
        "- transaction_list: 거래내역 목록 (거래내역 보여줘, 내역 알려줘)\n"
        "- spending_analysis: 소비 패턴/리포트 분석 (분석해줘, 소비 패턴)\n\n"
        "period: 이번달 | 지난달 | 최근7일 | null\n"
        "filter_type (action=history일 때): income | expense | both | null\n\n"
        f'발화: "{user_text}"'
    )
    try:
        return llm_structured.invoke([{"role": "user", "content": prompt}])
    except Exception as e:
        logger.warning("[AssetAgent] LLM 분류 실패: %s", e)
        return AssetQueryIntent(action="balance")


# ── 노드 ─────────────────────────────────────────────────────────────────────

def asset_node(state: VoiceState) -> dict:
    """발화를 분류하고 자산 tool을 호출해 TTS 응답을 생성한다.

    query + execute를 단일 노드로 처리한다 (슬롯 없음, 확인 없음).
    """
    user_text = last_user_text(state.get("messages", []))
    user_id = state.get("user_id", "")
    prev_period = state.get("analytics_period")

    # 잔액 fast-path: LLM 없이 즉시 실행
    if _is_balance_fast_path(user_text):
        intent = AssetQueryIntent(action="balance")
    else:
        intent = _classify_intent(user_text, prev_period)

    period = _normalize_period(intent.period) or prev_period
    days = _period_to_days(period)
    label = period or "이번달"

    db = next(get_db())
    try:
        tts_text = _execute(db, user_id, intent, days, label)
    except AppError as e:
        tts_text = e.user_message or e.message
    finally:
        db.close()

    # navigate_to 결정 (ASSET_NAVIGATE_VALUES 계약 준수)
    navigate_to: str | None = "report" if intent.action == "spending_analysis" else "balance"

    assert navigate_to in ASSET_NAVIGATE_VALUES, (
        f"AssetAgent navigate_to 계약 위반: {navigate_to}"
    )

    return {
        "messages": [AIMessage(content=tts_text)],
        "navigate_to": navigate_to,
        "analytics_period": period,  # 기간 미지정이면 None으로 초기화
    }


def _execute(db, user_id: str, intent: AssetQueryIntent, days: int, label: str) -> str:
    """action별 DB 조회 후 TTS 문자열을 반환한다."""
    if intent.action == "balance":
        accounts = get_asset_summary(db, user_id)
        total = sum(a.balance for a in accounts)
        return f"잔액 조회해드리겠습니다. 전체 잔액은 {_format_amount(total)}입니다."

    if intent.action == "top_category":
        summary = get_expense_summary(db, user_id, days=days)
        top = summary["top_categories"]
        if not top:
            return f"{label} 지출 내역이 없습니다."
        top_cat = top[0]
        return (
            f"{label} 지출 순위 알려드리겠습니다. "
            f"가장 많이 지출한 항목은 {top_cat['category']}로 "
            f"{_format_amount(top_cat['amount'])}입니다."
        )

    if intent.action == "category":
        if not intent.category:
            return "어떤 카테고리를 조회할까요? 예: 식비, 교통, 문화생활."
        txs = get_transaction_history(db, user_id, days=days, category=intent.category)
        total = sum(t.amount for t in txs)
        return (
            f"{label} {intent.category} 내역 알려드리겠습니다. "
            f"총 {len(txs)}건, {_format_amount(total)} 지출하셨습니다."
        )

    if intent.action == "transaction_list":
        txs = get_transaction_history(db, user_id, days=days)
        completed = [t for t in txs if t.status == "completed"]
        if not completed:
            return f"{label} 거래 내역이 없습니다."
        income_cnt = sum(1 for t in completed if t.category == "수입")
        expense_cnt = len(completed) - income_cnt
        return (
            f"{label} 거래내역은 총 {len(completed)}건입니다. "
            f"입금 {income_cnt}건, 출금 {expense_cnt}건입니다."
        )

    if intent.action == "spending_analysis":
        return get_monthly_spending_report.invoke({"user_id": user_id, "days": days})

    # action == "history" — 수입/지출 요약
    txs = get_transaction_history(db, user_id, days=days)
    completed = [t for t in txs if t.status == "completed"]
    if not completed:
        return f"{label} 거래 내역이 없습니다."
    income = sum(t.amount for t in completed if t.category == "수입")
    expense = sum(t.amount for t in completed if t.category != "수입")

    if intent.filter_type == "income":
        return f"{label} 수입 내역 알려드리겠습니다. 수입은 {_format_amount(income)}입니다."
    if intent.filter_type == "expense":
        return f"{label} 지출 내역 알려드리겠습니다. 지출은 {_format_amount(expense)}입니다."
    return (
        f"{label} 지출 수입 내역 알려드리겠습니다. "
        f"수입은 {_format_amount(income)}, 지출은 {_format_amount(expense)}입니다."
    )


# ── 그래프 빌드 ──────────────────────────────────────────────────────────────

def build_asset_graph() -> CompiledStateGraph:
    """AssetAgent 서브그래프를 빌드한다.

    checkpointer=None: 부모(Supervisor) MemorySaver를 공유한다.
    독립 MemorySaver를 주면 thread_id가 분리되어 상태 충돌 발생.
    """
    builder = StateGraph(VoiceState)
    builder.add_node("asset_node", asset_node)
    builder.set_entry_point("asset_node")
    builder.add_edge("asset_node", END)
    return builder.compile(checkpointer=None)


asset_graph = build_asset_graph()
