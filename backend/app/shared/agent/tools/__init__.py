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

from app.core.config import settings

# ── Mock tool 목록 ─────────────────────────────────────────────────────────────
# mock_tools.py가 아직 없는 환경(테스트 등)에서도 앱이 기동되도록 안전하게 처리.
try:
    from app.shared.agent.tools.mock_tools import (
        mock_execute_transfer,
        mock_get_balance,
        mock_get_events,
        mock_get_history,
        mock_lookup_recipient,
        mock_register_auto_transfer,
    )
    MOCK_TOOLS: list = [
        mock_lookup_recipient,
        mock_get_balance,
        mock_get_history,
        mock_execute_transfer,
        mock_register_auto_transfer,
        mock_get_events,
    ]
except ImportError:
    MOCK_TOOLS = []

# ── 실제 tool 목록 ─────────────────────────────────────────────────────────────
# 자동이체 담당자 완료분만 등록합니다.
# recipients(search_recipient), asv(verify_speaker), transfer 등
# 다른 담당자 tool은 각 담당자가 완성 후 여기에 추가합니다.
from app.shared.agent.tools.auto_transfer import parse_auto_transfer_slots
from app.shared.agent.tools.cancel_auto_transfer import cancel_auto_transfer
from app.shared.agent.tools.execute_auto_transfer import execute_auto_transfer
from app.shared.agent.tools.lookup_recipient import lookup_recipient

_REAL_TOOLS: list = [
    lookup_recipient,
    parse_auto_transfer_slots,
    execute_auto_transfer,
    cancel_auto_transfer,
]

# ── 활성 tool 목록 ─────────────────────────────────────────────────────────────
# USE_MOCK_TOOLS=true  (기본값) → MOCK_TOOLS 사용 (개발/테스트 환경)
# USE_MOCK_TOOLS=false           → 실제 tool 사용 (Phase 2 완료 후)
ALL_TOOLS: list = MOCK_TOOLS if settings.USE_MOCK_TOOLS else _REAL_TOOLS

__all__ = ["ALL_TOOLS", "MOCK_TOOLS"]
