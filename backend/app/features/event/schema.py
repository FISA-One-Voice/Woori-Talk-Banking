# =============================================================================
# backend/app/features/event/schema.py
#
# [이 파일의 역할]
# API 가 주고받는 데이터의 모양(형태)을 정의합니다.
# 잘못된 타입의 데이터가 들어오면 FastAPI 가 자동으로 422 오류를 반환합니다.
# 예: title 이 숫자로 들어오면 자동 거부 → 서비스 코드에서 검사할 필요가 없습니다.
#
# [다른 파일과의 관계]
# ├─ router.py  → 함수의 반환 타입(response_model)으로 사용합니다.
# └─ service.py → 반환값을 이 스키마로 조립합니다.
#
# [Pydantic BaseModel 이란?]
# Python 딕셔너리(dict)와 달리, 필드 타입을 보장하고 JSON 변환을 자동으로 처리합니다.
# =============================================================================

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── 이벤트 관련 응답 스키마 ────────────────────────────────────────────────────

class EventSummary(BaseModel):
    """
    이벤트 목록에서 한 줄로 보여줄 간략 정보.
    GET /api/events 의 data 배열 각 항목에 해당합니다.
    """

    event_id: str
    title: str
    start_at: datetime
    end_at: datetime
    is_active: bool


class EventDetail(BaseModel):
    """
    이벤트 상세 화면에서 보여줄 전체 정보.
    GET /api/events/{event_id} 의 data 에 해당합니다.
    """

    event_id: str
    title: str
    description: str | None
    banner_image_url: str | None
    start_at: datetime
    end_at: datetime
    is_active: bool
    # DB 컬럼 아님 — event_participations 행 수를 집계한 값
    participant_count: int


# ── 참여 관련 응답 스키마 ────────────────────────────────────────────────────

class ParticipationResult(BaseModel):
    """
    이벤트 참여 성공 시 반환하는 데이터.
    POST /api/events/{event_id}/participate 의 data 에 해당합니다.
    """

    event_id: str
    user_id: str
    participated_at: datetime


# ── 공통 API 응답 래퍼 ────────────────────────────────────────────────────────
# CLAUDE.md 에 정의된 표준 응답 형식입니다.
# 모든 엔드포인트는 성공/실패 모두 이 형태로 응답해야 합니다.
#
# 성공: {"success": true,  "data": {...}, "message": "...", "error_code": null}
# 실패: {"success": false, "data": null,  "message": "...", "error_code": "ALREADY_PARTICIPATED"}

class ApiResponse(BaseModel):
    """
    모든 API 엔드포인트의 공통 응답 형태.

    프론트엔드는 반드시 error_code 로 분기 처리해야 합니다.
    message 문자열로 분기하면 안 됩니다. (메시지는 언제든 바뀔 수 있기 때문입니다.)
    """

    success: bool  # 성공: True / 실패: False
    data: Any = None  # 실제 데이터 (실패 시 null)
    message: str  # 사람이 읽을 수 있는 안내 문구
    error_code: str | None = None  # 실패 시 오류 코드 (예: "ALREADY_PARTICIPATED")
