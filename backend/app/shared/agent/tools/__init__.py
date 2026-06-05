"""에이전트 tool 등록 포인트.

등록 방법:
    1. features/{screen}/tools 에 @tool 함수 작성
    2. 해당 Dev 구역에 import 후 ALL_TOOLS 에 추가

주의:
    - _sample.py는 가이드 파일이므로 여기에 import하지 마십시오.
    - tool 파일명은 features/ 화면명과 동일하게 유지하십시오.
      예: features/balance/ → tools/balance.py
"""

# ── Dev-B (TransferAgent tools) ───────────────────────────────────────────────
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
from app.shared.agent.tools.transfer import add_note, execute_transfer

# ── Dev-C (AssetAgent tools) ──────────────────────────────────────────────────
# Dev-C: 이 구역에만 추가
# from app.shared.agent.tools.spending_analysis import get_monthly_spending_report

# ── Dev-D (RAGAgent tools) ────────────────────────────────────────────────────
# Dev-D: 이 구역에만 추가
# from app.shared.agent.tools.financial_qa import search_financial_docs
# from app.shared.agent.tools.market_info import get_exchange_rate, get_base_rate

ALL_TOOLS: list = [
    # Balance
    get_total_balance,
    get_account_balance_by_id,
    # History
    get_recent_history,
    get_category_history,
    get_monthly_expense,
    # Dev-B: Transfer
    get_event_list,
    execute_transfer,
    lookup_recipient,
    add_note,
    execute_auto_transfer,
    cancel_auto_transfer,
    add_auto_transfer_note,
]

__all__ = ["ALL_TOOLS"]
