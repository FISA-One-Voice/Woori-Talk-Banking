# =============================================================================
# backend/app/features/event/service.py
#
# [이 파일의 역할]
# 이벤트 관련 비즈니스 로직을 담당합니다.
# - DB에서 활성화된 이벤트 목록을 조회합니다.
# - DB에서 특정 이벤트 상세 정보를 조회합니다.
# - 이벤트 참여 처리를 합니다.
#
# [다른 파일과의 관계]
# router.py → service.py 함수를 호출
# service.py → models/event.py (DB 테이블)을 사용
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exception import EventError
from app.models.event import Event, EventParticipation
from app.features.event.schema import EventListResponse, EventResponse


# ── 예외 클래스 정의 ─────────────────────────────────────────────────────────
# EventError(AppError)를 상속합니다. (스타일 가이드 §8.1 Level-1 패턴)
# main.py의 app_error_handler가 AppError 체인으로 자동 처리합니다.

class EventNotFoundError(EventError):
    """이벤트를 찾을 수 없을 때 발생합니다."""
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            code="EVENT_NOT_FOUND",
            message="이벤트를 찾을 수 없습니다.",
        )


class AlreadyParticipatedException(EventError):
    """이미 참여한 이벤트에 다시 참여할 때 발생합니다."""
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            code="ALREADY_PARTICIPATED",
            message="이미 참여한 이벤트입니다.",
        )


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _validate_event_id(event_id: str) -> None:
    """event_id 가 유효한 UUID 형식인지 검증합니다.

    PostgreSQL UUID 컬럼에 잘못된 형식의 문자열을 보내면 DataError가 발생합니다.
    DB 호출 전에 미리 검증해서 EventNotFoundError(404)로 처리합니다.

    Raises:
        EventNotFoundError: event_id 가 UUID 형식이 아닌 경우.
    """
    try:
        uuid.UUID(event_id)
    except ValueError:
        raise EventNotFoundError()


# ── 서비스 함수 ───────────────────────────────────────────────────────────────

def get_active_events(db: Session) -> EventListResponse:
    """활성화된 이벤트 목록을 반환합니다.

    is_active=True 인 이벤트만 조회하며,
    최신 이벤트가 먼저 나오도록 start_at 내림차순 정렬합니다.

    Args:
        db: SQLAlchemy DB 세션 (router에서 Depends(get_db)로 주입).

    Returns:
        EventListResponse: 이벤트 목록과 전체 개수.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = (
        db.query(Event)
        .filter(Event.is_active == True, Event.end_at >= now)  # noqa: E712
        .order_by(Event.start_at.desc())
        .all()
    )

    return EventListResponse(
        events=[EventResponse.model_validate(e) for e in events],
        total=len(events),
    )


def get_event_detail(db: Session, event_id: str) -> EventResponse:
    """특정 이벤트의 상세 정보를 반환합니다.

    Args:
        db: SQLAlchemy DB 세션.
        event_id: 조회할 이벤트의 UUID 문자열.

    Returns:
        EventResponse: 이벤트 상세 정보.

    Raises:
        EventNotFoundError: event_id 형식이 UUID가 아니거나 이벤트가 없는 경우.
    """
    _validate_event_id(event_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    event = (
        db.query(Event)
        .filter(
            Event.event_id == event_id,
            Event.is_active == True,  # noqa: E712
            Event.end_at >= now,
        )
        .first()
    )

    if not event:
        raise EventNotFoundError()

    return EventResponse.model_validate(event)


def participate_event(db: Session, event_id: str, user_id: str) -> dict:
    """이벤트에 참여 처리합니다.

    Args:
        db: SQLAlchemy DB 세션.
        event_id: 참여할 이벤트 UUID.
        user_id: JWT에서 추출한 사용자 UUID.

    Returns:
        {"participation_id": str}: 생성된 참여 기록 ID.

    Raises:
        EventNotFoundError: event_id 형식이 UUID가 아니거나 이벤트가 없는 경우.
        AlreadyParticipatedException: 이미 참여한 경우.
    """
    _validate_event_id(event_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # 이벤트 존재 여부 확인
    event = (
        db.query(Event)
        .filter(
            Event.event_id == event_id,
            Event.is_active == True,  # noqa: E712
            Event.end_at >= now,
        )
        .first()
    )
    if not event:
        raise EventNotFoundError()

    # 중복 참여 확인
    existing = (
        db.query(EventParticipation)
        .filter(
            EventParticipation.event_id == event_id,
            EventParticipation.user_id == user_id,
        )
        .first()
    )
    if existing:
        raise AlreadyParticipatedException()

    # 참여 기록 생성
    participation = EventParticipation(event_id=event_id, user_id=user_id)
    db.add(participation)
    db.commit()
    db.refresh(participation)

    return {"participation_id": participation.participation_id}
