import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.database import Base, SessionLocal, engine
from app.core.exception import AppError
from app.core.opensearch import create_indices_if_not_exists
from app.features.event.router import router as event_router
from app.features.asset.router import router as asset_router
from app.features.jwt_auth.router import router as jwt_auth_router
from app.models.event import Event
from app.shared.voice.router import router as voice_router

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
            "code": error_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(loc) for loc in first.get("loc", [])[1:])
    detail = first.get("msg", "입력값이 올바르지 않습니다.")
    message = f"{field}: {detail}" if field else detail

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "message": message,
            "error_code": "INVALID_REQUEST",
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.message,
            "code": exc.code,
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
    finally:
        db.close()


seed_sample_events()

app.include_router(event_router)
app.include_router(asset_router)
app.include_router(voice_router)
app.include_router(jwt_auth_router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}