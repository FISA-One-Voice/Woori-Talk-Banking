"""자산 조회 Agent Tool (Issue #48).

"잔액 얼마야", "이번달 식비 얼마야", "최근 거래 내역" 같은 음성 명령을 처리합니다.

슬롯 스키마:
    action    : "balance" | "history" | "category" | "top_category"
    period    : "이번달" | "지난달" | "최근7일"  (기본값: 이번달)
    date_range: 시작일 ISO 형식 "YYYY-MM-DD"  (지정 기간 조회)
    category  : "식비" | "교통" | "문화생활" 등  (action=category 시 사용)
"""

import logging
from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.asset.service import (
    get_asset_summary,
    get_expense_summary,
    get_transaction_history,
)

logger = logging.getLogger(__name__)

_VALID_PERIODS: frozenset[str] = frozenset({"이번달", "지난달", "최근7일"})


def _period_to_days(period: str | None) -> int:
    """period 슬롯 값을 조회 일수(int)로 변환한다. 프론트 history.tsx periodToDays와 동일."""
    if period == "최근7일":
        return 7
    if period == "이번달":
        return 30
    if period == "지난달":
        return 60
    return 30


def _date_range_to_since(date_range: str | None) -> datetime | None:
    """date_range 슬롯(YYYY-MM-DD)을 datetime으로 변환한다. 파싱 실패 시 None 반환."""
    if not date_range:
        return None
    try:
        return datetime.strptime(date_range, "%Y-%m-%d")
    except ValueError:
        return None


def _query_balance(db, user_id: str) -> str:
    """잔액 조회 결과를 TTS 문자열로 반환한다."""
    accounts = get_asset_summary(db, user_id)
    total = sum(a.balance for a in accounts)
    return f"잔액 조회해드리겠습니다. 전체 잔액은 {total:,}원입니다."


def _query_history(db, user_id: str, period: str | None, date_range: str | None) -> str:
    """수입/지출 요약을 TTS 문자열로 반환한다. 카테고리 Top 3 포함."""
    if period and period not in _VALID_PERIODS:
        return "조회할 수 없는 기간입니다. 이번달, 지난달, 최근 7일 중 말씀해 주세요."

    since = _date_range_to_since(date_range)
    days = None if since else _period_to_days(period)
    txs = get_transaction_history(db, user_id, days=days)
    label = period or "이번달"
    completed = [t for t in txs if t.status == "completed"]
    if not completed:
        return f"{label} 거래 내역이 없습니다."

    income = sum(t.amount for t in completed if t.category == "수입")
    expense = sum(t.amount for t in completed if t.category != "수입")
    result = (
        f"{label} 지출 수입 내역 알려드리겠습니다. "
        f"수입은 {income:,}원, 지출은 {expense:,}원입니다."
    )
    try:
        summary = get_expense_summary(db, user_id, days=days or 30)
        top = summary["top_categories"][:3]
        if top:
            cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top)
            result += f" 주요 지출은 {cat_text}입니다."
    except Exception as e:
        logger.warning("카테고리 요약 조회 실패 (비필수): %s", e)
    return result


def _query_category(db, user_id: str, period: str | None, category: str | None) -> str:
    """카테고리별 지출을 TTS 문자열로 반환한다."""
    if not category:
        return "어떤 카테고리를 조회할까요? 예: 식비, 교통, 문화생활."
    days = _period_to_days(period)
    txs = get_transaction_history(db, user_id, days=days, category=category)
    total = sum(t.amount for t in txs)
    label = period or "이번달"
    return f"{label} {category} 내역 알려드리겠습니다. 총 {len(txs)}건, {total:,}원 지출하셨습니다."


def _query_top_category(db, user_id: str, period: str | None) -> str:
    """카테고리 지출 순위를 TTS 문자열로 반환한다."""
    days = _period_to_days(period)
    label = period or "이번달"
    summary = get_expense_summary(db, user_id, days=days)
    top = summary["top_categories"]
    if not top:
        return f"{label} 지출 내역이 없습니다."
    top_cat = top[0]
    cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top[:3])
    return (
        f"{label} 지출 순위 알려드리겠습니다. "
        f"가장 많이 지출한 항목은 {top_cat['category']}로 {top_cat['amount']:,}원입니다. "
        f"상위 항목은 {cat_text}입니다."
    )


@tool
def query_asset(
    user_id: str,
    action: str = "balance",
    period: str | None = None,
    date_range: str | None = None,
    category: str | None = None,
) -> str:
    """사용자의 자산·거래 내역을 조회합니다.

    아래 발화에 사용됩니다:
      - "잔액 얼마야", "전체 잔액 알려줘"          → action="balance"
      - "이번달 지출 수입 얼마야"                   → action="history"
      - "이번달 식비 얼마야"                        → action="category"
      - "어떤 거에 제일 많이 지출했어"              → action="top_category"

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        action: "balance" | "history" | "category" | "top_category"
        period: "이번달" | "지난달" | "최근7일"
        date_range: 시작일 ISO 형식 "YYYY-MM-DD"
        category: 카테고리명. action="category"일 때 사용.

    Returns:
        TTS로 읽힐 자연어 문자열.
    """
    db = next(get_db())
    try:
        if action == "balance":
            return _query_balance(db, user_id)
        if action == "history":
            return _query_history(db, user_id, period, date_range)
        if action == "category":
            return _query_category(db, user_id, period, category)
        if action in ("top_category", "expense_summary"):
            return _query_top_category(db, user_id, period)
        # 알 수 없는 action → 잔액 fallback
        return _query_balance(db, user_id)
    finally:
        db.close()
