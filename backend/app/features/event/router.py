# =============================================================================
# backend/app/features/event/router.py
#
# [이 파일의 역할]
# "어떤 URL 로 요청이 오면 어떤 함수를 실행할지" 를 정의합니다.
# 실제 처리 로직은 service.py 에 있고, 이 파일은 URL ↔ 함수를 연결하기만 합니다.
#
# [다른 파일과의 관계]
# ├─ main.py          → 이 파일의 router 를 앱에 등록합니다.
# ├─ service.py       → 실제 비즈니스 로직 함수를 호출합니다.
# ├─ database.py      → get_db() 로 DB 세션을 주입받습니다.
# └─ schema.py        → 응답 형태(ApiResponse)를 가져옵니다.
#
# [엔드포인트 목록]
# GET  /api/events                        → 이벤트 목록
# GET  /api/events/{event_id}             → 이벤트 상세
# POST /api/events/{event_id}/participate → 이벤트 참여
# =============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.event import service
from app.features.event.schema import (
    ApiResponse,
    EventDetail,
    EventSummary,
    ParticipationResult,
)


# ── 임시 사용자 인증 ────────────────────────────────────────────────────────────
# 실제 서비스에서는 JWT 토큰을 검증해서 로그인한 사용자의 UUID 를 가져와야 합니다.
# auth 모듈이 완성되면 아래 함수를 삭제하고 다음 줄로 교체하세요:
# from app.features.auth.router import get_current_user
def get_current_user() -> str:
    """현재 로그인한 사용자 UUID 를 반환합니다. (임시: 고정값)"""
    return "00000000-0000-0000-0000-000000000001"  # TODO: JWT 토큰 검증으로 교체 예정


# ── 라우터 생성 ─────────────────────────────────────────────────────────────────
# prefix="/api/events" → 이 파일의 모든 경로 앞에 /api/events 가 자동으로 붙습니다.
# tags=["events"]      → Swagger UI (localhost:8000/docs) 에서 그룹화됩니다.
router = APIRouter(prefix="/api/events", tags=["events"])


# ── 엔드포인트 1: 이벤트 목록 ────────────────────────────────────────────────────
@router.get("", response_model=ApiResponse)
def list_events(db: Session = Depends(get_db)):
    """
    이벤트 목록 조회.

    GET /api/events
    성공: {"success": true, "data": [{...}, {...}], "message": "...", "error_code": null}
    """
    events = service.get_event_list(db)

    # EventSummary 형태로 변환합니다.
    # model_dump() 는 Pydantic 객체를 dict 로 변환하는 메서드입니다.
    data = [
        EventSummary(
            event_id=e.event_id,
            title=e.title,
            start_at=e.start_at,
            end_at=e.end_at,
            is_active=e.is_active,
        ).model_dump()
        for e in events  # events 리스트의 각 이벤트를 하나씩 변환
    ]

    return ApiResponse(
        success=True,
        data=data,
        message=f"이벤트 {len(data)}개를 불러왔습니다.",
    )


# ── 엔드포인트 2: 이벤트 상세 ────────────────────────────────────────────────────
@router.get("/{event_id}", response_model=ApiResponse)
def get_event(event_id: str, db: Session = Depends(get_db)):
    """
    이벤트 상세 조회.

    GET /api/events/{event_id}
    성공: {"success": true,  "data": {...}, "message": "..."}
    실패: {"success": false, "data": null, "message": "...", "error_code": "EVENT_NOT_FOUND"}

    오류는 main.py 의 전역 예외 핸들러가 처리하므로 여기서 try/except 를 쓰지 않습니다.
    """
    event = service.get_event_detail(db, event_id)  # 없으면 404 예외 발생 → 전역 핸들러 처리

    data = EventDetail(
        event_id=event.event_id,
        title=event.title,
        description=event.description,
        banner_image_url=event.banner_image_url,
        start_at=event.start_at,
        end_at=event.end_at,
        is_active=event.is_active,
        participant_count=len(event.participations),  # 참여 기록 수를 세어서 반환
    ).model_dump()

    return ApiResponse(success=True, data=data, message="이벤트 상세를 불러왔습니다.")


# ── 엔드포인트 3: 이벤트 참여 ────────────────────────────────────────────────────
@router.post("/{event_id}/participate", response_model=ApiResponse)
def participate(
    event_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),  # 현재 사용자 UUID (임시: 고정값)
):
    """
    이벤트 참여.

    POST /api/events/{event_id}/participate
    성공: {"success": true,  "data": {...}, "message": "참여 완료"}
    실패: {"success": false, "data": null,  "message": "...",
           "error_code": "ALREADY_PARTICIPATED" | "EVENT_ENDED" | "EVENT_NOT_FOUND"}

    프론트엔드는 error_code 값으로 분기 처리해야 합니다. message 로 분기하면 안 됩니다.
    """
    # service 에서 예외가 발생하면 main.py 의 전역 핸들러가 ApiResponse 형태로 변환합니다.
    participation = service.participate_event(db, event_id, user_id)

    data = ParticipationResult(
        event_id=participation.event_id,
        user_id=participation.user_id,
        participated_at=participation.participated_at,
    ).model_dump()

    return ApiResponse(success=True, data=data, message="이벤트 참여가 완료되었습니다.")
