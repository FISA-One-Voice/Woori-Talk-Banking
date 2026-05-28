"""ASV 서버 환경변수 관리 모듈.

# Design Ref: §3.1 — Pydantic Settings, 환경변수 단일 진입점
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """ASV 서버 환경변수 설정.

    .env 파일 또는 OS 환경변수에서 자동 로드됩니다.
    모든 변수는 대문자 환경변수명으로 재정의 가능합니다.

    Example:
        ASV_THRESHOLD=0.80 uvicorn main:app
    """

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    asv_threshold: float = 0.75
    """동일 화자 판별 코사인 유사도 임계값. 0.0~1.0 사이. 기본값 0.75."""

    model_name: str = "iic/speech_campplus_sv_zh_en_16k-common_advanced"
    """modelscope CAM++ 화자 인증 모델 ID."""

    model_cache_dir: str = "/app/model_cache"
    """모델 가중치 캐시 저장 경로. Docker 빌드 시 사전 다운로드 위치."""


settings = Settings()
