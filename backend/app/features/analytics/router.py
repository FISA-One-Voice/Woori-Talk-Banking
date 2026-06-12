from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.analytics import service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/monthly")
def get_monthly_analytics(
    period: str = "이번달",
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """월별 지출 분석을 조회합니다.

    Args:
        period: 조회 기간. "이번달" | "지난달" | "3개월". 기본값 "이번달".
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.

    Returns:
        period, total_spending, categories(카테고리별 지출+비율), top_category 포함 성공 응답.

    Raises:
        HistoryError: 해당 기간에 지출 내역이 없는 경우 (TX_NOT_FOUND).
    """
    data = service.get_monthly_analytics(db, user_id, period)
    return {
        "success": True,
        "data": data,
        "message": f"{period} 지출 분석입니다.",
    }
