# Design Ref: §1.1 — Docker 이식성: 빌드 타임 모델 다운로드, 런타임 네트워크 의존성 제거
# Plan SC: NFR — Docker 빌드 시점에 모델 가중치 포함 / 포트 8000 노출

FROM python:3.11-slim

LABEL maintainer="SouthGiri <southgiri.lee@gmail.com>"
LABEL description="CAM++ 화자 인증(ASV) FastAPI 서버 — Woori-Talk-Banking"

# ── 시스템 의존성 ──────────────────────────────────────────────────────────────
# libsndfile1 : soundfile 패키지 필수 (T-02 해결책 — torchaudio TorchCodec 대체)
# git         : modelscope 모델 다운로드 내부 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python 의존성 설치 ─────────────────────────────────────────────────────────
# 1단계: torch / torchaudio — CPU 전용 설치 (이미지 크기 최소화: ~250 MB vs ~2.5 GB)
#        GPU 지원 필요 시: --index-url 제거 후 pip install torch torchaudio
RUN pip install --no-cache-dir \
    "torch>=2.2.0" \
    "torchaudio>=2.2.0" \
    --index-url https://download.pytorch.org/whl/cpu

# 2단계: Production 의존성 (pytest 등 테스트 의존성 제외)
# addict: modelscope[audio] 옵션 extras — pip install modelscope 만으로는 설치 안 됨
#         modelscope/utils/config.py 최상위 import → 미설치 시 pipeline import 즉시 실패
RUN pip install --no-cache-dir \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.29.0" \
    "pydantic-settings>=2.2.0" \
    "modelscope>=1.9.5" \
    "addict>=2.4.0" \
    "datasets>=4.0.0" \
    "Pillow>=9.0.0" \
    "numpy>=1.24.0" \
    "python-multipart>=0.0.9" \
    "soundfile>=0.12.0" \
    "simplejson>=3.19.0" \
    "sortedcontainers>=2.4.0"

# ── CAM++ 모델 빌드 타임 다운로드 ──────────────────────────────────────────────
# 빌드 시 modelscope에서 모델을 /app/model_cache 에 다운로드합니다.
# 빌드 완료 후 컨테이너는 오프라인으로 동작 (런타임 네트워크 의존성 없음).
# 빌드 환경에서 modelscope Hub 접속 가능해야 합니다.
#
# MODELSCOPE_CACHE: modelscope가 최우선으로 사용하는 캐시 경로.
# 이 값을 고정하면 빌드 타임·런타임이 동일 경로를 바라보므로
# 빌드 시 다운로드한 가중치를 런타임에서 그대로 사용합니다.
ENV MODELSCOPE_CACHE=/app/model_cache
ENV MODEL_CACHE_DIR=/app/model_cache
ENV MODEL_NAME=iic/speech_campplus_sv_zh_en_16k-common_advanced

RUN python -c "\
from modelscope.pipelines import pipeline; \
from modelscope.utils.constant import Tasks; \
print('>>> CAM++ 모델 다운로드 시작 (iic/speech_campplus_sv_zh_en_16k-common_advanced)...'); \
pipeline( \
    task=Tasks.speaker_verification, \
    model='iic/speech_campplus_sv_zh_en_16k-common_advanced', \
    model_revision='v1.0.0', \
    model_cache_dir='/app/model_cache', \
); \
print('>>> CAM++ 모델 다운로드 완료.')"

# ── 애플리케이션 코드 복사 ─────────────────────────────────────────────────────
COPY config.py model.py main.py ./

# ── 실행 환경 ──────────────────────────────────────────────────────────────────
# 환경변수 기본값 — docker run -e ASV_THRESHOLD=0.8 로 재정의 가능
ENV ASV_THRESHOLD=0.6404

# Plan SC: NFR — 포트 매핑 | 컨테이너 내부 8000 → EC2 호스트 8000
EXPOSE 8000

# uvicorn 실행 — 0.0.0.0 바인딩으로 컨테이너 외부 접근 허용
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
