# =============================================================================
# backend/seeds/seed_events.py
#
# [이 파일의 역할]
# 테스트용 이벤트 데이터를 DB에 삽입합니다.
#
# [실행 방법]
#   cd backend
#   python seeds/seed_events.py
#
# [주의]
# 같은 title의 이벤트가 이미 있으면 건너뜁니다. (중복 방지)
# =============================================================================

import sys
import os

# backend/ 폴더를 Python 경로에 추가 (app 모듈 import를 위해)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from app.core.database import SessionLocal
from app.models.event import Event


# ── 시드 데이터 ────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


SEED_EVENTS = [
    {
        "title": "봄맞이 적금 이벤트",
        "description": "적금 가입 시 우대금리 0.5% 제공",
        "banner_image_url": None,
        "is_active": True,
        "start_at": _now() - timedelta(days=3),
        "end_at": _now() + timedelta(days=30),
    },
    {
        "title": "첫 이체 캐시백",
        "description": "첫 이체 시 1,000P 지급",
        "banner_image_url": None,
        "is_active": True,
        "start_at": _now() - timedelta(days=1),
        "end_at": _now() + timedelta(days=60),
    },
    {
        "title": "친구 초대 보너스",
        "description": "5,000P 지급",
        "banner_image_url": None,
        "is_active": True,
        "start_at": _now() - timedelta(days=2),
        "end_at": _now() + timedelta(days=90),
    },
]


# ── 실행 ───────────────────────────────────────────────────────────────────────

def seed():
    db = SessionLocal()
    try:
        inserted = 0
        skipped = 0

        for data in SEED_EVENTS:
            # 같은 title이 이미 있으면 건너뜀
            exists = db.query(Event).filter(Event.title == data["title"]).first()
            if exists:
                print(f"  건너뜀 (이미 존재): {data['title']}")
                skipped += 1
                continue

            event = Event(**data)
            db.add(event)
            print(f"  삽입: {data['title']}")
            inserted += 1

        db.commit()
        print(f"\n완료! 삽입 {inserted}개 / 건너뜀 {skipped}개")

    except Exception as e:
        db.rollback()
        print(f"\n오류 발생: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("이벤트 시드 데이터 삽입 중...\n")
    seed()
