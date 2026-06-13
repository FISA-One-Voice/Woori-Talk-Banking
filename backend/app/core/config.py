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

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """앱 설정 클래스.

    BaseSettings 가 .env 파일과 os.environ 을 자동으로 읽어
    각 필드에 타입 변환 후 매핑합니다.
    """

    # 데이터베이스 연결 주소
    # ─ DATABASE_URL 이 직접 설정되어 있으면 그 값을 사용합니다.
    # ─ 없으면 POSTGRES_* 개별 변수로 자동 조합합니다.
    # ─ POSTGRES_* 도 없으면 SQLite 로컬 파일 DB 를 사용합니다.
    DATABASE_URL: str = ""

    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_DATABASE: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SSL_MODE: str = "require"
    POSTGRES_SSL_ROOT_CERT: str = ""

    # 실행 환경 구분 ("development" | "production")
    ENV: str = "development"

    # NAVER CLOVA Speech (STT)
    # ─ CLOVA_SECRET_KEY: 네이버 클라우드 플랫폼에서 발급받은 Secret Key
    # ─ CLOVA_URL:        STT 요청을 보낼 API 엔드포인트 (기본값: 한국어)
    CLOVA_SECRET_KEY: str = ""
    CLOVA_URL: str = "https://clovaspeech-gw.ncloud.com/recog/v1/stt?lang=Kor"

    # Azure Cognitive Services Text-to-Speech (TTS)
    # ─ AZURE_TTS_KEY:    Azure 포털에서 발급받은 구독 키
    # ─ AZURE_TTS_REGION: 리소스가 배포된 Azure 리전 (기본값: 한국 중부)
    AZURE_TTS_KEY: str = ""
    AZURE_TTS_REGION: str = "koreacentral"
    # AES-256-GCM 암호화 키 (base64url 인코딩된 32바이트)
    # 생성: python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    CRYPTO_KEY: str = ""

    # True 로 설정하면 encrypt/decrypt 가 no-op (평문 그대로 반환) — 개발·테스트 전용
    # CRYPTO_NOOP: bool = False
    CRYPTO_NOOP: bool = True

    @property
    def database_url(self) -> str:
        """실제 사용할 DATABASE_URL 을 반환합니다.

        우선순위:
          1. DATABASE_URL 환경변수가 직접 설정된 경우
          2. POSTGRES_HOST 등 개별 변수로 URL 을 조합하는 경우
          3. 둘 다 없으면 SQLite 로컬 파일 DB
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if self.POSTGRES_SSL_ROOT_CERT and "sslrootcert" not in url:
                url += f"&sslrootcert={self.POSTGRES_SSL_ROOT_CERT}"
            return url
        if self.POSTGRES_HOST:
            url = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
                f"?sslmode={self.POSTGRES_SSL_MODE}"
            )
            if self.POSTGRES_SSL_ROOT_CERT:
                url += f"&sslrootcert={self.POSTGRES_SSL_ROOT_CERT}"
            return url
        return "sqlite:///./woori_talk.db"

    # ── OpenSearch ──────────────────────────────────────────────────────────────
    # OPENSEARCH_HOST : Aiven 클러스터 호스트
    # OPENSEARCH_PORT : 포트 (Aiven 기본값 11916)
    # OPENSEARCH_USER / OPENSEARCH_PASSWORD : 클러스터 인증 정보
    # OPENSEARCH_USE_SSL : SSL 사용 여부 (Aiven 항상 True)
    # OPENSEARCH_CA_CERT : CA 인증서 경로 — 없으면 검증 비활성화 (로컬 개발용)
    OPENSEARCH_HOST: str = ""
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_USER: str = ""
    OPENSEARCH_PASSWORD: str = ""
    OPENSEARCH_USE_SSL: bool = True
    OPENSEARCH_CA_CERT: str = ""
    # OpenAI 에이전트 설정
    # ─ OPENAI_CHAT_API_KEY: OpenAI 플랫폼에서 발급받은 API 키
    # ─ OPENAI_MODEL:      Transfer·Asset 서브그래프용 (슬롯 추출, 복합 쿼리)
    # ─ OPENAI_MODEL_LITE: Supervisor 분류기·Consultation 서브그래프용 (단순 분류·RAG 응답)
    OPENAI_CHAT_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_MODEL_LITE: str = "gpt-4.1-nano"

    # JWT 인증 설정
    JWT_SECRET_KEY: str = "supersecretkey-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── ASV 화자 인증 서버 설정 (Issue #7, ai/asv/) ───────────────────────────────
    # ASV_SERVER_URL: CAM++ 기반 화자 인증 서버 주소 (POST /verify)
    #   로컬 개발: ai/asv/main.py 실행 시 포트 8000
    #   프로덕션: EC2 인스턴스 주소 (southgiri/asv:1.0 Docker 이미지)
    ASV_SERVER_URL: str = "http://localhost:8000"

    # ── 한국은행 API 키 ─────────────────────
    BOK_ECOS_API_KEY: str = ""

    # ── AWS S3 동의 음성 저장 (voice-consent-s3) ──────────────────────────────────
    # AWS_S3_BUCKET: 업로드 대상 버킷. 빈 문자열이면 업로드를 스킵한다.
    # AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: 비어있으면 EC2 IAM Role 자동 인식.
    # AWS_REGION: 버킷이 위치한 리전 (기본: 서울).
    AWS_S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"

    # ── CORS 허용 출처 ────────────────────────────────────────────────────────────
    # 개발: ["*"] (기본값)
    # 프로덕션 .env 예시: ALLOWED_ORIGINS=["https://api.woori-talk.site"]
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── LangSmith 트레이싱 (개발 전용 — 프로덕션에서는 미설정) ────────────────────────
    # .env에 LANGSMITH_* 형식으로 설정한다.
    # LangChain/LangGraph는 os.environ을 직접 읽으므로 model_post_init에서 반영한다.
    LANGSMITH_TRACING: str = ""
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = ""
    LANGSMITH_ENDPOINT: str = ""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        """LangSmith 환경변수 반영 + 프로덕션 위험 설정 fast-fail."""
        if self.LANGSMITH_TRACING:
            os.environ["LANGSMITH_TRACING"] = self.LANGSMITH_TRACING
        if self.LANGSMITH_API_KEY:
            os.environ["LANGSMITH_API_KEY"] = self.LANGSMITH_API_KEY
        if self.LANGSMITH_PROJECT:
            os.environ["LANGSMITH_PROJECT"] = self.LANGSMITH_PROJECT
        if self.LANGSMITH_ENDPOINT:
            os.environ["LANGSMITH_ENDPOINT"] = self.LANGSMITH_ENDPOINT

        if self.ENV == "production":
            if self.JWT_SECRET_KEY == "supersecretkey-change-me-in-production":
                raise ValueError(
                    "JWT_SECRET_KEY가 기본값입니다. "
                    ".env에서 교체하세요: "
                    'python -c "import secrets; print(secrets.token_hex(32))"'
                )


# 싱글턴 패턴: 이 모듈을 import 하는 모든 파일이 같은 객체를 공유합니다.
# 매번 새 객체를 만들지 않아서 설정이 일관되게 유지됩니다.
settings = Settings()
