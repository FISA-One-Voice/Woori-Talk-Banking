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

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.database import Base, engine
from app.core.exception import AppError
from app.features.event.router import router as event_router
from app.core.opensearch import create_indices_if_not_exists
# from app.features.event.router import router as event_router  # TODO: event 기능 재구현 후 주석 해제
from app.features.jwt_auth.router import router as jwt_auth_router
from app.features.voice.router import router as voice_register_router
from app.features.recipients.router import router as recipients_router
from app.shared.voice.router import router as voice_router

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


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """AppError 및 모든 서브클래스를 표준 ApiResponse 형식으로 변환합니다."""
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
app.include_router(voice_router)
app.include_router(jwt_auth_router)
app.include_router(asset_router)  # 자산 화면 — 잔액 조회 + 거래 내역 조회
app.include_router(event_router)
app.include_router(voice_register_router)
app.include_router(recipients_router)


# ── 헬스체크 ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """서버가 정상 실행 중인지 확인하는 엔드포인트."""
    return {"status": "ok"}
