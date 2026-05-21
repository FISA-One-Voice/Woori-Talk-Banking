# =============================================================================
# backend/app/core/config.py
#
# [이 파일의 역할]
# 앱 전체에서 사용하는 설정값(환경변수)을 한 곳에서 관리합니다.
# .env 파일에 적힌 값을 읽어서 Python 객체로 만들어줍니다.
#
# [다른 파일과의 관계]
# └─ database.py → 이 파일의 DATABASE_URL 값을 가져가서 DB 연결에 사용합니다.
#
# [사용법]
# 다른 파일에서: from app.core.config import settings
# 그 다음:       settings.DATABASE_URL  로 값을 읽습니다.
# =============================================================================

from pydantic_settings import BaseSettings  # 환경변수를 자동으로 읽어주는 라이브러리


class Settings(BaseSettings):
    """
    앱 설정 클래스.

    pydantic_settings 의 BaseSettings 를 상속받으면
    .env 파일 또는 시스템 환경변수에서 값을 자동으로 읽어옵니다.
    """

    # 데이터베이스 연결 주소
    # ─ 기본값(sqlite): PostgreSQL 없이도 바로 실행 가능한 로컬 파일 DB
    # ─ 배포 시 교체:   DATABASE_URL=postgresql://user:pw@host/dbname
    DATABASE_URL: str = "sqlite:///./woori_talk.db"

    # 실행 환경 구분 ("development" | "production")
    ENV: str = "development"

    # JWT 인증 설정
    JWT_SECRET_KEY: str = "supersecretkey-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        # 프로젝트 루트의 .env 파일을 자동으로 읽습니다.
        # .env 가 없어도 오류 없이 기본값을 사용합니다.
        env_file = ".env"
        extra = "ignore"  # .env 에 정의되지 않은 변수가 있어도 오류 없이 무시


# 싱글턴 패턴: 이 모듈을 import 하는 모든 파일이 같은 객체를 공유합니다.
# 매번 새 객체를 만들지 않아서 설정이 일관되게 유지됩니다.
settings = Settings()
