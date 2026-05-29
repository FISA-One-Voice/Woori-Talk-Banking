# =============================================================================
# backend/app/models/event.py
#
# [이 파일의 역할]
# 데이터베이스 테이블 구조를 Python 클래스로 정의합니다.
# 이 파일의 클래스 하나 = 데이터베이스 테이블 하나입니다.
#
# [다른 파일과의 관계]
# ├─ database.py           → Base 클래스를 가져와서 상속합니다.
# ├─ main.py               → Base.metadata.create_all() 로 실제 테이블을 생성합니다.
# └─ features/event/service.py → 이 클래스로 DB 를 조회하고 데이터를 추가합니다.
# =============================================================================

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


KST = timezone(timedelta(hours=9))


def _now() -> datetime:
    """timezone-aware 없이 현재 KST 시각을 반환합니다. (SQLite/PostgreSQL 호환)"""
    return datetime.now(KST).replace(tzinfo=None)


class Event(Base):
    """
    이벤트 테이블 (DB 테이블명: events)

    각 행(row)이 이벤트 하나를 나타냅니다.
    Mapped[타입] = mapped_column(...)  형식으로 컬럼을 정의합니다.
    """

    __tablename__ = "events"

    # String(36) : UUID 를 문자열로 저장합니다. (예: "550e8400-e29b-41d4-a716-446655440000")
    # default=lambda: str(uuid.uuid4()) : 삽입 시 자동으로 새 UUID 를 생성합니다.
    event_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # String(200) : 최대 200자 문자열, nullable=False : 빈 값 불허
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # Text : 길이 제한 없는 긴 문자열. DB 스키마에서 not null 없으므로 nullable
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 배너 이미지 URL (선택 항목 — 없을 수 있음)
    banner_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 이벤트 활성 여부 (False 이면 목록에 표시 안 함)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 이벤트 시작/종료 시각 (DB 스키마 컬럼명: start_at / end_at)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 이 레코드가 DB 에 추가된 시각 (삽입 시 자동으로 현재 시각이 기록됩니다)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    # 관계(Relationship): 이 이벤트에 연결된 참여 기록 목록
    # 실제 DB 컬럼은 아니고, SQLAlchemy 가 JOIN 쿼리를 대신 처리해주는 편의 속성입니다.
    # event.participations 로 이 이벤트의 모든 참여 기록을 가져올 수 있습니다.
    participations: Mapped[list["EventParticipation"]] = relationship(
        "EventParticipation", back_populates="event"
    )


class EventParticipation(Base):
    """
    이벤트 참여 기록 테이블 (DB 테이블명: event_participations)

    어떤 사용자가 어떤 이벤트에 참여했는지 기록합니다.
    (user_id, event_id) 유니크 제약으로 중복 참여를 DB 레벨에서 차단합니다.
    """

    __tablename__ = "event_participations"

    # (user_id, event_id) 조합이 유일해야 합니다 (DB 레벨 중복 참여 방지)
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event"),)

    participation_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ForeignKey("events.event_id") : events 테이블의 event_id 컬럼을 참조합니다.
    # 존재하지 않는 event_id 는 DB 레벨에서 자동 차단됩니다.
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.event_id"), nullable=False
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )

    # 참여 시각 (삽입 시 자동으로 현재 시각이 기록됩니다)
    participated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, nullable=False
    )

    # 반대쪽 관계: 이 참여 기록이 어떤 이벤트에 속하는지
    # participation.event 로 해당 Event 객체를 바로 가져올 수 있습니다.
    event: Mapped["Event"] = relationship("Event", back_populates="participations")
