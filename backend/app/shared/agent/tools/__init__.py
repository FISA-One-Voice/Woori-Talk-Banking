"""에이전트 tool 등록 포인트.

등록 방법:
    1. features/{screen}/tools 에 @tool 함수 작성
    2. 해당 Dev 구역에 import 후 ALL_TOOLS 에 추가

주의:
    - _sample.py는 가이드 파일이므로 여기에 import하지 마십시오.
    - tool 파일명은 features/ 화면명과 동일하게 유지하십시오.
      예: features/balance/ → tools/balance.py
"""

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
from app.shared.agent.tools.spending_analysis import get_monthly_spending_report

# ── Dev-D (RAGAgent tools) ────────────────────────────────────────────────────
from app.shared.agent.tools.financial_qa import search_financial_docs
from app.shared.agent.tools.market_info import get_exchange_rate, get_base_rate


# TransferAgent 서브그래프 전용 tool 목록.
# Phase 2: supervisor.py에서 build_transfer_graph(TRANSFER_TOOLS)로 전달.
TRANSFER_TOOLS: list = [
    execute_transfer,
    add_note,
    execute_auto_transfer,
    add_auto_transfer_note,
    cancel_auto_transfer,
    lookup_recipient,
]

# 전체 단일 graph용 tool 목록 (build_graph / voice pipeline)
ALL_TOOLS: list = [
    get_total_balance,
    get_account_balance_by_id,
    get_recent_history,
    get_category_history,
    get_monthly_expense,
    # Dev-C: Asset
    get_monthly_spending_report,
    # Dev-B: Transfer
    get_event_list,
    execute_transfer,
    lookup_recipient,
    add_note,
    execute_auto_transfer,
    cancel_auto_transfer,
    add_auto_transfer_note,
]
