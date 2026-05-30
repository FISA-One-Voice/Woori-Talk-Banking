# =============================================================================
# backend/app/features/event/schema.py
#
# [이 파일의 역할]
# Event API가 주고받는 데이터 형식을 Pydantic 모델로 정의합니다.
#
# [DB 모델과의 차이]
# models/event.py  → SQLAlchemy 모델 (DB 테이블 구조)
# schema.py        → Pydantic 모델 (API 요청/응답 형식)
#
# 같은 데이터라도:
# - DB 모델: DB에 저장하기 위한 형식
# - 스키마:  API로 클라이언트에게 전달하기 위한 형식
# =============================================================================

from datetime import datetime

from pydantic import BaseModel, field_validator


class EventResponse(BaseModel):
    """이벤트 하나를 API 응답으로 반환할 때 사용하는 스키마.

    DB의 Event 객체를 이 형식으로 변환해서 JSON으로 전달합니다.
    """

    event_id: str
    title: str
    description: str | None
    banner_image_url: str | None  # 배너 이미지 URL (없으면 null)
    is_active: bool
    start_at: datetime
    end_at: datetime
    has_participated: bool = False  # 현재 사용자의 참여 여부 (토큰 없으면 False)

    # orm_mode(v1) → from_attributes(v2): SQLAlchemy 객체를 직접 변환 가능하게 함
    model_config = {"from_attributes": True}

    @field_validator("event_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: object) -> str:
        """DB가 UUID 객체로 반환할 때 str로 변환합니다.

        events 테이블의 event_id 컬럼이 PostgreSQL UUID 타입이면
        psycopg2가 Python UUID 객체로 반환합니다. str로 통일합니다.
        """
        return str(v)


class EventListResponse(BaseModel):
    """이벤트 목록 API 응답 스키마."""

    events: list[EventResponse]
    total: int  # 전체 이벤트 수 (페이지네이션 대비)
