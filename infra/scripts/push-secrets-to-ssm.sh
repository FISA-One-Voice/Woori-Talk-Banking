#!/bin/bash
# 로컬 .env 파일을 AWS SSM Parameter Store에 SecureString으로 일괄 업로드
#
# 사용법:
#   ./infra/scripts/push-secrets-to-ssm.sh [.env 파일 경로]
#
# 예시:
#   ./infra/scripts/push-secrets-to-ssm.sh backend/.env.prod
#
# 사전 조건:
#   - AWS CLI 설치 및 로그인 (aws configure 또는 환경변수)
#   - SSM Parameter Store 쓰기 권한 (ssm:PutParameter)

set -euo pipefail

ENV_FILE="${1:-backend/.env.prod}"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"
SSM_PATH="/woori/prod"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: $ENV_FILE 파일이 없습니다."
  echo "사용법: $0 [.env 파일 경로]"
  exit 1
fi

echo "SSM Parameter Store 업로드 시작"
echo "  파일: $ENV_FILE"
echo "  경로: $SSM_PATH/"
echo "  리전: $REGION"
echo ""

COUNT=0
while IFS= read -r line || [[ -n "$line" ]]; do
  # 빈 줄, 주석(#) 건너뜀
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  # KEY=VALUE 형식이 아닌 줄 건너뜀
  [[ "$line" != *"="* ]] && continue

  key="${line%%=*}"
  value="${line#*=}"

  # 값 앞뒤 따옴표 제거
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  aws ssm put-parameter \
    --region "$REGION" \
    --name "$SSM_PATH/$key" \
    --value "$value" \
    --type SecureString \
    --overwrite \
    --no-cli-pager \
    --output text > /dev/null

  echo "  업로드: $SSM_PATH/$key"
  COUNT=$((COUNT + 1))
done < "$ENV_FILE"

echo ""
echo "완료: $COUNT개 파라미터 업로드"
echo ""
echo "확인 명령어:"
echo "  aws ssm get-parameters-by-path --path $SSM_PATH/ --with-decryption --region $REGION --query 'Parameters[*].Name'"
