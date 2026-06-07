"""에이전트 tool 등록 포인트.

Phase 2.5 (Issue #21): USE_MOCK_TOOLS=true (기본값) 이면 MOCK_TOOLS 사용.
Phase 2 담당자가 실제 tool 완성 시 USE_MOCK_TOOLS=false 로 전환.

등록 방법 (실제 tool):
    1. features/{screen}/tools 에 @tool 함수 작성
    2. 아래 _REAL_TOOLS 에 import 후 추가
    3. USE_MOCK_TOOLS=false 설정

주의:
    - _sample.py는 가이드 파일이므로 여기에 import하지 마십시오.
    - tool 파일명은 features/ 화면명과 동일하게 유지하십시오.
      예: features/balance/ → tools/balance.py
"""
# Plan SC: build_graph([]) 호출 시 오류 없이 초기화 (Issue #5 완료 조건)

from app.shared.agent.tools.balance import get_account_balance_by_id, get_total_balance
from app.shared.agent.tools.history import (
    get_category_history,
    get_monthly_expense,
    get_recent_history,
)

ALL_TOOLS: list = [
    get_total_balance,
    get_account_balance_by_id,
    get_recent_history,
    get_category_history,
    get_monthly_expense,
]

# ── Dev-B (TransferAgent tools) ───────────────────────────────────────────────
from app.core.config import settings
from app.shared.agent.tools.auto_transfer import add_auto_transfer_note
from app.shared.agent.tools.cancel_auto_transfer import cancel_auto_transfer
from app.shared.agent.tools.event import get_event_list
from app.shared.agent.tools.execute_auto_transfer import execute_auto_transfer
from app.shared.agent.tools.lookup_recipient import lookup_recipient
from app.shared.agent.tools.mock_tools import (
    mock_execute_transfer,
    mock_get_balance,
    mock_get_history,
    mock_lookup_recipient,
    mock_register_auto_transfer,
)
from app.shared.agent.tools.transfer import add_note, execute_transfer

# ── Dev-C (AssetAgent tools) ──────────────────────────────────────────────────
# Dev-C: 이 구역에만 추가
# from app.shared.agent.tools.spending_analysis import get_monthly_spending_report

# ── Dev-D (RAGAgent tools) ────────────────────────────────────────────────────
# Dev-D: 이 구역에만 추가
from app.shared.agent.tools.financial_qa import search_financial_docs
from app.shared.agent.tools.market_info import get_exchange_rate, get_base_rate

# ── Mock tool 목록 ─────────────────────────────────────────────────────────────
# 실제 tool 완성 전까지 사용하는 mock 구현체.
# 화면 담당자가 실제 tool을 완성하면 _REAL_TOOLS로 이동.
MOCK_TOOLS: list = [
    mock_lookup_recipient,
    mock_get_balance,
    mock_get_history,
    mock_execute_transfer,
    mock_register_auto_transfer,
    get_event_list,
]

# ── 실제 tool 목록 ─────────────────────────────────────────────────────────────
# Phase 2 담당자가 완성한 실제 tool을 여기에 추가한다.
#
# 추가 순서 (담당자별):
#   공통:          from app.shared.agent.tools.lookup_recipient import lookup_recipient
#   balance  (B):  from app.shared.agent.tools.balance import execute_balance
#   history  (B):  from app.shared.agent.tools.history import execute_history
#   transfer (C):  from app.shared.agent.tools.transfer import execute_transfer
#   auto_transfer (D): from app.shared.agent.tools.auto_transfer import (
#                          register_auto_transfer)
_REAL_TOOLS: list = [
    get_event_list,
    execute_transfer,
    lookup_recipient,
    execute_auto_transfer,
    cancel_auto_transfer,
    # execute_balance,
    # execute_history,
    add_note,  # 이체 직후 메모 (tx_id 기반)
    add_auto_transfer_note,  # 자동이체 직후 메모 (order_id 기반)
    # lookup_recipient,   # 공통 — tools/lookup_recipient.py 완성 후 주석 해제
    # execute_balance,    # balance 담당자 — tools/balance.py 완성 후 주석 해제
    # execute_history,    # history 담당자 — tools/history.py 완성 후 주석 해제
    # register_auto_transfer,  # auto_transfer 담당자 — auto_transfer.py 완성 후 해제
    # Dev-D (RAG)
    search_financial_docs,
    get_exchange_rate,
    get_base_rate,
]

# ── 활성 tool 목록 ─────────────────────────────────────────────────────────────
# USE_MOCK_TOOLS=true  → MOCK_TOOLS 사용 (개발/테스트 환경)
# USE_MOCK_TOOLS=false → 실제 tool 사용 (Phase 2 완료 후)
ALL_TOOLS: list = MOCK_TOOLS if settings.USE_MOCK_TOOLS else _REAL_TOOLS

__all__ = ["ALL_TOOLS", "MOCK_TOOLS"]
