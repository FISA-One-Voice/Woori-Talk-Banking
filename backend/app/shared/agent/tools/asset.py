"""자산 조회 Agent Tool (Issue #48).

슬롯 스키마:
    action    : "balance" | "history" | "category" | "top_category" | "transaction_list"
    period    : "이번달" | "지난달" | "최근7일"
    date_range: 시작일 ISO 형식 "YYYY-MM-DD"
    category  : "식비" | "교통" | "문화생활" 등  (action=category 시 사용)
    filter_type: "income" | "expense" | "both"   (action=history 시 사용)
"""

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.asset.service import (
    query_balance_tts,
    query_category_tts,
    query_history_tts,
    query_top_category_tts,
    query_transaction_list_tts,
)


@tool
def query_asset(
    user_id: str,
    action: str = "balance",
    period: str | None = None,
    date_range: str | None = None,
    category: str | None = None,
    filter_type: str | None = None,
) -> str:
    """사용자의 자산·거래 내역을 조회합니다.

    아래 발화에 사용됩니다:
      - "잔액 얼마야", "전체 잔액 알려줘"          → action="balance"
      - "이번달 지출 수입 얼마야"                   → action="history"
      - "이번달 식비 얼마야"                        → action="category"
      - "어떤 거에 제일 많이 지출했어"              → action="top_category"
      - "최근 거래내역 알려줘"                      → action="transaction_list"

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        action: "balance" | "history" | "category" | "top_category" | "transaction_list"
        period: "이번달" | "지난달" | "최근7일"
        date_range: 시작일 ISO 형식 "YYYY-MM-DD"
        category: 카테고리명. action="category"일 때 사용.
        filter_type: "income" | "expense" | "both". action="history"일 때 사용.

    Returns:
        TTS로 읽힐 자연어 문자열.
    """
    db = next(get_db())
    try:
        if action == "balance":
            return query_balance_tts(db, user_id)
        if action == "transaction_list":
            return query_transaction_list_tts(db, user_id, period, date_range)
        if action == "history":
            return query_history_tts(db, user_id, period, date_range, filter_type)
        if action == "category":
            return query_category_tts(db, user_id, period, category)
        if action in ("top_category", "expense_summary"):
            return query_top_category_tts(db, user_id, period)
        return query_balance_tts(db, user_id)
    finally:
        db.close()
