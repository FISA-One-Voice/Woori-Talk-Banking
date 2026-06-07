# Observability 개발 계획

작성일: 2026-06-07
담당: 유민

---

## 한 줄 요약

로그는 FastAPI에서 JSON으로 찍고 Fluent Bit가 파일 읽어서 OpenSearch에 저장.  
메트릭은 Prometheus가 FastAPI `/metrics`를 주기적으로 긁어가고 둘 다 Grafana에서 시각화.

---

## 전체 흐름

```
로그   →  FastAPI (JSON stdout + 파일 저장)
             → Fluent Bit (파일 읽기 + rewrite_tag 라우팅)
             → OpenSearch (app_logs / transfer_audit / voice_pipeline 인덱스)
             → Grafana (인덱스 조회)

메트릭 →  node_exporter (CPU·메모리 /metrics 노출)
          instrumentator (앱 내부 코드에 심어서 /metrics 노출)
             → Prometheus (주기적으로 /metrics 긁어와 저장)
             → Grafana (메트릭 조회)
```

---

## 수집 데이터

### 로그 계열 → OpenSearch

| 인덱스 | 수집 데이터 | 보존 |
|--------|------------|------|
| `app_logs` | 모든 API 호출 기록, 응답시간, 에러 로그, 음성 파이프라인 완료 기록 | 30일 |
| `transfer_audit` | 이체 실행, 자동이체 실행·등록·취소 감사 기록 | 365일 |
| `voice_pipeline` | STT/agent/TTS 단계별 ms, 인텐트, 성공/실패 | 90일 |

### 메트릭 계열 → Prometheus

- CPU / 메모리
- API 엔드포인트별 응답시간 (P50/P95/P99), 에러율
- STT / agent / TTS 단계별 레이턴시
- Clova / Azure 성공·실패 횟수
- ASV 인증 결과 (pass/fail/spoofing)
- 이체 성공·실패 횟수
- AppError 코드별 발생 횟수

---

## 기술 선택

| 수집 대상 | 선택 | 이유 |
|-----------|------|------|
| 로그 포맷 | python-json-logger | Fluent Bit가 JSON을 그대로 OpenSearch에 흘려보낼 수 있음 |
| API 호출 로그 | Fluent Bit | stdout 수집 가능, rewrite_tag로 라우팅 가능, 가벼움 |
| transfer_audit 별도 저장 | Fluent Bit | rewrite_tag로 목적지 다르게 지정 가능 |
| CPU / 메모리 | Prometheus + node_exporter | OS 레벨 + 앱 내부 데이터 둘 다 수집 가능 |
| API 응답시간·에러율 | Prometheus | instrumentator로 앱 내부 자동 수집 |
| STT/LLM/TTS 레이턴시 | Prometheus | 커스텀 Histogram을 코드에 심어 직접 기록 |
| 외부 API 상태 | Prometheus | 커스텀 Counter로 성공/실패 추적 |
| 시각화 | Grafana | OpenSearch + Prometheus 둘 다 데이터소스 연결 가능 |

---

## 사전 준비

- [x] Docker Desktop 설치 확인 (`docker --version`, `docker compose version`) — Docker 29.1.3 / Compose v5.0.1
- [x] `.env`에 `GRAFANA_ADMIN_PASSWORD` 추가 — 확인됨
- [x] 로그 저장 폴더 생성 (`mkdir -p ~/woori-logs`) — 생성 완료
- [x] 미결사항 ① — **이중 기록 허용** (`rewrite_tag false` 유지): `app_logs` + `transfer_audit` 양쪽 기록
- [ ] 미결사항 ② — Grafana Slack Webhook URL 발급 → **Phase 4 때 처리**
- [ ] 미결사항 ③ — Aiven OpenSearch ISM 정책 지원 여부 콘솔 확인 → **Phase 3 때 처리**
- [x] 미결사항 ④ — **`main.py` AppError 핸들러**에서 `app_error_total` 증가
- [x] 미결사항 ⑤ — `_handle_normal_flow()` 함수명 코드에서 직접 확인 — `shared/voice/service.py`에 존재 확인

---

## Phase 1 — 구조화 로그

### 신규 파일

- [x] **`backend/requirements.txt`** — 패키지 추가 완료
  - `python-json-logger==4.1.0`
  - `prometheus-fastapi-instrumentator==8.0.0`
  - `prometheus_client==0.25.0`

- [x] **`backend/app/core/request_context.py`**
  - `request_id_var: ContextVar[str]`
  - `get_request_id() -> str`

- [x] **`backend/app/core/logging_config.py`**
  - `_RequestIdFilter` — 모든 로그에 request_id 주입
  - `setup_logging()` — JsonFormatter, StreamHandler + FileHandler(~/woori-logs/app.log)

- [x] **`backend/app/core/middleware.py`**
  - `RequestLoggingMiddleware`
  - X-Request-ID 읽기/생성, feature 태그 추출
  - `request_start` / `request_end` 이벤트 로그
  - `finally`에서 `request_id_var.reset(token)` 필수

- [x] **`backend/app/core/opensearch_writer.py`**
  - `write_voice_pipeline_record_async(record)` — `run_in_executor`로 블로킹 방지
  - 실패 시 `logger.warning`만, 예외 미전파

### 기존 파일 수정

- [x] **`backend/app/main.py`**
  - `logging.basicConfig(...)` 제거
  - `setup_logging()` 추가
  - `RequestLoggingMiddleware` 등록
  - `job()` — `job_id` 생성 + `auto_transfer_executed` 이벤트 로그

- [x] **`backend/app/shared/voice/service.py`**
  - `_handle_normal_flow()` 내부 타이밍 측정
    - STT 전후 → `stt_ms`
    - `graph.ainvoke()` 전후 → `agent_ms` (`llm_ms` 아님)
    - TTS 전후 → `tts_ms` / 전체 → `total_ms`
  - `voice_pipeline_complete` 이벤트 로그
  - `asyncio.create_task(write_voice_pipeline_record_async({...}))`

- [x] **`backend/app/features/transfer/service.py`**
  - `execute_transfer()` — `db.commit()` 직후 `transfer_executed` 이벤트 로그
  - `_mask_account()` 재사용, 계좌번호 전체 절대 기록 금지

- [x] **`backend/app/shared/agent/graph.py`**
  - `execute_node` 내부 tool 호출 전후 로그
    - `agent_tool_call_start` — tool명, action, user_id, amount(이체만)
    - `agent_tool_call_end` — tool명, duration_ms, success
  - 이체 결과 분기
    - `agent_transfer_completed` — tx_id 있을 때
    - `agent_transfer_failed` — tx_id None일 때 (비즈니스 실패)
  - `agent_auto_transfer_registered` — 자동이체 등록 성공 시

- [x] **`backend/app/shared/agent/tools/execute_auto_transfer.py`**
  - logger 추가, 성공·실패 이벤트 로그

- [x] **`backend/app/shared/agent/tools/balance.py`**
  - logger 추가, 호출 로그

### Phase 1 검증

```bash
uvicorn app.main:app --reload
# API 호출 후
cat ~/woori-logs/app.log  # JSON 로그 파일 확인
# 터미널 stdout에도 JSON 출력 확인
```

---

## Phase 2 — Prometheus 메트릭

### 신규 파일

- [x] **`backend/app/core/metrics.py`**
  ```python
  voice_stage_duration        # Histogram, stage=[stt/agent/tts]
                              # buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
  agent_node_executions_total # Counter, node
  app_error_total             # Counter, code
  external_api_calls_total    # Counter, service+status
  transfer_total              # Counter, status
  auto_transfer_scheduler_runs_total  # Counter, status
  asv_verification_total      # Counter, result=[pass/fail/spoofing]
  ```

### 기존 파일 수정

- [x] **`backend/app/main.py`**
  ```python
  Instrumentator().instrument(app).expose(app)  # /metrics 자동 생성
  ```

- [x] **`backend/app/shared/voice/service.py`**
  ```python
  voice_stage_duration.labels(stage="stt").observe(stt_ms / 1000)
  voice_stage_duration.labels(stage="agent").observe(agent_ms / 1000)
  voice_stage_duration.labels(stage="tts").observe(tts_ms / 1000)
  ```

- [x] **`backend/app/shared/voice/stt_service.py`**
  ```python
  external_api_calls_total.labels(service="clova_stt", status="success|error").inc()
  ```

- [x] **`backend/app/shared/voice/tts_service.py`**
  ```python
  external_api_calls_total.labels(service="azure_tts", status="success|error").inc()
  ```

- [x] **`backend/app/shared/agent/graph.py`**
  ```python
  asv_verification_total.labels(result="pass|fail|spoofing").inc()
  agent_node_executions_total.labels(node="...").inc()
  ```

- [x] **`backend/app/features/transfer/service.py`**
  ```python
  transfer_total.labels(status="success").inc()
  transfer_total.labels(status="failed").inc()
  ```

- [x] **`backend/app/main.py` job()**
  ```python
  auto_transfer_scheduler_runs_total.labels(status="success|failed").inc()
  ```

### Phase 2 검증

```bash
curl http://localhost:8000/metrics
# http_request_duration_seconds, voice_pipeline_stage_duration_seconds 등 확인
```

---

## Phase 3 — OpenSearch 인덱스 + Fluent Bit + Docker

### 기존 파일 수정

- [x] **`backend/app/core/opensearch.py`**
  - `app_logs`, `voice_pipeline`, `transfer_audit` 인덱스 매핑 추가
  - ISM 정책 등록 (30일 / 90일 / 365일) → **미결사항 ③ 확인 후 처리**

### 신규 파일 생성 (infra 디렉토리)

```
infra/
├── fluent-bit/
│   ├── fluent-bit.conf
│   └── parsers.conf
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── datasources.yml
│       └── dashboards/
│           └── dashboards.yml
└── docker-compose.yml
```

- [x] **`infra/fluent-bit/parsers.conf`**
  ```ini
  [PARSER]
      Name        json_log
      Format      json
      Time_Key    timestamp
      Time_Format %Y-%m-%dT%H:%M:%S.%LZ
  ```

- [x] **`infra/fluent-bit/fluent-bit.conf`**
  - `storage.type filesystem` (SERVICE + INPUT 레벨 둘 다)
  - INPUT: `tail` → `/logs/app.log` (Docker 볼륨 마운트: `~/woori-logs:/logs`)
  - FILTER: `rewrite_tag` — 이체·자동이체 이벤트 → `woori.audit` (keep=true: 이중 기록)
    - `transfer_executed | auto_transfer_executed | agent_auto_transfer_registered`
  - OUTPUT: `woori.audit` → `transfer_audit` 인덱스
  - OUTPUT: `woori.app` → `app_logs` 인덱스

- [x] **`infra/docker-compose.yml`**
  - `fluent-bit` — `~/woori-logs:/logs` 볼륨 마운트, `../.env` env_file
  - `prometheus` — `expose: 9090`, 30일 retention
  - `node-exporter` — CPU·메모리 수집, `pid: host`
  - `blackbox-exporter` — `expose: 9115`
  - `grafana` — `ports: 3000:3000`, `GF_INSTALL_PLUGINS=grafana-opensearch-datasource`, `GF_USERS_ALLOW_SIGN_UP=false`
  - `version` 필드 없음 (deprecated)
  - ASV는 EC2에 별도 배포 중이므로 docker-compose에서 제외

### Phase 3 검증

```bash
cd infra
docker compose up -d
docker compose ps              # 모든 컨테이너 UP 확인
docker compose logs fluent-bit # 에러 없는지 확인
# Aiven 콘솔 → app_logs 인덱스에 데이터 쌓이는지 확인
```

---

## Phase 4 — Prometheus + Grafana

- [x] **`infra/prometheus/prometheus.yml`**
  ```yaml
  scrape_configs:
    - job_name: "woori-backend"
      static_configs:
        - targets: ["host.docker.internal:8000"]  # 로컬 FastAPI
      metrics_path: /metrics

    - job_name: "woori-node"
      static_configs:
        - targets: ["node-exporter:9100"]

    - job_name: "woori-healthcheck"
      metrics_path: /probe
      params:
        module: [http_2xx]
      static_configs:
        - targets:
            - http://host.docker.internal:8000/health
      relabel_configs:
        - source_labels: [__address__]
          target_label: __param_target
        - target_label: __address__
          replacement: blackbox-exporter:9115
  ```

- [x] **`infra/grafana/provisioning/datasources/datasources.yml`**
  - Prometheus 데이터소스 (isDefault: true)
  - OpenSearch 데이터소스 (Aiven 주소)

- [x] **`infra/grafana/provisioning/dashboards/dashboards.yml`**
  - 대시보드 폴더 설정

- [x] **Grafana 접속 확인**
  ```
  http://localhost:3000
  Connections → Data sources → Prometheus, OpenSearch 연결 확인
  ```

- [x] **대시보드 4개 구성**
  - 음성 파이프라인 현황 (STT/agent/TTS 레이턴시, P50/P95/P99, 인텐트 분포 + OpenSearch 파이프라인 이력 테이블)
  - 금융 거래 현황 (이체 성공/실패, 시간대별 건수 + OpenSearch transfer_audit 감사 로그 테이블)
  - 외부 API 상태 (Clova/Azure 에러율·응답시간)
  - 에러 분석 (AppError 코드별, HTTP 4xx/5xx + OpenSearch ERROR 레벨 로그 패널)

- [ ] **Slack Webhook 알림 연결** (URL 발급 후)
  | 조건 | 임계값 |
  |------|--------|
  | 음성 P99 > 8초 | 5분 지속 |
  | 외부 API 에러율 > 10% | 2분 지속 |
  | 이체 실패율 > 5% | 1분 지속 |
  | HTTP 5xx 발생 | 즉시 |

### Phase 4 검증

```bash
http://localhost:9090/targets  # 모든 job UP 상태 확인
http://localhost:3000          # Grafana 대시보드 확인
```

---

## Phase 5 — EC2 분리 (데모 후)

팀 합의 후 `observability-plan.md` §3 절차 실행.

---

## 코드 생성 후 검토 체크리스트

### 검토 1 — 구조 정합성
- [ ] 신규 파일이 `observability-design.md` 2번 목록과 일치하는가
- [ ] 기존 파일 수정이 `observability-design.md` 3번 목록과 일치하는가

### 검토 2 — 로그 스키마 정합성
- [ ] `voice_pipeline_complete` 필드에 `agent_ms` 사용 (`llm_ms` 아님)
- [ ] `transfer_executed` 필드에 마스킹된 계좌번호만 있는가
- [ ] `agent_tool_call_start/end` 스키마 일치하는가
- [ ] `agent_transfer_failed` vs `agent_tool_call_end success=false` 올바르게 분기되는가
- [ ] `agent_auto_transfer_registered`에 `order_id, amount, to_bank, recipient` 포함되는가
- [ ] amount 없는 tool (잔액 조회 등)은 amount 필드 키 자체 생략하는가

### 검토 3 — 비동기 안전성
- [ ] `opensearch_writer.py`에서 `run_in_executor`로 감쌌는가
- [ ] `asyncio.create_task()`가 async context 안에서 호출되는가
- [ ] `middleware.py` `finally`에서 `request_id_var.reset(token)` 호출하는가

### 검토 4 — 보안·개인정보
- [ ] 로그에 계좌번호 전체 / 비밀번호 없는가
- [ ] `GF_USERS_ALLOW_SIGN_UP=false` 설정됐는가
- [ ] `.env`의 `GRAFANA_ADMIN_PASSWORD`가 강력한 값인가
