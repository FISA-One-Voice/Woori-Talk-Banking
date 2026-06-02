"""자산 조회 Agent Tool (Issue #48).

"잔액 얼마야", "이번달 식비 얼마야", "최근 거래 내역" 같은 음성 명령을 처리합니다.

슬롯 스키마:
    action    : "balance" | "history" | "category"
    period    : "이번달" | "지난달" | "최근7일"  (기본값: 이번달)
    date_range: 시작일 ISO 형식 "YYYY-MM-DD"  (지정 기간 조회)
    category  : "식비" | "교통" | "문화생활" 등  (action=category 시 사용)
"""

from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.asset.service import (
    get_asset_summary,
    get_expense_summary,
    get_transaction_history,
)


def _period_to_days(period: str | None) -> int:
    """period 슬롯 값을 조회 일수(int)로 변환한다."""
    if period == "최근7일":
        return 7
    if period == "이번달":
        now = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None)
        return now.day
    if period == "지난달":
        return 60  # service 레이어에서 실제 범위로 필터링
    return 30  # 기본값


def _date_range_to_since(date_range: str | None) -> datetime | None:
    """date_range 슬롯(YYYY-MM-DD)을 datetime으로 변환한다. 파싱 실패 시 None 반환."""
    if not date_range:
        return None
    try:
        return datetime.strptime(date_range, "%Y-%m-%d")
    except ValueError:
        return None


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
      - "잔액 얼마야", "전체 잔액 알려줘", "통장 잔액"          → action="balance"
      - "이번달 거래 내역", "최근 칠일 소비 내역"               → action="history"
      - "이번달 식비 얼마야", "교통비 내역 알려줘"              → action="category"

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        action: "balance" | "history" | "category" (기본값: "balance")
        period: "이번달" | "지난달" | "최근7일" (없으면 30일 기본)
        date_range: 시작일 ISO 형식 "YYYY-MM-DD" (지정 기간)
        category: 카테고리명. action="category"일 때 사용. 예: "식비", "교통"

    Returns:
        TTS로 읽힐 자연어 문자열.
    """
    db = next(get_db())
    try:
        if action == "balance":
            accounts = get_asset_summary(db, user_id)
            total = sum(a.balance for a in accounts)
            return f"전체 잔액은 {total:,}원입니다."

        if action == "history":
            since = _date_range_to_since(date_range)
            days = None if since else _period_to_days(period)
            txs = get_transaction_history(db, user_id, days=days)
            total = sum(t.amount for t in txs)
            label = period or "최근"
            return f"{label} 거래 내역은 총 {len(txs)}건, {total:,}원입니다."

        if action == "category":
            if not category:
                return "어떤 카테고리를 조회할까요? 예: 식비, 교통, 문화생활."
            days = _period_to_days(period)
            txs = get_transaction_history(db, user_id, days=days, category=category)
            total = sum(t.amount for t in txs)
            label = period or "최근"
            return f"{label} {category} 지출은 총 {len(txs)}건, {total:,}원입니다."

        # 알 수 없는 action → 잔액 요약 fallback
        summary = get_expense_summary(db, user_id, days=30)
        total = summary["total"]
        top = summary["top_categories"]
        cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top)
        return f"이번달 총 지출은 {total:,}원입니다. {cat_text} 등 지출하셨습니다."

    finally:
        db.close()
