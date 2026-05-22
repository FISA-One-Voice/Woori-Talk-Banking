import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.database import Base, SessionLocal, engine
from app.features.event.router import router as event_router
from app.features.account.router import router as account_router
from app.models.event import Event
from app.models.account import Account
from app.models.user import User


app = FastAPI(
    title="Woori-Talk-Banking API",
    description="시각장애인을 위한 음성 뱅킹 서비스 백엔드",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        error_code = exc.detail["error"]
    else:
        error_code = None

    ERROR_MESSAGES: dict[str, str] = {
        "EVENT_NOT_FOUND": "이벤트를 찾을 수 없습니다.",
        "ALREADY_PARTICIPATED": "이미 참여한 이벤트입니다.",
        "EVENT_ENDED": "종료된 이벤트입니다.",
        "ACCOUNT_NOT_FOUND": "계좌를 찾을 수 없습니다.",
    }

    message = (
        ERROR_MESSAGES.get(error_code, str(exc.detail))
        if error_code
        else str(exc.detail)
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": message,
            "error_code": error_code,
        },
    )


Base.metadata.create_all(bind=engine)


def seed_sample_events() -> None:
    db = SessionLocal()
    try:
        if db.query(Event).count() > 0:
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        sample_events = [
            Event(
                event_id=str(uuid.uuid4()),
                title="신규 가입 환영 이벤트",
                description=(
                    "우리톡뱅킹에 처음 가입하신 고객님께 드리는 특별 혜택입니다. "
                    "이벤트 참여 시 계좌 개설 수수료가 면제됩니다."
                ),
                start_at=now - timedelta(days=1),
                end_at=now + timedelta(days=30),
                is_active=True,
            ),
            Event(
                event_id=str(uuid.uuid4()),
                title="첫 이체 캐시백 이벤트",
                description=(
                    "첫 이체를 완료하신 고객님께 캐시백 500원을 지급합니다. "
                    "이체 완료 후 영업일 기준 3일 이내에 지급됩니다."
                ),
                start_at=now,
                end_at=now + timedelta(days=14),
                is_active=True,
            ),
            Event(
                event_id=str(uuid.uuid4()),
                title="음성 인증 등록 완료 이벤트",
                description=(
                    "음성 보안 등록을 완료하신 고객님께"
                    " 편의점 상품권 1,000원을 드립니다."
                ),
                start_at=now - timedelta(days=10),
                end_at=now + timedelta(days=5),
                is_active=True,
            ),
        ]
        db.add_all(sample_events)
        db.commit()
        print("✅ 샘플 이벤트 3개가 추가되었습니다.")
    finally:
        db.close()


def seed_sample_users() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            User.user_id == "00000000-0000-0000-0000-000000000001"
        ).first()
        if existing:
            return
        sample_user = User(
            user_id="00000000-0000-0000-0000-000000000001",
            name="테스트유저",
            phone="010-1234-5678",
        )
        db.add(sample_user)
        db.commit()
        print("✅ 샘플 유저 1명이 추가되었습니다.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ 유저 삽입 실패 (이미 존재할 수 있음): {e}")
    finally:
        db.close()


def seed_sample_accounts() -> None:
    db = SessionLocal()
    try:
        if db.query(Account).count() > 0:
            return
        import uuid as uuid_lib
        # DB에 실제 존재하는 user_id 사용
        REAL_USER_ID = "ff49c2a0-9b82-4c4f-9f61-d39930b16dd6"
        sample_accounts = [
            Account(
                account_id=str(uuid_lib.uuid4()),
                user_id=REAL_USER_ID,
                bank_name="우리은행",
                account_number="1002-123-456789",
                account_type="입출금",
                balance=1500000,
                alias="주거래 통장",
            ),
            Account(
                account_id=str(uuid_lib.uuid4()),
                user_id=REAL_USER_ID,
                bank_name="우리은행",
                account_number="1002-987-654321",
                account_type="저축",
                balance=5000000,
                alias="저축 통장",
            ),
        ]
        db.add_all(sample_accounts)
        db.commit()
        print("✅ 샘플 계좌 2개가 추가되었습니다.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ 계좌 삽입 실패: {e}")
    finally:
        db.close()
        
seed_sample_events()
seed_sample_users()
seed_sample_accounts()

app.include_router(event_router)
app.include_router(account_router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}