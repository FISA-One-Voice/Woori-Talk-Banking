"""지출 분석 Agent Tools (Dev-C).

리포트 화면(report/index.tsx)에 표시할 월별 지출 분석 TTS 요약을 반환합니다.
예외는 잡지 않고 그대로 올린다 — main.py AppError 핸들러가 처리한다.
"""

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.analytics.service import get_monthly_analytics


@tool
def get_monthly_spending_report(user_id: str, period: str = "이번달") -> str:
    """월별 카테고리별 지출 분석 리포트를 조회합니다.

    "이번달 지출 분석해줘", "지난달 소비 리포트 보여줘" 발화에 사용합니다.
    navigate_to="report" 와 함께 사용하여 리포트 화면을 표시합니다.

    Args:
        user_id: 사용자 UUID 문자열.
        period: "이번달" | "지난달" | "3개월"
    """
    db = next(get_db())
    try:
        result = get_monthly_analytics(db, user_id, period)
        top = result.categories[0] if result.categories else None
        tts = (
            f"{period} 총 지출은 {result.total_spending:,}원이고, "
            f"가장 많이 쓴 카테고리는 {top.category} {top.amount:,}원입니다."
            if top
            else f"{period} 지출 내역이 없습니다."
        )
        return tts
    finally:
        db.close()
