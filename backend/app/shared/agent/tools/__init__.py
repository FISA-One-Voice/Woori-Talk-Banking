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
# Issue #48: query_asset — 자산 조회 슬롯 기반 실제 tool
from app.shared.agent.tools.asset import query_asset

_REAL_TOOLS: list = [
    query_asset,
]

# ── 활성 tool 목록 ─────────────────────────────────────────────────────────────
ALL_TOOLS: list = MOCK_TOOLS if settings.USE_MOCK_TOOLS else _REAL_TOOLS

__all__ = ["ALL_TOOLS", "MOCK_TOOLS"]
