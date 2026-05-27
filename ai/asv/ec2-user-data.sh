#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# EC2 User Data — ASV Server (CAM++ Speaker Verification)
# 인스턴스 최초 시작 시 1회 자동 실행됩니다.
#
# Docker Hub 이미지: southgiri/asv-cpu
# https://hub.docker.com/repository/docker/southgiri/asv/general
#
# 전제 조건:
#   - AMI: Ubuntu 24.04 LTS
#   - 인스턴스 타입: t3.medium 이상 권장 (CAM++ 모델 추론)
#   - 보안 그룹: 8000 포트 — 메인 백엔드 인스턴스 IP에서만 인바운드 허용
#   - 인터넷 게이트웨이 / NAT: Docker Hub 이미지 pull 필요
#
# 실행 로그: /var/log/asv-user-data.log
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
exec > >(tee /var/log/asv-user-data.log) 2>&1

echo "========================================"
echo " ASV Server — EC2 User Data 시작"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# ── 1. 시스템 패키지 업데이트 ─────────────────────────────────────────────────
echo "[1/4] 시스템 업데이트..."
apt-get update -y
apt-get upgrade -y

# ── 2. Docker 설치 (공식 Docker apt 저장소) ───────────────────────────────────
echo "[2/4] Docker 설치..."

# HTTPS 전송 및 GPG 키 관련 패키지
apt-get install -y ca-certificates curl

# Docker 공식 GPG 키 등록
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Docker apt 저장소 추가
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu
echo "  Docker 버전: $(docker --version)"

# ── 3. Docker Hub에서 이미지 Pull ─────────────────────────────────────────────
echo "[3/4] Docker Hub에서 이미지 pull..."
# southgiri/asv:1.0 — 모델 가중치 포함 (빌드타임 다운로드 완료된 이미지)
docker pull southgiri/asv:1.0
echo "  Pull 완료: southgiri/asv:1.0"

# ── 4. ASV 컨테이너 실행 ──────────────────────────────────────────────────────
echo "[4/4] ASV 컨테이너 시작..."

# 기존 컨테이너 제거 (재실행 시 중복 방지)
docker rm -f asv-server 2>/dev/null || true

docker run -d \
  --name asv-server \
  --restart unless-stopped \
  -p 8000:8000 \
  southgiri/asv:1.0

echo "  컨테이너 시작 완료 (포트 매핑: 8000 → 8000)"

# ── Health Check ──────────────────────────────────────────────────────────────
echo "서버 기동 대기 중..."
for i in $(seq 1 12); do
  sleep 5
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || true)
  if [ "$STATUS" = "200" ]; then
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "unknown")
    echo "========================================"
    echo " ✅ ASV 서버 기동 완료"
    echo " Health: http://${PUBLIC_IP}:8000/health"
    echo " Docs:   http://${PUBLIC_IP}:8000/docs"
    echo " Image:  southgiri/asv:1.0"
    echo " ASV_THRESHOLD=0.6404"
    echo " $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    exit 0
  fi
  echo "  대기 중... (${i}/12, HTTP=${STATUS})"
done

echo "⚠️  Health Check 60초 내 응답 없음 — 로그 확인: docker logs asv-server"
