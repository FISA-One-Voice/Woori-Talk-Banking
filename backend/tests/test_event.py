# =============================================================================
# backend/tests/test_event.py
#
# [이 파일의 역할]
# Event 기능의 HTTP 통합 테스트입니다.
# 실제 DB(Aiven PostgreSQL)에 테스트 이벤트를 만들고,
# /events 엔드포인트를 호출해서 응답이 표준 형식을 따르는지 검증합니다.
#
# [테스트 케이스 목록]
# 1. 이벤트 목록 조회       → 200, events 배열 + total 반환
# 2. 비활성 이벤트 미노출   → is_active=False 이벤트는 목록에 없음
# 3. 이벤트 상세 조회       → 200, event_id + banner_image_url 포함
# 4. 없는 이벤트 조회       → 404, EVENT_NOT_FOUND
# 5. 이벤트 참여            → 200, participation_id 반환
# 6. 중복 참여              → 409, ALREADY_PARTICIPATED
# 7. 로그인 없이 참여 시도  → 401, 인증 오류
#
# [실행 방법]
#   cd backend
#   CRYPTO_NOOP=true pytest tests/test_event.py -v
# =============================================================================

from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.jwt_utils import create_access_token
from app.models.event import Event, EventParticipation
from app.models.user import User


# ── 테스트 데이터 상수 ──────────────────────────────────────────────────────────
TEST_PHONE = "010-0000-EVT1"
TEST_PIN = "123456"


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

def _make_event(
    db: Session,
    title: str,
    is_active: bool = True,
    banner_url: str | None = None,
    end_at: datetime | None = None,
) -> Event:
    """테스트용 이벤트를 DB에 직접 삽입합니다."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    event = Event(
        title=title,
        description=f"{title} 설명입니다.",
        banner_image_url=banner_url,
        is_active=is_active,
        start_at=now - timedelta(days=1),
        end_at=end_at if end_at is not None else now + timedelta(days=7),
    )
    db.add(event)
    db.commit()
    # NullPool 환경에서 commit 후 refresh 실패 시 세션 롤백 후 재조회
    try:
        db.refresh(event)
    except Exception:
        db.rollback()
        event = db.query(Event).filter(Event.title == title).first()
    return event


def _make_user(db: Session) -> User:
    """테스트용 사용자를 DB에 직접 삽입합니다."""
    pin_hash = bcrypt.hashpw(TEST_PIN.encode(), bcrypt.gensalt()).decode()
    user = User(
        name="테스트유저_event",
        phone=TEST_PHONE,
        pin_hash=pin_hash,
        embedding_vector=[0.0] * 192,  # DB vector 컬럼 차원 수와 일치
    )
    db.add(user)
    db.commit()
    # NullPool 환경에서 commit 후 refresh 실패 시 세션 롤백 후 재조회
    try:
        db.refresh(user)
    except Exception:
        db.rollback()
        user = db.query(User).filter(User.phone == TEST_PHONE).first()
    return user


def _cleanup(db: Session) -> None:
    """테스트 데이터를 삭제합니다."""
    cleanup_db = SessionLocal()
    try:
        # 참여 기록 먼저 삭제 (FK 제약)
        cleanup_db.query(EventParticipation).filter(
            EventParticipation.user_id.in_(
                cleanup_db.query(User.user_id).filter(User.phone == TEST_PHONE)
            )
        ).delete(synchronize_session=False)
        cleanup_db.query(Event).filter(Event.title.like("테스트_%")).delete(
            synchronize_session=False
        )
        cleanup_db.query(User).filter(User.phone == TEST_PHONE).delete()
        cleanup_db.commit()
    finally:
        cleanup_db.close()


# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup(db: Session):
    """각 테스트 실행 후 테스트 데이터를 삭제합니다."""
    yield
    _cleanup(db)


@pytest.fixture
def active_event(db: Session) -> Event:
    """활성 테스트 이벤트 (배너 URL 포함)."""
    return _make_event(
        db,
        title="테스트_활성이벤트",
        is_active=True,
        banner_url="https://example.com/banner.png",
    )


@pytest.fixture
def inactive_event(db: Session) -> Event:
    """비활성 테스트 이벤트."""
    return _make_event(db, title="테스트_비활성이벤트", is_active=False)


@pytest.fixture
def expired_event(db: Session) -> Event:
    """만료된 테스트 이벤트 (end_at이 과거).

    start_at = now - 2일, end_at = now - 1시간 으로 설정해
    end_at > start_at DB 제약을 만족하면서 이미 만료된 이벤트를 만듭니다.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return _make_event(
        db,
        title="테스트_만료이벤트",
        is_active=True,
        end_at=now - timedelta(hours=1),
    )


@pytest.fixture
def test_user(db: Session) -> User:
    """테스트 사용자."""
    return _make_user(db)


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """테스트 사용자의 JWT 인증 헤더."""
    token = create_access_token({"sub": str(test_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


# ── 테스트 케이스 ─────────────────────────────────────────────────────────────


class TestListEvents:
    """GET /events — 이벤트 목록 조회"""

    def test_list_events_success(self, client: TestClient, active_event: Event):
        """활성 이벤트가 목록에 포함됩니다."""
        res = client.get("/events")

        assert res.status_code == 200

        body = res.json()
        assert body["success"] is True

        data = body["data"]
        assert "events" in data
        assert "total" in data
        assert data["total"] >= 1

        # 생성한 이벤트가 목록에 있어야 함
        # event_id는 DB에서 UUID 객체로 반환되고, API는 str로 직렬화하므로 str로 비교
        ids = [e["event_id"] for e in data["events"]]
        assert str(active_event.event_id) in ids

    def test_inactive_event_not_in_list(
        self, client: TestClient, inactive_event: Event
    ):
        """비활성(is_active=False) 이벤트는 목록에 나오지 않습니다."""
        res = client.get("/events")

        assert res.status_code == 200

        ids = [e["event_id"] for e in res.json()["data"]["events"]]
        assert inactive_event.event_id not in ids

    def test_list_includes_banner_url(self, client: TestClient, active_event: Event):
        """이벤트 목록에 banner_image_url 필드가 포함됩니다."""
        res = client.get("/events")

        events = res.json()["data"]["events"]
        target = next(e for e in events if e["event_id"] == str(active_event.event_id))

        assert "banner_image_url" in target
        assert target["banner_image_url"] == "https://example.com/banner.png"


class TestExpiredEvent:
    """만료된 이벤트(end_at < now) 처리"""

    def test_expired_event_not_in_list(self, client: TestClient, expired_event: Event):
        """만료된 이벤트는 목록에 나오지 않습니다."""
        res = client.get("/events")

        assert res.status_code == 200
        ids = [e["event_id"] for e in res.json()["data"]["events"]]
        assert str(expired_event.event_id) not in ids

    def test_expired_event_detail_returns_404(
        self, client: TestClient, expired_event: Event
    ):
        """만료된 이벤트 ID로 상세 조회하면 404가 반환됩니다."""
        res = client.get(f"/events/{expired_event.event_id}")

        assert res.status_code == 404
        assert res.json()["code"] == "EVENT_NOT_FOUND"

    def test_participate_expired_event(
        self, client: TestClient, expired_event: Event, auth_headers: dict
    ):
        """만료된 이벤트에 참여 시도하면 404가 반환됩니다."""
        res = client.post(
            f"/events/{expired_event.event_id}/join",
            headers=auth_headers,
        )

        assert res.status_code == 404
        assert res.json()["code"] == "EVENT_NOT_FOUND"


class TestGetEventDetail:
    """GET /events/{event_id} — 이벤트 상세 조회"""

    def test_get_event_detail_success(self, client: TestClient, active_event: Event):
        """존재하는 이벤트 ID로 상세 조회하면 200이 반환됩니다."""
        res = client.get(f"/events/{active_event.event_id}")

        assert res.status_code == 200

        body = res.json()
        assert body["success"] is True

        data = body["data"]
        assert data["event_id"] == str(active_event.event_id)
        assert data["title"] == active_event.title
        assert "banner_image_url" in data

    def test_get_event_not_found(self, client: TestClient):
        """존재하지 않는 event_id → 404, EVENT_NOT_FOUND."""
        res = client.get("/events/non-existent-uuid-1234")

        assert res.status_code == 404

        body = res.json()
        assert body["success"] is False
        assert body["code"] == "EVENT_NOT_FOUND"

    def test_get_inactive_event_returns_404(
        self, client: TestClient, inactive_event: Event
    ):
        """비활성 이벤트 ID로 조회하면 404가 반환됩니다."""
        res = client.get(f"/events/{inactive_event.event_id}")

        assert res.status_code == 404
        assert res.json()["code"] == "EVENT_NOT_FOUND"


class TestJoinEvent:
    """POST /events/{event_id}/join — 이벤트 참여"""

    def test_participate_success(
        self, client: TestClient, active_event: Event, auth_headers: dict
    ):
        """로그인 사용자가 이벤트에 참여하면 participation_id가 반환됩니다."""
        res = client.post(
            f"/events/{active_event.event_id}/join",
            headers=auth_headers,
        )

        assert res.status_code == 200

        body = res.json()
        assert body["success"] is True
        assert "participation_id" in body["data"]
        assert body["data"]["participation_id"] != ""

    def test_participate_duplicate(
        self, client: TestClient, active_event: Event, auth_headers: dict
    ):
        """같은 이벤트에 두 번 참여하면 409, ALREADY_PARTICIPATED."""
        # 첫 번째 참여
        client.post(
            f"/events/{active_event.event_id}/join",
            headers=auth_headers,
        )

        # 두 번째 참여 시도
        res = client.post(
            f"/events/{active_event.event_id}/join",
            headers=auth_headers,
        )

        assert res.status_code == 409
        assert res.json()["code"] == "ALREADY_PARTICIPATED"

    def test_participate_without_auth(self, client: TestClient, active_event: Event):
        """로그인 없이 참여 시도하면 401이 반환됩니다."""
        res = client.post(f"/events/{active_event.event_id}/join")

        assert res.status_code == 401

    def test_participate_nonexistent_event(
        self, client: TestClient, auth_headers: dict
    ):
        """존재하지 않는 이벤트에 참여 시도하면 404가 반환됩니다."""
        res = client.post(
            "/events/non-existent-uuid-9999/join",
            headers=auth_headers,
        )

        assert res.status_code == 404
        assert res.json()["code"] == "EVENT_NOT_FOUND"
