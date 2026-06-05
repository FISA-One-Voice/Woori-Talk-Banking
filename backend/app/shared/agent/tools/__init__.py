"""에이전트 tool 등록 포인트 (Issue #21, #48).

USE_MOCK_TOOLS=true  (기본값) → MOCK_TOOLS 사용 (개발/테스트 환경)
USE_MOCK_TOOLS=false           → 실제 tool 사용 (Phase 2 완료 후)
"""

from app.core.config import settings
from app.shared.agent.tools.mock_tools import (
    mock_execute_transfer,
    mock_get_balance,
    mock_get_events,
    mock_get_history,
    mock_lookup_recipient,
    mock_query_asset,
    mock_register_auto_transfer,
)

MOCK_TOOLS: list = [
    mock_lookup_recipient,
    mock_query_asset,
    mock_get_balance,
    mock_get_history,
    mock_execute_transfer,
    mock_register_auto_transfer,
    mock_get_events,
]

from app.shared.agent.tools.asset import query_asset
from app.shared.agent.tools.auto_transfer import add_auto_transfer_note
from app.shared.agent.tools.balance import get_account_balance_by_id, get_total_balance
from app.shared.agent.tools.cancel_auto_transfer import cancel_auto_transfer
from app.shared.agent.tools.event import get_event_list
from app.shared.agent.tools.execute_auto_transfer import execute_auto_transfer
from app.shared.agent.tools.history import (
    get_category_history,
    get_monthly_expense,
    get_recent_history,
)
from app.shared.agent.tools.lookup_recipient import lookup_recipient
from app.shared.agent.tools.transfer import add_note, execute_transfer, get_transfer_history

_REAL_TOOLS: list = [
    query_asset,
    get_total_balance,
    get_account_balance_by_id,
    get_recent_history,
    get_category_history,
    get_monthly_expense,
    get_transfer_history,
    execute_transfer,
    lookup_recipient,
    add_note,
    execute_auto_transfer,
    cancel_auto_transfer,
    add_auto_transfer_note,
    get_event_list,
]

ALL_TOOLS: list = MOCK_TOOLS if settings.USE_MOCK_TOOLS else _REAL_TOOLS

__all__ = ["ALL_TOOLS", "MOCK_TOOLS"]
