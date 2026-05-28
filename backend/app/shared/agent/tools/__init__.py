# Design Ref: §3.3 — Phase 2 tool 집합 포인트. 이 파일만 수정하면 에이전트에 연결.
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
from app.shared.agent.tools.mock_tools import (
    mock_execute_transfer,
    mock_get_balance,
    mock_get_events,
    mock_get_history,
    mock_register_auto_transfer,
)

# ── Mock tool 목록 ─────────────────────────────────────────────────────────────
# Phase 2 실제 tool 완성 전까지 사용하는 mock 구현체.
# 화면 담당자가 실제 tool을 완성하면 _REAL_TOOLS로 이동.
MOCK_TOOLS: list = [
    mock_get_balance,
    mock_get_history,
    mock_execute_transfer,
    mock_register_auto_transfer,
    mock_get_events,
]

# ── 실제 tool 목록 ─────────────────────────────────────────────────────────────
# Phase 2 담당자가 완성한 실제 tool을 여기에 추가한다.
# 예:
#   from app.shared.agent.tools.balance import get_balance_tool
#   _REAL_TOOLS = [get_balance_tool, ...]
_REAL_TOOLS: list = []

# ── 활성 tool 목록 ─────────────────────────────────────────────────────────────
# USE_MOCK_TOOLS=true  (기본값) → MOCK_TOOLS 사용 (개발/테스트 환경)
# USE_MOCK_TOOLS=false           → 실제 tool 사용 (Phase 2 완료 후)
ALL_TOOLS: list = MOCK_TOOLS if settings.USE_MOCK_TOOLS else _REAL_TOOLS

__all__ = ["ALL_TOOLS", "MOCK_TOOLS"]
