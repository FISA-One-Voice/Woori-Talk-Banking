import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.database import Base, SessionLocal, engine
from app.features.event.router import router as event_router
from app.shared.voice.voice_router import router as voice_router
from app.models.event import Event


# ── FastAPI 앱 생성 ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Woori-Talk-Banking API",
    description="시각장애인을 위한 음성 뱅킹 서비스 백엔드",
    version="1.0.0",
)


# ── CORS 설정 ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 전역 예외 핸들러 ─────────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    """HTTPException 을 표준 ApiResponse 형식으로 변환합니다."""

    if isinstance(exc.detail, dict) and "error" in exc.detail:
        error_code = exc.detail["error"]
    else:
        error_code = None

    ERROR_MESSAGES: dict[str, str] = {
        "EVENT_NOT_FOUND": "이벤트를 찾을 수 없습니다.",
        "ALREADY_PARTICIPATED": "이미 참여한 이벤트입니다.",
        "EVENT_ENDED": "종료된 이벤트입니다.",
        "STT_FAILED": "음성 변환에 실패했습니다.",
        "VOICE_AUDIO_TOO_LONG": "음성은 60초를 초과할 수 없습니다.",
        "VOICE_AUDIO_TOO_LARGE": "음성 파일 크기가 10 MB를 초과합니다.",
        "VOICE_AUDIO_INVALID_FORMAT": "지원하지 않는 오디오 형식입니다.",
        "TTS_SPEED_OUT_OF_RANGE": "TTS 속도는 0.25 ~ 4.0 범위여야 합니다.",
        "SERVICE_UNAVAILABLE": "외부 서비스에 일시적인 문제가 발생했습니다.",
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """Pydantic 요청 검증 오류를 표준 ApiResponse 형식으로 변환합니다."""
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


# ── DB 테이블 생성 ──────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)


# ── 샘플 데이터 추가 ────────────────────────────────────────────────────────────
def seed_sample_events() -> None:
    """이벤트 테이블이 비어 있으면 샘플 데이터를 삽입합니다."""
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


# ── 라우터 등록 ─────────────────────────────────────────────────────────────────
app.include_router(event_router)
app.include_router(voice_router)


# ── 헬스체크 ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """서버가 정상 실행 중인지 확인하는 엔드포인트."""
    return {"status": "ok"}
