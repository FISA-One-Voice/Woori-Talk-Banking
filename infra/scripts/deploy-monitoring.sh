#!/bin/bash
set -euo pipefail

REGION="ap-northeast-2"
SSM_PATH="/woori/prod"
WORKDIR="/home/ubuntu"
REPO_RAW="https://raw.githubusercontent.com/FISA-One-Voice/Woori-Talk-Banking/main"

echo "[monitoring] SSM Parameter Store -> .env regenerate..."
aws ssm get-parameters-by-path \
  --path "${SSM_PATH}/" \
  --with-decryption \
  --region "$REGION" \
  --output json \
  --query 'Parameters[*].[Name,Value]' > /tmp/monitoring_ssm_params.json

python3 -c "
import json

required = {
    'GRAFANA_ADMIN_PASSWORD',
    'OPENSEARCH_HOST',
    'OPENSEARCH_PORT',
    'OPENSEARCH_USER',
    'OPENSEARCH_PASSWORD',
    'POSTGRES_HOST',
    'POSTGRES_PORT',
    'POSTGRES_DATABASE',
    'POSTGRES_USER',
    'POSTGRES_PASSWORD',
}

with open('/tmp/monitoring_ssm_params.json') as f:
    params = json.load(f)

values = {name.rsplit('/', 1)[-1]: value for name, value in params}
missing = sorted(required - values.keys())
if missing:
    raise SystemExit('[monitoring] missing SSM parameters: ' + ', '.join(missing))

with open('/home/ubuntu/.env', 'w') as f:
    for key in sorted(required):
        value = values[key]
        if '\n' in value:
            value = '\"' + value.replace('\"', '\\\\\"') + '\"'
        f.write(f'{key}={value}\n')

print(f'[monitoring] .env created: {len(required)} variables')
"
rm -f /tmp/monitoring_ssm_params.json
chmod 600 "${WORKDIR}/.env"

echo "[monitoring] Sync latest config files..."
mkdir -p "${WORKDIR}/prometheus" \
  "${WORKDIR}/grafana/provisioning/dashboards" \
  "${WORKDIR}/grafana/provisioning/datasources"

curl -fsSL "${REPO_RAW}/infra/docker-compose.yml" -o "${WORKDIR}/docker-compose.yml"
curl -fsSL "${REPO_RAW}/infra/prometheus/prometheus.yml" -o "${WORKDIR}/prometheus/prometheus.yml"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/datasources/datasources.yml" -o "${WORKDIR}/grafana/provisioning/datasources/datasources.yml"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/dashboards.yml" -o "${WORKDIR}/grafana/provisioning/dashboards/dashboards.yml"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/asv.json" -o "${WORKDIR}/grafana/provisioning/dashboards/asv.json"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/errors.json" -o "${WORKDIR}/grafana/provisioning/dashboards/errors.json"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/external_api.json" -o "${WORKDIR}/grafana/provisioning/dashboards/external_api.json"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/financial.json" -o "${WORKDIR}/grafana/provisioning/dashboards/financial.json"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/node_exporter.json" -o "${WORKDIR}/grafana/provisioning/dashboards/node_exporter.json"
curl -fsSL "${REPO_RAW}/infra/grafana/provisioning/dashboards/voice_pipeline.json" -o "${WORKDIR}/grafana/provisioning/dashboards/voice_pipeline.json"

echo "[monitoring] Restart containers..."
cd "$WORKDIR"
docker compose --env-file "${WORKDIR}/.env" -f "${WORKDIR}/docker-compose.yml" up -d prometheus blackbox-exporter
docker compose --env-file "${WORKDIR}/.env" -f "${WORKDIR}/docker-compose.yml" up -d --force-recreate grafana
docker compose --env-file "${WORKDIR}/.env" -f "${WORKDIR}/docker-compose.yml" ps
