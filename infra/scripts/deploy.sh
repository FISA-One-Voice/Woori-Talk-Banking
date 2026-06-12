#!/bin/bash
set -euo pipefail

REGION="ap-northeast-2"
SSM_PATH="/woori/prod"
WORKDIR="/home/ubuntu"
REPO_RAW="https://raw.githubusercontent.com/FISA-One-Voice/Woori-Talk-Banking/main"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "[deploy] ECR 로그인..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "[deploy] SSM Parameter Store → .env 재생성..."
aws ssm get-parameters-by-path \
  --path "${SSM_PATH}/" \
  --with-decryption \
  --region "$REGION" \
  --output json \
  --query 'Parameters[*].[Name,Value]' > /tmp/ssm_params.json

python3 -c "
import json
with open('/tmp/ssm_params.json') as f:
    params = json.load(f)
with open('/home/ubuntu/.env', 'w') as f:
    for name, value in params:
        key = name.rsplit('/', 1)[-1]
        if '\n' in value:
            value = '\"' + value.replace('\"', '\\\\\"') + '\"'
        f.write(f'{key}={value}\n')
print(f'[deploy] .env 생성 완료: {len(params)}개 변수')
"
rm -f /tmp/ssm_params.json

echo "[deploy] 최신 설정 파일 동기화..."
curl -fsSL "${REPO_RAW}/backend/docker-compose.yml" -o "${WORKDIR}/docker-compose.yml"
mkdir -p "${WORKDIR}/fluent-bit"
curl -fsSL "${REPO_RAW}/backend/fluent-bit/fluent-bit.conf" -o "${WORKDIR}/fluent-bit/fluent-bit.conf"
curl -fsSL "${REPO_RAW}/backend/fluent-bit/parsers.conf"    -o "${WORKDIR}/fluent-bit/parsers.conf"

echo "[deploy] 이미지 갱신..."
cd "$WORKDIR"
docker compose pull woori-backend

echo "[deploy] 컨테이너 재시작..."
docker compose up -d woori-backend node-exporter fluent-bit

echo "[deploy] 완료: $(docker inspect woori-backend --format='{{.Config.Image}}')"
