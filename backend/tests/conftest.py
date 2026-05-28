# =============================================================================
# backend/tests/conftest.py
#
# [이 파일의 역할]
# tests/ 디렉터리 전체에서 공유되는 pytest 픽스처를 정의합니다.
#
# [실행 방법]
#   cd backend
#   CRYPTO_NOOP=true pytest tests/ -v
#
# 전제 조건:
#   - .env에 POSTGRES_* 또는 DATABASE_URL 설정 (Aiven PostgreSQL)
#   - Aiven에서 CREATE EXTENSION IF NOT EXISTS vector; 실행 완료
#
# ── scope 선택 이유 ────────────────────────────────────────────────────────────
# scope="module" : 테스트 파일 하나당 세션 1개를 공유합니다.
#   → test_models_crud.py처럼 test_user → test_account → test_transaction으로
#     이어지는 "연쇄 픽스처"가 같은 세션 안에서 SQLAlchemy 객체를 공유해야
#     하기 때문에 module scope가 필요합니다.
#
# scope="function"을 쓰면 어떻게 될까?
#   scope="module"인 test_user 픽스처가 scope="function"인 db에 의존하게 되어
#   pytest가 ScopeMismatch 에러를 발생시킵니다.
#   (규칙: 더 넓은 scope는 더 좁은 scope에 의존 불가)
# =============================================================================

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — Base.metadata에 모든 테이블 등록
from app.core.database import Base, SessionLocal, engine
from app.main import app


# ── DB 세션 ────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def db() -> Generator[Session, None, None]:
    """테스트용 DB 세션. 한 테스트 파일(모듈) 안에서 공유됩니다.

    테이블이 없으면 create_all로 생성하고, 세션을 열어 반환합니다.
    모듈 내 모든 테스트가 끝나면 세션을 닫습니다.
    (데이터 정리는 각 테스트 파일의 fixture가 담당합니다.)
    """
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── TestClient ─────────────────────────────────────────────────────────────────
# FastAPI 앱을 실제 서버 없이 코드에서 직접 호출하는 객체입니다.
# Swagger에서 버튼을 클릭하는 것과 동일한 동작을 코드로 재현합니다.
# scope="session": 전체 pytest 실행 중 한 번만 생성합니다.
@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """테스트용 FastAPI 클라이언트. 세션 전체에서 공유됩니다."""
    with TestClient(app) as c:
        yield c
