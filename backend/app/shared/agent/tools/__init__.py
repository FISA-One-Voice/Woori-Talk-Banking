"""에이전트 tool 등록 포인트 (Issue #21, #48).

USE_MOCK_TOOLS=true  (기본값) → MOCK_TOOLS 사용 (개발/테스트 환경)
USE_MOCK_TOOLS=false           → 실제 tool 사용 (Phase 2 완료 후)

실제 tool 추가 방법:
    1. features/{screen}/tools.py 에 @tool 함수 작성
    2. 아래 _REAL_TOOLS 에 import 후 추가
    3. USE_MOCK_TOOLS=false 설정

주의: _sample.py 는 가이드 파일이므로 여기에 import 하지 마십시오.
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

# ── Mock tool 목록 ─────────────────────────────────────────────────────────────
MOCK_TOOLS: list = [
    mock_lookup_recipient,
    mock_query_asset,
    mock_get_balance,
    mock_get_history,
    mock_execute_transfer,
    mock_register_auto_transfer,
    mock_get_events,
]

# ── 실제 tool 목록 ─────────────────────────────────────────────────────────────
from app.shared.agent.tools.asset import query_asset
from app.shared.agent.tools.event import get_event_list
from app.shared.agent.tools.transfer import add_note, execute_transfer, get_transfer_history
from app.shared.agent.tools.balance import get_account_balance_by_id, get_total_balance
from app.shared.agent.tools.history import (
    get_category_history,
    get_monthly_expense,
    get_recent_history,
)

_REAL_TOOLS: list = [
    get_event_list,
    execute_transfer,
    add_note,
    get_transfer_history,
    get_total_balance,
    get_account_balance_by_id,
    get_recent_history,
    get_category_history,
    get_monthly_expense,
    query_asset,
    # lookup_recipient,   # 공통 — tools/lookup_recipient.py 완성 후 주석 해제
    # register_auto_transfer,  # auto_transfer 담당자 완성 후 주석 해제
]

# ── 활성 tool 목록 ─────────────────────────────────────────────────────────────
ALL_TOOLS: list = MOCK_TOOLS if settings.USE_MOCK_TOOLS else _REAL_TOOLS

__all__ = ["ALL_TOOLS", "MOCK_TOOLS"]
