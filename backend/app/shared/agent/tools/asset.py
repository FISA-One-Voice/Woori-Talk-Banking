"""자산 조회 Agent Tools (Issue #48).

각 tool은 단일 책임을 가지며 짧은 docstring으로 에이전트가 쉽게 선택할 수 있도록 한다.
비즈니스 로직은 features/asset/service.py에 있고, 여기서는 wrapping만 한다.
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
def get_balance(user_id: str) -> str:
    """전체 계좌 잔액을 조회합니다.

    "잔액 얼마야", "전체 잔액 알려줘", "통장에 돈 얼마 있어" 발화에 사용합니다.
    """
    db = next(get_db())
    try:
        return query_balance_tts(db, user_id)
    finally:
        db.close()


@tool
def get_income_expense_summary(
    user_id: str,
    period: str = "이번달",
    filter_type: str = "both",
) -> str:
    """수입·지출 금액 요약을 조회합니다.

    "이번달 지출 얼마야", "지난달 수입 알려줘", "최근 7일 소비 얼마야" 발화에 사용합니다.

    Args:
        period: "이번달" | "지난달" | "최근7일"
        filter_type: "income"=수입만 | "expense"=지출만 | "both"=둘다
    """
    db = next(get_db())
    try:
        return query_history_tts(db, user_id, period, None, filter_type)
    finally:
        db.close()


@tool
def get_category_expense(
    user_id: str,
    category: str,
    period: str = "이번달",
) -> str:
    """특정 카테고리의 지출을 조회합니다.

    "이번달 식비 얼마야", "지난달 교통비 알려줘" 발화에 사용합니다.

    Args:
        category: 카테고리명 (예: 식비, 교통, 쇼핑, 의료비, 문화생활)
        period: "이번달" | "지난달" | "최근7일"
    """
    db = next(get_db())
    try:
        return query_category_tts(db, user_id, period, category)
    finally:
        db.close()


@tool
def get_top_spending_category(
    user_id: str,
    period: str = "이번달",
) -> str:
    """가장 많이 지출한 카테고리를 조회합니다.

    "어디에 제일 많이 썼어", "뭐에 돈 많이 썼어", "이번달 지출 1위 알려줘" 발화에 사용합니다.

    Args:
        period: "이번달" | "지난달" | "최근7일"
    """
    db = next(get_db())
    try:
        return query_top_category_tts(db, user_id, period)
    finally:
        db.close()


@tool
def get_transaction_list(
    user_id: str,
    period: str = "이번달",
) -> str:
    """거래내역 목록을 조회합니다 (최대 10건).

    "거래내역 보여줘", "최근 내역 알려줘", "이번달 거래 목록" 발화에 사용합니다.

    Args:
        period: "이번달" | "지난달" | "최근7일"
    """
    db = next(get_db())
    try:
        return query_transaction_list_tts(db, user_id, period, None)
    finally:
        db.close()
