# =============================================================================
# backend/app/main.py
#
# [이 파일의 역할]
# FastAPI 앱의 시작점(entry point)입니다.
# - 앱 객체를 생성합니다.
# - 각 feature 의 router 를 등록합니다.
# - DB 테이블을 생성합니다.
# - 전역 예외 핸들러를 등록합니다.
# - 테스트용 샘플 데이터를 추가합니다.
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
from datetime import datetime, timedelta, timezone

from app.core.logging_config import setup_logging

setup_logging()

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from app.core.database import Base, engine
from app.core.exception import AppError
from app.features.analytics.router import router as analytics_router
from app.features.asset.router import router as asset_router
from app.features.auto_transfer.router import router as auto_transfer_router
from app.features.client_errors.router import router as client_errors_router
from app.features.event.router import router as event_router
from app.features.jwt_auth.router import router as jwt_auth_router
from app.features.recipients.router import router as recipients_router
from app.features.transfer.router import router as transfer_router
from app.features.voice.router import router as voice_register_router
from app.shared.voice.router import router as voice_router

from app.core.config import settings as _settings

# ── FastAPI 앱 생성 ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Woori-Talk-Banking API",
    description="시각장애인을 위한 음성 뱅킹 서비스 백엔드",
    version="1.0.0",
)


# ── CORS 설정 ───────────────────────────────────────────────────────────────────
# CORS(Cross-Origin Resource Sharing): 프론트엔드(다른 주소)에서 이 서버로
# API 요청을 보낼 수 있도록 허용하는 설정입니다.
# 개발 중에는 모든 출처("*")를 허용합니다. 배포 시 실제 도메인으로 교체하세요.

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.ALLOWED_ORIGINS,
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
            "code": "INVALID_REQUEST",
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    from app.core.middleware import _extract_feature

    logger.error(
        "app_error",
        extra={
            "event": "app_error",
            "code": exc.code,
            "status_code": exc.status_code,
            "error_message": exc.message,
            "feature": _extract_feature(request.url.path),
        },
    )
    app_error_total.labels(code=exc.code).inc()
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
# 각 feature 의 router 를 앱에 등록합니다.
# 새 화면(feature)을 추가할 때마다 이 파일에 두 줄씩 추가합니다:
# from app.features.{name}.router import router as {name}_router
# app.include_router({name}_router)
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.metrics import app_error_total, auto_transfer_scheduler_runs_total
from app.core.middleware import RequestLoggingMiddleware

Instrumentator().instrument(app).expose(app)
app.add_middleware(RequestLoggingMiddleware)

logger.info("[Startup] ASV_SERVER_URL = %s", _settings.ASV_SERVER_URL)

app.include_router(voice_router)
app.include_router(jwt_auth_router)
app.include_router(asset_router)  # 자산 화면 — 잔액 조회 + 거래 내역 조회
app.include_router(analytics_router)  # 지출 분석 리포트
app.include_router(event_router)
app.include_router(voice_register_router)
app.include_router(recipients_router)
app.include_router(auto_transfer_router)
app.include_router(transfer_router)
app.include_router(client_errors_router)


# ── 헬스체크 ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """서버가 정상 실행 중인지 확인하는 엔드포인트."""
    return {"status": "ok"}


from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.features.auto_transfer.service import run_due_auto_transfers

scheduler = BackgroundScheduler()


@app.on_event("startup")
def start_scheduler():
    def job() -> None:
        job_id = (
            f"auto_transfer_{datetime.now(timezone(timedelta(hours=9))).isoformat()}"
        )
        db = SessionLocal()
        try:
            run_due_auto_transfers(db, user_id=None)
            logger.info(
                "auto_transfer_executed",
                extra={
                    "event": "auto_transfer_executed",
                    "job_id": job_id,
                    "status": "success",
                },
            )
        except Exception as e:
            logger.error(
                "auto_transfer_executed",
                extra={
                    "event": "auto_transfer_executed",
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                },
            )
            auto_transfer_scheduler_runs_total.labels(status="failed").inc()
        else:
            auto_transfer_scheduler_runs_total.labels(status="success").inc()
        finally:
            db.close()

    scheduler.add_job(job, "cron", hour=14, minute=30)  # 매일 14:30 실행
    scheduler.start()


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()


# ── Redis Checkpointer (멀티 워커 LangGraph 세션 공유) ──────────────────────────
# REDIS_URL이 설정된 경우 AsyncRedisSaver로 그래프를 초기화한다.
# 미설정 시 _get_graph()의 MemorySaver 폴백이 동작하므로 단일 워커 환경은 무변경.

_redis_saver_cm = None


@app.on_event("startup")
async def startup_redis_graph():
    """Redis checkpointer를 초기화하고 LangGraph 그래프를 빌드한다."""
    global _redis_saver_cm
    if not _settings.REDIS_URL:
        logger.info("[Startup] REDIS_URL 미설정 — MemorySaver 폴백")
        return
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        from app.shared.voice.service import initialize_graph

        _redis_saver_cm = AsyncRedisSaver.from_conn_string(_settings.REDIS_URL)
        checkpointer = await _redis_saver_cm.__aenter__()
        await checkpointer.setup()
        initialize_graph(checkpointer)
        logger.info("[Startup] Redis checkpointer 초기화 완료: %s", _settings.REDIS_URL)
    except Exception:
        logger.exception("[Startup] Redis 연결 실패 — MemorySaver 폴백")
        _redis_saver_cm = None


@app.on_event("shutdown")
async def shutdown_redis_graph():
    """Redis 연결을 해제한다."""
    global _redis_saver_cm
    if _redis_saver_cm is not None:
        await _redis_saver_cm.__aexit__(None, None, None)
        _redis_saver_cm = None
