from sqlalchemy.orm import Session

from app.features.asset.service import get_expense_summary
from app.features.analytics.schema import CategorySpending, MonthlyAnalyticsResponse

PERIOD_TO_DAYS: dict[str, int] = {
    "이번달": 30,
    "지난달": 60,
    "3개월": 90,
}


def get_monthly_analytics(
    db: Session,
    user_id: str,
    period: str = "이번달",
) -> MonthlyAnalyticsResponse:
    """월별 지출 분석 데이터를 조회합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: 사용자 UUID 문자열.
        period: 조회 기간. "이번달" | "지난달" | "3개월". 기본값 "이번달".

    Returns:
        MonthlyAnalyticsResponse — 총 지출, 카테고리별 지출 비율, 최다 지출 카테고리.

    Raises:
        HistoryError: 해당 기간에 지출 내역이 없는 경우 (TX_NOT_FOUND).
    """
    days = PERIOD_TO_DAYS.get(period, 30)
    summary = get_expense_summary(db, user_id, days)

    total = summary["total"]
    top_categories = summary["top_categories"]

    categories = [
        CategorySpending(
            category=item["category"],
            amount=item["amount"],
            ratio=round(item["amount"] / total * 100, 1) if total else 0.0,
        )
        for item in top_categories
    ]

    top_category = categories[0].category if categories else "없음"

    return MonthlyAnalyticsResponse(
        period=period,
        total_spending=total,
        categories=categories,
        top_category=top_category,
    )
