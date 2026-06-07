# Observability 구현 변경 사항 정리

작성일: 2026-06-07  
작성자: 유민  
참고: `observability-design.md`, `observability-dev-plan.md`

---

## 개요

Woori-Talk-Banking 백엔드에 **구조화 로그 · Prometheus 메트릭 · OpenSearch 인덱스 · Fluent Bit · Grafana** 파이프라인을 구축한다.  
이 문서는 팀원들이 변경 사항을 파악할 수 있도록 **신규 파일**과 **기존 파일 수정** 내용을 정리한 것이다.

---

## 1. 신규 파일 목록

| 파일 경로 | 역할 | Phase | 상태 |
|-----------|------|-------|------|
| `backend/app/core/request_context.py` | request_id ContextVar — 모든 로그에 요청 추적 ID 주입 | 1 | ✅ 완료 |
| `backend/app/core/logging_config.py` | JSON 포매터, 루트 로거 설정 | 1 | ✅ 완료 |
| `backend/app/core/middleware.py` | RequestLoggingMiddleware — HTTP 요청/응답 자동 로깅 | 1 | ✅ 완료 |
| `backend/app/core/opensearch_writer.py` | voice_pipeline 레코드 비동기 직접 쓰기 | 1 | ✅ 완료 |
| `backend/app/core/metrics.py` | Prometheus 커스텀 메트릭 정의 | 2 | ✅ 완료 |
| `infra/fluent-bit/fluent-bit.conf` | Fluent Bit 파이프라인 설정 | 3 | ✅ 완료 |
| `infra/fluent-bit/parsers.conf` | JSON 파서 정의 | 3 | ✅ 완료 |
| `infra/docker-compose.yml` | 전체 컨테이너 구성 (fluent-bit, prometheus, node-exporter, blackbox-exporter, grafana) | 3 | ✅ 완료 |
| `infra/prometheus/prometheus.yml` | Prometheus scrape 설정 | 4 | ✅ 완료 |
| `infra/grafana/provisioning/datasources/datasources.yml` | Grafana 데이터소스 자동 등록 | 4 | ✅ 완료 |
| `infra/grafana/provisioning/dashboards/dashboards.yml` | Grafana 대시보드 폴더 설정 | 4 | ✅ 완료 |
| `infra/grafana/provisioning/dashboards/voice_pipeline.json` | 음성 파이프라인 현황 대시보드 (Prometheus 6패널 + OpenSearch 2패널) | 4 | ✅ 완료 |
| `infra/grafana/provisioning/dashboards/financial.json` | 금융 거래 현황 대시보드 (Prometheus 6패널 + OpenSearch 1패널) | 4 | ✅ 완료 |
| `infra/grafana/provisioning/dashboards/external_api.json` | 외부 API 상태 대시보드 (Prometheus 4패널) | 4 | ✅ 완료 |
| `infra/grafana/provisioning/dashboards/errors.json` | 에러 분석 대시보드 (Prometheus 4패널 + OpenSearch 1패널) | 4 | ✅ 완료 |

---

## 2. 기존 파일 수정 목록

### 2-1. `backend/requirements.txt`

**Phase**: 사전 준비  
**상태**: ✅ 완료  

**변경 내용**: 아래 패키지 3개 추가 (pip freeze 버전 고정)

```
python-json-logger==4.1.0
prometheus-fastapi-instrumentator==8.0.0
prometheus_client==0.25.0
```

> **수정 이력**: 초기 구현에서 FileHandler 누락 → `setup_logging()`에 RotatingFileHandler 추가 (50 MB × 5개 롤링). `~/woori-logs/` 디렉토리도 자동 생성하도록 수정.

**왜 필요한가**
- `python-json-logger`: FastAPI stdout 로그를 JSON 포맷으로 출력. Fluent Bit가 JSON을 파싱해서 OpenSearch 필드로 그대로 저장할 수 있음
- `prometheus-fastapi-instrumentator`: FastAPI에 `/metrics` 엔드포인트를 자동 생성. HTTP 응답시간, 에러율 등 기본 메트릭을 코드 수정 없이 수집
- `prometheus_client`: 커스텀 메트릭(Counter, Histogram) 정의에 사용

---

### 2-2. `backend/app/main.py`

**Phase**: 1 · 2  
**상태**: ✅ 완료

**변경 내용 요약**

| 변경 종류 | 대상 | 설명 |
|-----------|------|------|
| 제거 | `logging.basicConfig(...)` | JSON 포매터와 충돌. `setup_logging()`으로 대체 |
| 추가 | `setup_logging()` 호출 | 모든 로그를 JSON으로 출력하는 루트 로거 설정 |
| 추가 | `RequestLoggingMiddleware` 등록 | 모든 HTTP 요청/응답을 자동 로깅 |
| 추가 | `Instrumentator().instrument(app).expose(app)` | `/metrics` 엔드포인트 자동 생성 |
| 수정 | `job()` 함수 내부 | APScheduler 자동이체 실행 결과를 로그 + 메트릭에 기록 |
| 추가 | `app_error_total` counter | AppError 핸들러에서 에러 코드별 발생 횟수 기록 |

**`job()` 변경 상세**

현재 코드:
```python
def job():
    db = SessionLocal()
    try:
        run_due_auto_transfers(db, user_id=None)
    finally:
        db.close()
```

변경 후:
```python
def job():
    # job_id로 스케줄러 실행 단위를 로그에서 추적 가능
    job_id = f"auto_transfer_{datetime.now(timezone.utc).isoformat()}"
    db = SessionLocal()
    try:
        run_due_auto_transfers(db, user_id=None)
        logger.info("auto_transfer_executed", extra={
            "event": "auto_transfer_executed",
            "job_id": job_id,
            "status": "success",
        })
    except Exception as e:
        logger.error("auto_transfer_executed", extra={
            "event": "auto_transfer_executed",
            "job_id": job_id,
            "status": "failed",
            "error": str(e),
        })
        auto_transfer_scheduler_runs_total.labels(status="failed").inc()
    else:
        auto_transfer_scheduler_runs_total.labels(status="success").inc()
    finally:
        db.close()
```

**왜 필요한가**  
현재 자동이체 스케줄러 실행 결과가 어디에도 기록되지 않음. 실패해도 알 수 없는 상태.  
`job_id`를 찍으면 OpenSearch에서 "특정 시간대 자동이체 실행이 성공했는지" 추적 가능.

---

### 2-3. `backend/app/shared/voice/service.py`

**Phase**: 1 · 2  
**상태**: ✅ 완료

**변경 대상 함수**: `_handle_normal_flow()`

**변경 내용 요약**

| 변경 종류 | 설명 |
|-----------|------|
| 추가 | STT · agent · TTS 각 단계 실행 시간 측정 (`time.monotonic()`) |
| 추가 | `voice_pipeline_complete` 이벤트 로그 출력 |
| 추가 | `asyncio.create_task(write_voice_pipeline_record_async(...))` — OpenSearch voice_pipeline 인덱스 직접 기록 |
| 추가 | Prometheus Histogram 관측값 기록 (`voice_stage_duration`) |

**기록되는 데이터 (`voice_pipeline_complete` 이벤트)**
```json
{
  "event": "voice_pipeline_complete",
  "request_id": "uuid",
  "user_id": "uuid",
  "stt_ms": 450,
  "agent_ms": 1200,
  "tts_ms": 690,
  "total_ms": 2340,
  "intent": "transfer",
  "navigate_to": "transfer/confirm",
  "success": true
}
```

**왜 필요한가**  
현재 음성 파이프라인 전체 응답시간이 어디에도 측정되지 않음.  
STT가 느린지, LLM이 느린지 구분이 불가능한 상태.  
단계별 ms를 기록하면 병목 지점을 정확히 특정할 수 있음.

> **주의**: `agent_ms`는 `graph.ainvoke()` 전체 시간 — LLM 호출뿐 아니라 tool 실행, DB 조회 시간 포함. `llm_ms`가 아닌 `agent_ms`로 명명.

---

### 2-4. `backend/app/features/transfer/service.py`

**Phase**: 1 · 2  
**상태**: ✅ 완료

**변경 대상 함수**: `execute_transfer()`

**변경 내용 요약**

| 변경 종류 | 위치 | 설명 |
|-----------|------|------|
| 추가 | 함수 시작 | `transfer_start = time.monotonic()` — 실행 시간 측정 시작 |
| 추가 | `db.commit()` 직후 (성공 경로) | `transfer_executed` 이벤트 로그 + `transfer_total.labels(status="success").inc()` |
| 추가 | `TransferError("INSUFFICIENT_BALANCE")` raise 직전 | `transfer_total.labels(status="failed").inc()` |

**기록되는 데이터 (`transfer_executed` 이벤트)**
```json
{
  "event": "transfer_executed",
  "request_id": "uuid",
  "user_id": "uuid",
  "tx_id": "uuid",
  "amount": 50000,
  "to_bank": "우리은행",
  "to_account_masked": "110123***4567",
  "status": "success",
  "duration_ms": 320
}
```

**왜 필요한가**  
이체는 금융 서비스의 핵심 이벤트. 감사(Audit) 목적으로 누가 언제 얼마를 이체했는지 별도 인덱스(`transfer_audit`)에 365일 보존.

> **보안**: `_mask_account()` 기존 함수 재사용. 계좌번호 전체는 절대 로그에 기록하지 않음.

---

### 2-5. `backend/app/shared/agent/graph.py`

**Phase**: 1 · 2  
**상태**: ✅ 완료

**변경 대상 함수**: `execute_node()` 내부

**변경 내용 요약**

| 변경 종류 | 설명 |
|-----------|------|
| 추가 | tool 호출 전 `agent_tool_call_start` 이벤트 로그 |
| 추가 | tool 호출 후 `agent_tool_call_end` 이벤트 로그 (finally 블록) |
| 추가 | 이체 성공 시 `agent_transfer_completed` 로그 |
| 추가 | 이체 비즈니스 실패 시 `agent_transfer_failed` 로그 |
| 추가 | 자동이체 등록 성공 시 `agent_auto_transfer_registered` 로그 |
| 추가 | `agent_node_executions_total` Counter (finally 블록, 항상 증가) |
| 추가 | `asv_verification_total` Counter (`service.py`의 `_handle_asv_flow()` 내부) |

**왜 필요한가**  
`RequestLoggingMiddleware`는 HTTP 요청만 로깅함. agent의 `execute_node`는 HTTP 레이어 없이 직접 service 함수를 호출하기 때문에 미들웨어 로그에 찍히지 않음.  
이체·잔액·자동이체 tool 실행이 현재 완전한 블랙박스 상태.

**이벤트 구분 정리**

| 이벤트 | 언제 발생 | 의미 |
|--------|-----------|------|
| `agent_tool_call_end success=true` | Python 예외 없이 tool 정상 종료 | tool 자체는 성공 |
| `agent_transfer_failed` | `run_execute_transfer`가 `(message, None)` 반환 | 잔액 부족 등 비즈니스 실패 (Python 예외 없음) |
| `agent_tool_call_end success=false` | except 블록에서 Python 예외 잡힘 | DB 연결 끊김 등 기술적 장애 |

---

### 2-6. `backend/app/shared/agent/tools/execute_auto_transfer.py`

**Phase**: 1  
**상태**: ✅ 완료

**변경 내용 요약**

| 변경 종류 | 설명 |
|-----------|------|
| 추가 | `logger = logging.getLogger(__name__)` |
| 추가 | `register_auto_transfer()` 성공 후 성공 로그 |
| 추가 | `except` 블록에서 실패 로그 |

**왜 필요한가**  
자동이체 등록 tool 내부 동작이 현재 로그에 전혀 기록되지 않음. 등록 실패 원인 파악 불가.

---

### 2-7. `backend/app/shared/agent/tools/balance.py`

**Phase**: 1  
**상태**: ✅ 완료

**변경 내용 요약**

| 변경 종류 | 설명 |
|-----------|------|
| 추가 | `logger = logging.getLogger(__name__)` |
| 추가 | `get_total_balance()` 호출 시 로그 (`user_id`, 조회 결과) |

**왜 필요한가**  
잔액 조회 tool 호출 빈도·결과를 추적할 수 없는 상태.

---

### 2-8. `backend/app/shared/voice/stt_service.py`

**Phase**: 2  
**상태**: ✅ 완료

**변경 내용 요약**

| 변경 종류 | 위치 | 설명 |
|-----------|------|------|
| 추가 | Clova API 호출 성공 후 | `external_api_calls_total.labels(service="clova_stt", status="success").inc()` |
| 추가 | `STTError` raise 직전 (TimeoutException, RequestError, non-200, empty text) | `external_api_calls_total.labels(service="clova_stt", status="error").inc()` |

**왜 필요한가**  
Clova STT API 에러율을 실시간으로 Prometheus에서 추적. 외부 API 장애를 빠르게 감지.

---

### 2-9. `backend/app/shared/voice/tts_service.py`

**Phase**: 2  
**상태**: ✅ 완료

**변경 내용 요약**

| 변경 종류 | 위치 | 설명 |
|-----------|------|------|
| 추가 | Azure TTS API 호출 성공 후 | `external_api_calls_total.labels(service="azure_tts", status="success").inc()` |
| 추가 | `TTSError` raise 직전 (TimeoutException, RequestError, non-200) | `external_api_calls_total.labels(service="azure_tts", status="error").inc()` |

**왜 필요한가**  
Azure TTS API 에러율 추적. STT와 동일한 이유.

---

### 2-10. `backend/app/core/opensearch.py`

**Phase**: 3  
**상태**: ✅ 완료

**변경 내용 요약**

`create_indices_if_not_exists()`에 아래 인덱스 3개 추가. 기존 `financial_docs`, `chatbot_logs` 인덱스는 그대로 유지.

| 인덱스 | 주요 필드 | 쓰기 주체 | 보존 |
|--------|-----------|-----------|------|
| `app_logs` | timestamp, level, request_id, feature, event, duration_ms | Fluent Bit | 30일 |
| `voice_pipeline` | stt_ms, agent_ms, tts_ms, total_ms, intent, success | 앱 직접 (opensearch_writer) | 90일 |
| `transfer_audit` | tx_id, order_id, amount, to_bank, to_account_masked, recipient, status | Fluent Bit | 365일 |

**왜 필요한가**  
인덱스가 없으면 Fluent Bit가 데이터를 보낼 때 자동 생성되지만, 필드 타입이 잘못 매핑될 수 있음 (예: 숫자가 문자열로 저장). 명시적 매핑으로 Grafana 쿼리 오류 방지.

---

## 3. 변경 파일이 없는 팀원 확인 사항

| 항목 | 담당 | 시점 |
|------|------|------|
| Grafana Slack Webhook URL 발급 | 팀 채널 관리자 | Phase 4 |
| Aiven OpenSearch ISM 정책 지원 여부 확인 | Aiven 콘솔 접속 가능한 팀원 | Phase 3 |
| EC2 보안 그룹에서 Grafana 포트(3000) IP 제한 설정 | 인프라 담당 | Phase 3 |
