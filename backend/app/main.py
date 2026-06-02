# =============================================================================
# backend/app/main.py
#
# [이 파일의 역할]
# FastAPI 앱의 시작점(entry point)입니다.
# - 앱 객체를 생성합니다.
# - 각 feature 의 router 를 등록합니다.
# - DB 테이블을 생성합니다.
# - 전역 예외 핸들러를 등록합니다.
#
# [서버 실행 방법]
# cd backend
# uvicorn app.main:app --reload
#
# 실행 후 브라우저에서 확인:
# - API 문서: http://localhost:8000/docs  (Swagger UI, 직접 테스트 가능)
# - 헬스체크: http://localhost:8000/health
# =============================================================================

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from app.core.database import Base, engine
from app.core.exception import AppError
from app.core.opensearch import create_indices_if_not_exists
from app.features.event.router import router as event_router
from app.features.asset.router import router as asset_router
from app.features.jwt_auth.router import router as jwt_auth_router
from app.features.recipients.router import router as recipients_router
from app.features.transfer.router import router as transfer_router
from app.features.voice.router import router as voice_register_router
from app.shared.voice.router import router as voice_router

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

    message = str(exc.detail) if not error_code else error_code

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
    logger.error(
        "[AppError] code=%s status=%s message=%s",
        exc.code,
        exc.status_code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.message,
            "code": exc.code,
        },
    )


# ── DB 테이블 생성 ──────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── 라우터 등록 ─────────────────────────────────────────────────────────────────
from app.core.config import settings as _settings

logger.info("[Startup] ASV_SERVER_URL = %s", _settings.ASV_SERVER_URL)

app.include_router(voice_router)
app.include_router(jwt_auth_router)
app.include_router(asset_router)
app.include_router(event_router)
app.include_router(voice_register_router)
app.include_router(recipients_router)
app.include_router(transfer_router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}
