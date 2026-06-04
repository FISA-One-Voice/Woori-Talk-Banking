"""거래 내역 조회 Agent Tool.

"최근 7일 소비 내역", "이번 달 지출 얼마야" 같은 음성 명령을 처리합니다.

tool이 에이전트에 연결되는 방식:
    1. tools/__init__.py 의 ALL_TOOLS 에 등록
    2. shared/voice/router.py 가 build_graph(ALL_TOOLS) 호출
    3. 에이전트가 사용자 발화를 분석해 tool 자동 선택·실행
"""

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError
from app.features.asset.service import get_expense_summary, get_transaction_history


@tool
def get_recent_history(user_id: str, days: int = 7) -> str:  # noqa: D401
    """최근 N일간의 거래 내역을 조회합니다.

    "최근 7일 소비 내역", "지난 한달 거래 내역" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        days: 조회할 기간 (기본 7일).

    Returns:
        TTS로 읽을 문자열. 예: "최근 7일간 거래 내역은 총 3건입니다."

    Raises:
        HistoryError: 거래 내역이 없을 때.
    """
    db = next(get_db())
    try:
        transactions = get_transaction_history(db, user_id, days=days)
        total = sum(t.amount for t in transactions)
        return (
            f"최근 {days}일간 거래 내역 알려드리겠습니다. 총 {len(transactions)}건, {total:,}원입니다."
        )
    except AppError as e:
        return e.user_message or e.message
    finally:
        db.close()


@tool
def get_category_history(user_id: str, category: str, days: int = 30) -> str:  # noqa: D401
    """카테고리별 거래 내역을 조회합니다.

    "이번 달 식비 얼마야", "최근 교통비 내역" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        category: 조회할 카테고리 (예: 식비, 교통, 쇼핑).
        days: 조회할 기간 (기본 30일).

    Returns:
        TTS로 읽을 문자열. 예: "이번 달 식비는 총 5건, 15만 원입니다."

    Raises:
        HistoryError: 거래 내역이 없을 때.
    """
    db = next(get_db())
    try:
        transactions = get_transaction_history(
            db, user_id, days=days, category=category
        )
        total = sum(t.amount for t in transactions)
        return (
            f"{days}일간 {category} 내역 알려드리겠습니다. 총 {len(transactions)}건, {total:,}원입니다."
        )
    except AppError as e:
        return e.user_message or e.message
    finally:
        db.close()


@tool
def get_monthly_expense(user_id: str, days: int = 30) -> str:  # noqa: D401
    """지난 달 총 지출과 카테고리별 지출 현황을 조회합니다.

    "지난 달 돈 얼마 썼어", "이번 달 소비 내역 알려줘", "최근 한달 지출 요약해줘" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        days: 조회할 기간 (기본 30일).

    Returns:
        TTS로 읽을 문자열. 예: "30일간 총 지출은 50만 원입니다. 식비 20만 원, 교통비 10만 원 등 지출하였습니다."

    Raises:
        HistoryError: 지출 거래 내역이 없을 때.
    """
    db = next(get_db())
    try:
        summary = get_expense_summary(db, user_id, days)
        total = summary["total"]
        top = summary["top_categories"]
        cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top)
        return f"{days}일간 지출 내역 알려드리겠습니다. 총 지출은 {total:,}원이며, {cat_text} 등 지출하셨습니다."
    finally:
        db.close()
