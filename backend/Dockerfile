# ── Stage 1: Build ──────────────────────────────────────────────────────────
# gcc 등 빌드 도구로 Python 패키지 컴파일. 이 레이어는 최종 이미지에 포함되지 않음.
FROM python:3.11-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.prod.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim

# ffmpeg: 안드로이드 .m4a → .wav 변환 필수
# curl: HEALTHCHECK 헬스체크 명령용
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# builder 스테이지에서 컴파일된 패키지만 복사 (build-essential 제외)
COPY --from=builder /install /usr/local

WORKDIR /app

COPY ./app ./app

# Fluent Bit이 읽을 로그 디렉토리 생성 + 비루트 유저 (보안)
RUN mkdir -p /app/logs && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
