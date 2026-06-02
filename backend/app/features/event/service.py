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
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

KST = timezone(timedelta(hours=9))

from app.core.exception import EventNotFoundError, AlreadyParticipatedError
from app.models.event import Event, EventParticipation
from app.features.event.schema import EventListResponse, EventResponse


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
        raise EventNotFoundError(
            code="INVALID_EVENT_ID",
            message="유효하지 않은 이벤트 ID 형식입니다.",
            status_code=404,
        )


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
    now = datetime.now(KST).replace(tzinfo=None)
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


def get_event_detail(db: Session, event_id: str, user_id: str | None = None) -> EventResponse:
    """특정 이벤트의 상세 정보를 반환합니다.

    Args:
        db: SQLAlchemy DB 세션.
        event_id: 조회할 이벤트의 UUID 문자열.
        user_id: JWT에서 추출한 사용자 ID (선택). 있으면 has_participated 를 실제 값으로 반환.

    Returns:
        EventResponse: 이벤트 상세 정보. has_participated 포함.

    Raises:
        EventNotFoundError: event_id 형식이 UUID가 아니거나 이벤트가 없는 경우.
    """
    _validate_event_id(event_id)
    now = datetime.now(KST).replace(tzinfo=None)
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
        raise EventNotFoundError(
            code="EVENT_NOT_FOUND",
            message="이벤트를 찾을 수 없습니다.",
            status_code=404,
        )

    # 로그인 사용자의 참여 여부 확인
    has_participated = False
    if user_id:
        has_participated = (
            db.query(EventParticipation)
            .filter(
                EventParticipation.event_id == event_id,
                EventParticipation.user_id == user_id,
            )
            .first()
        ) is not None

    response = EventResponse.model_validate(event)
    return response.model_copy(update={"has_participated": has_participated})


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
        AlreadyParticipatedError: 이미 참여한 경우.
    """
    _validate_event_id(event_id)
    now = datetime.now(KST).replace(tzinfo=None)
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
        raise EventNotFoundError(
            code="EVENT_NOT_FOUND",
            message="이벤트를 찾을 수 없습니다.",
            status_code=404,
        )

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
        raise AlreadyParticipatedError(
            code="ALREADY_PARTICIPATED",
            message="이미 참여한 이벤트입니다.",
            status_code=409,
        )

    # 참여 기록 생성
    participation = EventParticipation(event_id=event_id, user_id=user_id)
    db.add(participation)
    db.commit()
    db.refresh(participation)

    return {"participation_id": participation.participation_id}


def get_events_tts_text(db: Session) -> str:
    """이벤트 목록을 TTS 친화적 문자열로 반환합니다.

    AI 에이전트 tool에서 호출합니다. 마크다운 없이 한국어 자연어로 반환합니다.

    Args:
        db: SQLAlchemy DB 세션.

    Returns:
        TTS로 읽힐 자연어 문자열.
    """
    result = get_active_events(db)
    events = result.events

    if not events:
        return "현재 진행 중인 이벤트가 없습니다."

    count_kor = _to_korean_count(len(events))
    titles = [f"{_ordinal(i + 1)}, {e.title}" for i, e in enumerate(events)]
    titles_str = ". ".join(titles)

    return f"현재 진행 중인 이벤트는 {count_kor}입니다. {titles_str}."


def _to_korean_count(n: int) -> str:
    """숫자를 '~개' 형태의 한국어로 변환합니다."""
    korean = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"]
    if 1 <= n <= 10:
        return f"{korean[n]} 개"
    return f"{n}개"


def _ordinal(n: int) -> str:
    """순서를 한국어로 변환합니다."""
    ordinals = ["", "첫 번째", "두 번째", "세 번째", "네 번째", "다섯 번째"]
    if 1 <= n <= 5:
        return ordinals[n]
    return f"{n}번째"
