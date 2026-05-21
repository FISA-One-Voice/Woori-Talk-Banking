# =============================================================================
# backend/app/features/event/service.py
#
# [이 파일의 역할]
# 이벤트 관련 비즈니스 로직을 모두 담당합니다.
# "비즈니스 로직"이란 실제 업무 규칙을 코드로 구현한 것입니다.
# 예: "이미 참여한 이벤트에는 다시 참여할 수 없다"
#
# [다른 파일과의 관계]
# ├─ router.py         → 이 파일의 함수를 호출합니다. (router 는 연결만, 처리는 service)
# └─ models/event.py   → Event, EventParticipation 클래스로 DB 를 조회·추가합니다.
#
# [이 파일에서 하지 않는 것]
# - HTTP 요청/응답 처리 (그건 router.py 의 일)
# - 데이터 형태 정의 (그건 schema.py 의 일)
# =============================================================================

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session  # DB 세션 타입 힌트용

from app.models.event import Event, EventParticipation


def get_event_list(db: Session) -> list[Event]:
    """
    활성화된 이벤트 전체 목록을 반환합니다.

    Args:
        db: 데이터베이스 세션 (database.py 의 get_db() 가 주입합니다)

    Returns:
        is_active=True 인 이벤트 목록, 최신순 정렬
    """
    return (
        db.query(Event)  # Event 테이블 전체를 대상으로
        .filter(Event.is_active == True)  # is_active 가 True 인 것만 필터링
        .order_by(Event.created_at.desc())  # 최신 이벤트가 위에 오도록 정렬
        .all()  # 조건에 맞는 모든 행을 리스트로 반환
    )


def get_event_detail(db: Session, event_id: str) -> Event:
    """
    특정 이벤트의 상세 정보를 반환합니다.

    Args:
        db: 데이터베이스 세션
        event_id: 조회할 이벤트 UUID

    Returns:
        해당 Event 객체

    Raises:
        HTTPException(404): 해당 event_id 의 이벤트가 없을 때
    """
    # .first() : 조건에 맞는 첫 번째 행을 반환, 없으면 None
    event = db.query(Event).filter(Event.event_id == event_id).first()

    # 이벤트가 없으면 404 오류를 발생시킵니다.
    # detail={"error": "ERROR_CODE"} 형태로 오류 코드를 포함합니다.
    # main.py 의 전역 예외 핸들러가 이 형태를 표준 ApiResponse 로 변환합니다.
    if event is None:
        raise HTTPException(status_code=404, detail={"error": "EVENT_NOT_FOUND"})

    return event


def participate_event(db: Session, event_id: str, user_id: str) -> EventParticipation:
    """
    이벤트 참여를 처리합니다.

    3단계 검증을 순서대로 통과해야만 참여 기록이 저장됩니다:
    1. 이벤트가 존재하는가?
    2. 이벤트가 아직 진행 중인가?
    3. 이미 참여한 적이 있는가?

    Args:
        db: 데이터베이스 세션
        event_id: 참여할 이벤트 UUID
        user_id: 참여하는 사용자 UUID

    Returns:
        생성된 EventParticipation 객체

    Raises:
        HTTPException(404): 이벤트가 없을 때
        HTTPException(409): 이벤트가 종료되었을 때
        HTTPException(409): 이미 참여한 이벤트일 때
    """
    # 1단계: 이벤트 존재 여부 확인
    # 없으면 get_event_detail 내부에서 HTTPException(404) 가 발생합니다.
    event = get_event_detail(db, event_id)

    # 2단계: 이벤트 기간 확인
    # end_at 이 지났으면 참여 불가
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now > event.end_at:
        raise HTTPException(status_code=409, detail={"error": "EVENT_ENDED"})

    # 3단계: 중복 참여 확인
    # 같은 user_id + 같은 event_id 조합이 이미 있는지 검사합니다.
    already_joined = (
        db.query(EventParticipation)
        .filter(
            EventParticipation.event_id == event_id,
            EventParticipation.user_id == user_id,
        )
        .first()  # 하나라도 있으면 중복
    )

    if already_joined is not None:
        raise HTTPException(status_code=409, detail={"error": "ALREADY_PARTICIPATED"})

    # 검증 통과 → 참여 기록 생성
    participation = EventParticipation(event_id=event_id, user_id=user_id)
    db.add(participation)  # 세션에 추가 (아직 DB에 저장 안 됨)
    db.commit()  # DB 에 실제로 저장 (이 시점에 INSERT 쿼리가 실행됩니다)
    db.refresh(participation)  # DB 에서 최신 상태를 다시 읽어옴 (UUID 등 반영)

    return participation
