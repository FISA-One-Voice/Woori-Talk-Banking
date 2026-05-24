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

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.database import Base, SessionLocal, engine
from app.features.event.router import router as event_router
from app.models.event import Event  # 테이블 생성 전에 모델을 import 해야 합니다
from app.models.user import User
from app.core.exceptions import AppError


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
# service.py 에서 HTTPException 을 raise 하면 이 핸들러가 받아서
# CLAUDE.md 표준 응답 형식(ApiResponse)으로 변환합니다.
#
# 이 핸들러가 없으면 FastAPI 기본 오류 형식이 반환됩니다:
# {"detail": {"error": "ALREADY_PARTICIPATED"}}  ← 우리 표준이 아님
@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    """HTTPException 을 표준 ApiResponse 형식으로 변환합니다."""

    # detail 이 {"error": "ERROR_CODE"} 형태인지 확인합니다.
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        error_code = exc.detail["error"]
    else:
        error_code = None

    # 오류 코드 → 사용자 안내 메시지 변환표
    # 프론트엔드는 message 가 아닌 error_code 로 분기해야 합니다.
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


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False, 
            "data": None, 
            "message": exc.message, 
            "code": exc.code
        }
    )

@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "success": False, 
            "data": None, 
            "message": "서버 내부 오류", 
            "code": "INTERNAL_ERROR"
        }
    )


# ── DB 테이블 생성 ──────────────────────────────────────────────────────────────
# import 된 모든 모델(Base 를 상속한 클래스)의 테이블을 DB 에 생성합니다.
# 테이블이 이미 존재하면 건너뜁니다. (덮어쓰지 않습니다)
Base.metadata.create_all(bind=engine)


# ── 샘플 데이터 추가 ────────────────────────────────────────────────────────────
# 팀원이 서버를 처음 실행했을 때 바로 테스트할 수 있도록
# 이벤트 테이블이 비어 있으면 샘플 이벤트 3개를 자동으로 추가합니다.
def seed_sample_events() -> None:
    """이벤트 테이블이 비어 있으면 샘플 데이터를 삽입합니다."""
    db = SessionLocal()
    try:
        if db.query(Event).count() > 0:
            return  # 이미 데이터가 있으면 중복 삽입 방지

        # DB 저장용 naive datetime (timezone 정보 제거)
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


seed_sample_events()


# ── 라우터 등록 ─────────────────────────────────────────────────────────────────
# 각 feature 의 router 를 앱에 등록합니다.
# 새 화면(feature)을 추가할 때마다 이 파일에 두 줄씩 추가합니다:
# from app.features.{name}.router import router as {name}_router
# app.include_router({name}_router)
app.include_router(event_router)
from app.features.jwt_auth.router import router as jwt_auth_router
app.include_router(jwt_auth_router)


# ── 헬스체크 ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """서버가 정상 실행 중인지 확인하는 엔드포인트."""
    return {"status": "ok"}
