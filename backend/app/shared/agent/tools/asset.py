"""자산 조회 Agent Tools — AssetAgent 전용.

잔액·거래내역·지출 분석·비교 조회를 각각 독립 tool로 분리합니다.
AssetAgent(subgraphs/asset.py)가 action 분류 후 해당 tool을 호출합니다.
TTS 포맷은 service 레이어(asset/service.py, analytics/service.py)가 담당합니다.
"""

import logging

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError
from app.features.analytics.service import query_spending_analysis_tts
from app.features.asset.service import (
    query_balance_tts,
    query_category_tts,
    query_compare_tts,
    query_history_tts,
    query_top_category_tts,
    query_transaction_list_tts,
)

logger = logging.getLogger(__name__)


@tool
def query_balance(user_id: str) -> str:
    """사용자의 전체 계좌 잔액을 조회합니다.

    "잔액 얼마야", "돈 얼마 있어", "통장 잔액" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
    """
    db = next(get_db())
    try:
        return query_balance_tts(db, user_id)
    except AppError as e:
        logger.warning("query_balance AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()


@tool
def query_history(
    user_id: str,
    period: str = "이번달",
    filter_type: str | None = None,
) -> str:
    """수입·지출 요약을 조회합니다.

    "이번달 지출 얼마야", "수입 얼마야", "소비 얼마야" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        period: 조회 기간. 예: "이번달", "지난달", "최근7일".
        filter_type: "income"=수입만, "expense"=지출만, None=둘 다.
    """
    db = next(get_db())
    try:
        return query_history_tts(db, user_id, period, None, filter_type)
    except AppError as e:
        logger.warning("query_history AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()


@tool
def query_category(
    user_id: str,
    period: str = "이번달",
    category: str | None = None,
) -> str:
    """특정 카테고리의 지출을 조회합니다.

    "이번달 식비 얼마야", "교통비 알려줘" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        period: 조회 기간.
        category: 조회할 카테고리. 예: "식비", "교통", "쇼핑".
    """
    db = next(get_db())
    try:
        return query_category_tts(db, user_id, period, category)
    except AppError as e:
        logger.warning("query_category AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()


@tool
def query_top_category(user_id: str, period: str = "이번달") -> str:
    """가장 많이 지출한 카테고리를 조회합니다.

    "어디에 제일 많이 썼어", "최다 지출 카테고리" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        period: 조회 기간.
    """
    db = next(get_db())
    try:
        return query_top_category_tts(db, user_id, period)
    except AppError as e:
        logger.warning("query_top_category AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()


@tool
def query_transaction_list(user_id: str, period: str = "이번달") -> str:
    """거래 내역 목록을 조회합니다 (최대 10건).

    "거래내역 보여줘", "최근 내역 알려줘" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        period: 조회 기간.
    """
    db = next(get_db())
    try:
        return query_transaction_list_tts(db, user_id, period, None)
    except AppError as e:
        logger.warning("query_transaction_list AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()


@tool
def query_spending_report(user_id: str, period: str = "이번달") -> str:
    """월별 카테고리별 지출 분석 리포트를 조회합니다.

    "지출 분석해줘", "소비 분석", "리포트 보여줘" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        period: 조회 기간. "이번달" | "지난달" | "3개월".
    """
    db = next(get_db())
    try:
        return query_spending_analysis_tts(db, user_id, period)
    except AppError as e:
        logger.warning("query_spending_report AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()


@tool
def query_compare(
    user_id: str,
    period: str = "이번달",
    compare_period: str = "지난달",
    category: str | None = None,
) -> str:
    """두 기간의 지출을 비교합니다.

    "이번달 지난달 비교", "식비 이번주 지난주 대비" 발화에 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        period: 기준 기간 (최신). 예: "이번달", "이번주".
        compare_period: 비교 기간 (과거). 예: "지난달", "지난주".
        category: 특정 카테고리만 비교할 경우. None이면 전체 지출 비교.
    """
    db = next(get_db())
    try:
        return query_compare_tts(db, user_id, period, compare_period, category)
    except AppError as e:
        logger.warning("query_compare AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    finally:
        db.close()
