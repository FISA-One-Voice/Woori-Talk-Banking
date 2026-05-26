"""에이전트 tool 등록 파일.

Phase 1 상태: ALL_TOOLS = [] (빈 리스트)
Phase 2에서 각 화면 담당자가 아래 예시처럼 tool을 추가합니다.
"""

from app.shared.agent.tools.balance import get_total_balance, get_account_balance_by_id
from app.shared.agent.tools.history import get_recent_history, get_category_history

ALL_TOOLS: list = [
    get_total_balance,
    get_account_balance_by_id,
    get_recent_history,
    get_category_history,
]

__all__ = ["ALL_TOOLS"]