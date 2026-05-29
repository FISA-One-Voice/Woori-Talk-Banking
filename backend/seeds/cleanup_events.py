# =============================================================================
# backend/seeds/cleanup_events.py
#
# [이 파일의 역할]
# DB에 중복된 이벤트를 정리합니다.
# 같은 title 중 가장 최근에 생성된 것 하나만 남기고 나머지 삭제합니다.
#
# [실행 방법]
#   cd backend
#   python seeds/cleanup_events.py
# =============================================================================

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.event import Event, EventParticipation


def cleanup():
    db = SessionLocal()
    try:
        # 전체 이벤트 title 목록
        all_events = db.query(Event).order_by(Event.created_at.desc()).all()

        seen_titles = set()
        to_delete = []

        for event in all_events:
            if event.title in seen_titles:
                to_delete.append(event)
            else:
                seen_titles.add(event.title)

        if not to_delete:
            print("중복 이벤트 없음 — 정리 불필요")
            return

        print(f"중복 이벤트 {len(to_delete)}개 발견:\n")
        for e in to_delete:
            print(f"  삭제: [{e.event_id}] {e.title}")
            # 참여 기록 먼저 삭제 (FK 제약)
            db.query(EventParticipation).filter(
                EventParticipation.event_id == e.event_id
            ).delete(synchronize_session=False)
            db.delete(e)

        db.commit()
        print(f"\n완료! {len(to_delete)}개 삭제됨")

    except Exception as ex:
        db.rollback()
        print(f"오류: {ex}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup()
