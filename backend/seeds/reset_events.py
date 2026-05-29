# =============================================================================
# backend/seeds/reset_events.py
#
# [이 파일의 역할]
# 기존 이벤트를 전부 삭제하고, 목업 이벤트 3개만 새로 삽입합니다.
#
# [실행 방법]
#   cd backend
#   python seeds/reset_events.py
# =============================================================================

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from app.core.database import SessionLocal
from app.models.event import Event, EventParticipation


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


MOCK_EVENTS = [
    {
        "title": "우리 Talk 첫 이용 이벤트",
        "description": "보이스 뱅킹 첫 이용 시 1,000P 지급",
        "banner_image_url": None,
        "is_active": True,
        "start_at": _now() - timedelta(days=1),
        "end_at": _now() + timedelta(days=30),
    },
    {
        "title": "이달의 이체 수수료 면제",
        "description": "6월 모든 이체 수수료 무료",
        "banner_image_url": None,
        "is_active": True,
        "start_at": _now() - timedelta(days=3),
        "end_at": _now() + timedelta(days=20),
    },
    {
        "title": "신규 적금 우대금리 이벤트",
        "description": "신규 적금 가입 시 연 0.5% 우대금리 제공",
        "banner_image_url": None,
        "is_active": True,
        "start_at": _now() - timedelta(days=5),
        "end_at": _now() + timedelta(days=60),
    },
]


def reset():
    db = SessionLocal()
    try:
        # 1. 기존 참여 기록 전부 삭제 (FK 제약 먼저)
        deleted_p = db.query(EventParticipation).delete(synchronize_session=False)
        print(f"참여 기록 삭제: {deleted_p}건")

        # 2. 기존 이벤트 전부 삭제
        deleted_e = db.query(Event).delete(synchronize_session=False)
        print(f"기존 이벤트 삭제: {deleted_e}건\n")

        # 3. 새 목업 이벤트 삽입
        for data in MOCK_EVENTS:
            event = Event(**data)
            db.add(event)
            print(f"  삽입: {data['title']}")

        db.commit()
        print(f"\n완료! 총 {len(MOCK_EVENTS)}개 이벤트 등록됨")

    except Exception as e:
        db.rollback()
        print(f"\n오류 발생: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=== 이벤트 DB 초기화 + 재삽입 ===\n")
    reset()
