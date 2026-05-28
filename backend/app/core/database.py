# =============================================================================
# backend/app/core/database.py
#
# [이 파일의 역할]
# 데이터베이스와의 연결을 설정하고 세션(연결 객체)을 제공합니다.
# "세션"이란 DB에 쿼리를 보내고 결과를 받는 하나의 연결 통로입니다.
#
# [다른 파일과의 관계]
# ├─ config.py         → DATABASE_URL 값을 가져와서 어떤 DB에 연결할지 결정합니다.
# ├─ models/event.py   → Base 클래스를 가져가서 테이블 정의에 상속합니다.
# └─ features/event/   → get_db() 함수를 통해 DB 세션을 주입받습니다.
# =============================================================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


# SQLite 전용 옵션: SQLite 는 기본적으로 멀티스레드를 허용하지 않습니다.
# check_same_thread=False 로 이 제한을 해제해야 FastAPI 가 정상 작동합니다.
# PostgreSQL 사용 시에는 이 옵션이 자동으로 무시되니 그냥 두어도 됩니다.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# DB 엔진: 실제 데이터베이스에 연결하는 핵심 객체
# DATABASE_URL 하나만 바꾸면 SQLite ↔ PostgreSQL 전환이 됩니다.
# pool_pre_ping=True: Aiven 등 클라우드 DB에서 유휴 연결을 강제로 끊었을 때 발생하는 OperationalError 방지
engine = create_engine(
    settings.database_url, connect_args=connect_args, pool_pre_ping=True
)

# 세션 팩토리: DB 연결(세션)을 생성하는 틀(공장)
# autocommit=False → db.commit() 을 직접 호출해야만 DB에 반영됩니다. (실수 방지)
# autoflush=False  → 명시적으로 flush() 하기 전까지 DB에 쿼리를 보내지 않습니다.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    모든 SQLAlchemy 모델이 상속받는 베이스 클래스.

    models/event.py 에서 "class Event(Base):" 형태로 사용합니다.
    Base 를 상속받은 클래스가 곧 데이터베이스 테이블이 됩니다.
    """


def get_db():
    """
    FastAPI 의존성 주입(Dependency Injection)용 DB 세션 제공 함수.

    라우터 함수 매개변수에 "db: Session = Depends(get_db)" 라고 쓰면
    FastAPI 가 요청마다 자동으로 이 함수를 호출해서 세션을 주입해줍니다.

    Yields:
        Session: 사용 가능한 DB 세션 객체

    사용 예시 (router.py):
        @router.get("/events")
        def list_events(db: Session = Depends(get_db)):
            return db.query(Event).all()

    중요: yield 구문은 요청 처리 중에는 세션을 제공하고,
          요청이 끝나면(성공/실패 모두) finally 블록에서 세션을 닫습니다.
          세션을 닫지 않으면 DB 연결이 계속 쌓여서 서버가 느려지거나 다운됩니다.
    """
    db = SessionLocal()  # 새 DB 세션 생성
    try:
        yield db  # 라우터 함수에 세션 전달
    finally:
        db.close()  # 요청 완료 후 반드시 세션 닫기
