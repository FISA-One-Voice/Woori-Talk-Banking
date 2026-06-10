"""잔액 조회 Agent Tool.

"잔액 얼마야", "얼마 있어" 같은 음성 명령을 처리합니다.

tool이 에이전트에 연결되는 방식:
    1. tools/__init__.py 의 ALL_TOOLS 에 등록
    2. shared/voice/router.py 가 build_graph(ALL_TOOLS) 호출
    3. 에이전트가 사용자 발화를 분석해 tool 자동 선택·실행
"""

import logging

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError
from app.features.asset.service import get_asset_summary, get_account_balance

logger = logging.getLogger(__name__)


@tool
def get_total_balance(user_id: str) -> str:  # noqa: D401
    """사용자의 전체 계좌 잔액 합계를 조회합니다.

    "잔액 얼마야", "돈 얼마 있어", "전체 잔액 알려줘" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출된 사용자 ID. voice/router.py 가 주입합니다.

    Returns:
        TTS로 읽을 문자열. 예: "전체 잔액은 150만 원입니다."

    Raises:
        BalanceError: 계좌를 찾을 수 없을 때.
    """
    db = next(get_db())
    try:
        accounts = get_asset_summary(db, user_id)
        total = sum(a.balance for a in accounts)
        logger.info(
            "balance_query_result",
            extra={"event": "balance_query_result", "user_id": user_id, "total": total},
        )
        return f"전체 잔액은 {total:,}원입니다."
    except AppError as e:
        return e.user_message or e.message
    finally:
        db.close()


@tool
def get_account_balance_by_id(user_id: str, account_id: str) -> str:  # noqa: D401
    """특정 계좌의 잔액을 조회합니다.

    "우리은행 잔액 얼마야", "주거래 통장 얼마 있어" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출된 사용자 ID.
        account_id: 조회할 계좌 ID.

    Returns:
        TTS로 읽을 문자열. 예: "우리은행 계좌 잔액은 150만 원입니다."

    Raises:
        BalanceError: 계좌를 찾을 수 없을 때.
    """
    db = next(get_db())
    try:
        account = get_account_balance(db, user_id, account_id)
        return f"{account.bank_name} 계좌 잔액은 {account.balance:,}원입니다."
    except AppError as e:
        return e.user_message or e.message
    finally:
        db.close()
