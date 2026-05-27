# =============================================================================
# backend/app/features/event/router.py
#
# [이 파일의 역할]
# HTTP 요청을 받아서 service 함수를 호출하고 표준 응답을 반환합니다.
#
# [API 목록]
# GET  /events              → 활성 이벤트 목록 조회 (로그인 불필요)
# GET  /events/{event_id}   → 이벤트 상세 조회 (로그인 불필요)
# POST /events/{event_id}/participate → 이벤트 참여 (로그인 필요)
#
# [Swagger 문서]
# 서버 실행 후 http://localhost:8000/docs 에서 직접 테스트 가능합니다.
# =============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.event import service

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=dict)
def list_events(db: Session = Depends(get_db)):
    """활성화된 이벤트 목록을 반환합니다.

    로그인 없이 조회 가능합니다.
    배너 이미지 URL이 포함됩니다 (없으면 null).

    Returns:
        표준 ApiResponse: data 필드에 EventListResponse 포함.
    """
    data = service.get_active_events(db)
    return {
        "success": True,
        "data": data.model_dump(),
        "message": "이벤트 목록을 조회했습니다.",
    }


@router.get("/{event_id}", response_model=dict)
def get_event(event_id: str, db: Session = Depends(get_db)):
    """특정 이벤트의 상세 정보를 반환합니다.

    Args:
        event_id: URL 경로에서 추출한 이벤트 UUID.

    Returns:
        표준 ApiResponse: data 필드에 EventResponse 포함.
    """
    data = service.get_event_detail(db, event_id)
    return {
        "success": True,
        "data": data.model_dump(),
        "message": "이벤트 상세 정보를 조회했습니다.",
    }


@router.post("/{event_id}/join", response_model=dict)
def join_event(
    event_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),  # JWT 인증 필요
):
    """이벤트에 참여합니다.

    로그인이 필요합니다 (Authorization: Bearer <token> 헤더).

    Args:
        event_id: 참여할 이벤트 UUID.
        user_id: JWT에서 자동 추출한 사용자 ID.

    Returns:
        표준 ApiResponse: data 필드에 participation_id 포함.
    """
    data = service.participate_event(db, event_id, user_id)
    return {
        "success": True,
        "data": data,
        "message": "이벤트 참여가 완료되었습니다.",
    }
