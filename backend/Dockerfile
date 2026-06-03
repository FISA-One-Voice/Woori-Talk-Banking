# Python 3.11 슬림 버전 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# ffmpeg 설치 로직
# 안드로이드 기기에서 녹음된 .m4a 파일을 백엔드에서 .wav로 변환하기 위해
# OS 레벨의 ffmpeg 프로그램 설치가 필수적입니다.
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 코드 복사
COPY ./app ./app

# 컨테이너 포트 8000번 개방
EXPOSE 8000

# FastAPI 서버 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
