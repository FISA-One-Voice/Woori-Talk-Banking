# Woori-Talk-Banking 옵저버빌리티 완전 가이드

> 이 문서는 팀원 누구나 "우리 시스템이 어떻게 돌아가고, 어떻게 데이터를 수집하고, 대시보드에서 뭘 보는 건지"를 처음부터 이해할 수 있도록 작성했습니다.

---

## 핵심 개념 — 공장 비유로 이해하기

**공장(FastAPI 서버)** 이 돌아가면서 매일 작업 기록지를 쌓아요.

---

**Fluent Bit** — 똑똑한 배달부

기록지를 배달하는데, 배달하면서 "이건 이체 기록이니까 이체 창고로, 나머지는 일반 창고로" 분류까지 해줘요.  
Filebeat보다 가볍고 할 수 있는 게 많아요.

> **Filebeat**(단순 배달부)와 비교: Filebeat는 기록지를 주워서 한 곳으로만 배달, Fluent Bit는 분류·라우팅까지 가능

---

**Prometheus** — 자체 수첩 가진 점검원

Metricbeat처럼 설비 상태를 측정하는데, 창고에 보내지 않고 **자기 수첩에 직접 기록**해요.  
나중에 Grafana가 이 수첩을 읽어가요.

> **Metricbeat**(공장 설비 점검원)와 비교: Metricbeat는 OS 레벨(CPU·메모리)만 측정, Prometheus는 앱 내부 데이터(응답시간·에러율·STT 레이턴시)까지 수집 가능

---

**OpenSearch** — 창고

Fluent Bit가 배달한 기록지를 모두 보관하는 곳이에요. 검색도 할 수 있어요.

**OpenSearch 대시보드** — 창고 전용 열람실: OpenSearch 안 기록지만 볼 수 있음, Prometheus 수첩은 못 봄

**Grafana** — 통합 열람실: OpenSearch 창고도 보고, Prometheus 수첩도 보고, **한 화면에 같이** 볼 수 있어요.

---

```
공장(FastAPI)
    │
    ├─ Fluent Bit (배달부) ──────► OpenSearch (창고) ◄─── Grafana (열람실)
    │                                                          │
    └─ Prometheus (수첩 점검원) ──────────────────────────────┘
```

![Observability 파이프라인](assets/하이고야.png)
---

## 기술 선택 근거

### 우리 프로젝트 조건

- 시각장애인 대상 뱅킹앱 → 금융 감사 로그 필수
- 음성 파이프라인 (STT → LLM → TTS) → 단계별 레이턴시 추적 필요
- FastAPI + Docker → stdout 로그가 주 출력
- Aiven OpenSearch 이미 있음
- 로컬 개발 환경

### 데이터 수집 경로 3가지

| 경로 | 도구 | 대상 인덱스/저장소 |
|------|------|-------------------|
| 로그 자동 수집 | Fluent Bit | `app_logs`, `transfer_audit` |
| 메트릭 자동 수집 | Prometheus scrape | Prometheus TSDB |
| **앱 직접 기록** | `opensearch_writer.py` | `voice_pipeline` |

**앱 직접 기록을 별도로 선택한 이유 (`voice_pipeline`)**

`voice_pipeline` 레이턴시 데이터(stt_ms, agent_ms, tts_ms)는:
- **Fluent Bit 경유 불가**: 로그 메시지로 남기면 텍스트 파싱이 필요하고 필드 구조가 복잡함
- **Prometheus 불가**: Histogram으로 수집하면 재시작 시 히스토리가 날아가는 누적 데이터라 부적합
- → **해결책**: 파이프라인 완료 시점에 앱이 직접 OpenSearch API를 호출해 구조화된 레코드로 저장 (fire-and-forget)

```
voice/service.py
  └─ _record_voice_pipeline()
       └─ opensearch_writer.py (asyncio.create_task — 이벤트 루프 블로킹 없음)
            └─ OpenSearch voice_pipeline 인덱스 직접 기록
```

---

### 로그 vs 메트릭 역할 분리

| 계열 | 목적 | 경로 |
|------|------|------|
| **로그** | "무슨 일이 있었는지 기록" → 나중에 검색해서 원인 파악 | Fluent Bit → OpenSearch |
| **메트릭** | "지금 상태가 어떤지 숫자" → 실시간 모니터링 및 알림 | Prometheus → Grafana |

**로그 계열 수집 대상**
- API 호출 기록 (누가 어떤 엔드포인트를 호출했는지)
- 이체 실행 기록 (transfer_audit — 언제, 얼마, 어느 계좌로)
- 자동이체 실행 기록
- 음성 파이프라인 완료 기록 (voice_pipeline 인덱스)
- 에러 발생 로그

**메트릭 계열 수집 대상**
- CPU / 메모리 사용량
- API 응답시간 (엔드포인트별 몇 ms)
- API 에러율 (5xx 비율)
- STT 단계 레이턴시 (Clova 응답 몇 ms)
- LLM 단계 레이턴시 (OpenAI 응답 몇 ms)
- TTS 단계 레이턴시 (Azure 응답 몇 ms)
- 외부 API 성공/실패 횟수 (Clova, Azure, OpenAI)
- 이체 성공/실패 횟수
- ASV 인증 성공/실패 횟수

### 도구별 선택 이유

| 수집 대상 | 후보 | 선택 | 이유 |
|-----------|------|------|------|
| 로그 포맷 | logging.basicConfig / python-json-logger | **python-json-logger** | basicConfig는 텍스트라 Fluent Bit가 필드 추출 어려움. JSON으로 출력해서 Fluent Bit가 그대로 OpenSearch에 흘려보낼 수 있음 |
| API 호출 로그 | Filebeat / Fluent Bit | **Fluent Bit** | FastAPI는 stdout을 뱉음. Filebeat는 stdout 못 읽음. Fluent Bit는 stdout 수집 가능하고 도커 사이드카에 적합하며 가벼움 |
| transfer_audit 별도 저장 | Filebeat / Fluent Bit | **Fluent Bit** | Filebeat는 한 곳으로만 전송 가능. Fluent Bit는 rewrite_tag로 목적지 다르게 라우팅 가능 |
| CPU / 메모리 | Metricbeat / Prometheus | **Prometheus + node_exporter** | Metricbeat는 OS 레벨만 수집 가능. Prometheus는 node_exporter로 OS, instrumentator로 앱 내부 데이터 둘 다 수집 가능 |
| API 응답시간 · 에러율 | Metricbeat / Prometheus | **Prometheus** | Metricbeat는 앱 내부 계측 불가. instrumentator로 코드 몇 줄이면 자동 수집 |
| STT / LLM / TTS 단계별 레이턴시 | Metricbeat / Prometheus | **Prometheus** | Metricbeat는 앱 내부 계측 불가. 커스텀 Histogram을 코드에 심으면 원하는 값을 직접 기록 가능 |
| 외부 API 상태 (Clova, Azure, OpenAI) | Metricbeat / Prometheus | **Prometheus** | Metricbeat는 앱 내부 계측 불가. 커스텀 Counter를 호출부에 심으면 서비스별 성공/실패 횟수 정확히 기록 가능 |
| 시각화 | OpenSearch 대시보드 / Grafana | **Grafana** | 로그(OpenSearch)와 메트릭(Prometheus)이 두 군데 나뉘어 있어서 OpenSearch 대시보드는 Prometheus 데이터를 못 읽음. Grafana는 둘 다 데이터소스로 연결해 한 화면에서 조회 가능 |

---

## 목차

1. [왜 모니터링이 필요한가?](#1-왜-모니터링이-필요한가)
2. [우리 시스템 전체 구조](#2-우리-시스템-전체-구조)
3. [각 기술 도구 소개](#3-각-기술-도구-소개)
4. [옵저버빌리티란 무엇인가?](#4-옵저버빌리티란-무엇인가)
5. [음성 요청이 들어오면 무슨 일이 벌어지나?](#5-음성-요청이-들어오면-무슨-일이-벌어지나)
6. [데이터 수집 방법](#6-데이터-수집-방법)
7. [데이터는 어디에 저장되나?](#7-데이터는-어디에-저장되나)
8. [누적 데이터 vs 실시간 데이터](#8-누적-데이터-vs-실시간-데이터)
9. [대시보드 4개 완전 해설](#9-대시보드-4개-완전-해설)
10. [알림 시스템](#10-알림-시스템)
11. [자주 겪는 문제와 해석법](#11-자주-겪는-문제와-해석법)

---

## 1. 왜 모니터링이 필요한가?

### 비유로 이해하기

병원 중환자실을 생각해 보세요.
의사와 간호사는 환자 옆에 항상 붙어있지 않습니다.
대신 모니터 하나가 **심박수, 혈압, 산소포화도**를 실시간으로 보여주고, 이상이 생기면 **경보음**이 울립니다.

우리 서버도 똑같습니다.
- 서버 = 환자
- 모니터링 시스템 = 병원 모니터
- 개발자 = 의사

모니터링이 없으면?
- 사용자가 "이체가 안 돼요!"라고 신고할 때까지 장애를 모름
- 어디서 문제가 생겼는지 찾는 데 몇 시간 걸림
- 얼마나 많은 사람이 피해를 봤는지 알 수 없음

### 우리 앱이 특히 중요한 이유

Woori-Talk-Banking은 **돈을 다루는 앱**입니다.
- STT(음성인식)가 잘못 들어서 "5만원" 이체가 "50만원"으로 처리되면 안 됩니다
- 이체 API가 10초 이상 걸리면 사용자는 "전송됐나?" 불안해합니다
- ASV(화자 인증) 오류가 급증하면 보안 공격 가능성이 있습니다

따라서 모니터링은 선택이 아니라 **필수**입니다.

---

## 2. 우리 시스템 전체 구조

```
[사용자 스마트폰]
      |
      | 음성 녹음 파일 전송 (HTTP)
      v
[FastAPI 백엔드] ←→ [PostgreSQL DB]
      |
      |-- [Clova STT API] : 음성 → 텍스트 변환
      |-- [LangGraph 에이전트] : 텍스트 분석 + 행동 결정
      |       |
      |       |-- [Tool: 잔액 조회]
      |       |-- [Tool: 이체 실행]
      |       |-- [Tool: 거래내역 조회]
      |       └-- [Tool: 자동이체 관리]
      |-- [ASV 화자 인증] : "이 목소리가 진짜 사용자인가?"
      └-- [Azure TTS API] : 텍스트 → 음성 변환

[모니터링 인프라] ← 위 모든 과정에서 데이터 수집
      |
      |-- [Prometheus] : 숫자 데이터(메트릭) 저장
      |-- [OpenSearch] : 텍스트 데이터(로그) 저장
      |-- [PostgreSQL] : 비즈니스 데이터 저장
      └-- [Grafana]   : 시각화 대시보드

전체를 [Docker Compose]로 하나의 묶음으로 실행
```

---

## 3. 각 기술 도구 소개

### FastAPI (백엔드 프레임워크)

Python으로 만든 웹 서버입니다.
사용자 앱에서 오는 HTTP 요청을 받아서 처리하고 응답을 돌려줍니다.

```
사용자가 "잔액 얼마야?" 라고 말하면
→ 앱이 음성 파일을 FastAPI에 POST /api/voice/voice 로 전송
→ FastAPI가 이걸 처리해서 "전체 잔액은 150만 원입니다" 음성으로 반환
```

### Prometheus (메트릭 수집기)

**숫자로 된 상태 데이터**를 수집하는 도구입니다.

비유: 자동차 계기판
- 속도계 = 초당 요청 수
- 연료 게이지 = 성공률
- 주행거리 = 총 요청 횟수

Prometheus는 **15초마다** 우리 백엔드에 접속해서 숫자 데이터를 가져갑니다 (이걸 "스크래핑"이라고 합니다).

```
[Prometheus] → "야 백엔드, 지금 상태 알려줘" (15초마다)
[백엔드]     → "요청 총 1,234건, 에러 5건, 평균 응답시간 0.8초"
[Prometheus] → (데이터 저장)
```

### Grafana (대시보드 도구)

Prometheus와 OpenSearch에 저장된 데이터를 **그래프, 차트, 숫자판**으로 보여줍니다.

비유: 자동차 계기판 화면 자체
- Prometheus = 센서들 (속도, 연료 등을 측정)
- Grafana = 계기판 화면 (측정값을 보여줌)

### OpenSearch (로그 저장소)

**텍스트로 된 기록(로그)**을 저장하는 데이터베이스입니다.

비유: 회사 업무 일지
- "2026-06-08 14:23:11 - 사용자 abc123이 이체 요청 / 금액: 50,000원 / 성공"
- "2026-06-08 14:23:45 - 에러 발생 / 코드: INSUFFICIENT_BALANCE / 사용자: xyz789"

Elasticsearch를 기반으로 한 오픈소스 버전이며, 텍스트 검색이 매우 빠릅니다.

우리는 로그를 3개 인덱스(=폴더)로 나눠 저장합니다:

| 인덱스 | 내용 | 보관 기간 |
|--------|------|-----------|
| `app_logs` | 일반 애플리케이션 로그, 에러 로그 | 30일 |
| `voice_pipeline` | 음성 처리 과정 기록 | 90일 |
| `transfer_audit` | 이체 감사 로그 (금융 규제용) | 365일 |

### PostgreSQL (관계형 데이터베이스)

사용자 계정, 거래 내역, 자동이체 설정 등 **비즈니스 핵심 데이터**를 저장합니다.
모니터링에서는 자동이체 등록 건수, 실행 이력 등을 조회할 때 사용합니다.

### Docker / Docker Compose (컨테이너)

위의 모든 프로그램을 **각각의 독립된 상자(컨테이너)에 담아서** 한 번에 실행하는 도구입니다.

비유: 도시락 칸 분리대
- 밥, 국, 반찬이 서로 섞이지 않게 분리
- 한 칸이 망가져도 다른 칸에 영향 없음
- 어떤 컴퓨터에서든 동일하게 실행 가능

```bash
docker compose up -d   # 모든 서비스 한 번에 시작
docker compose down    # 모든 서비스 한 번에 종료
```

---

## 4. 옵저버빌리티란 무엇인가?

옵저버빌리티(Observability)는 **"시스템 내부를 얼마나 잘 들여다볼 수 있는가"**입니다.

3가지 요소로 구성됩니다:

### 로그 (Log) - "무슨 일이 있었나?"

텍스트 형태의 기록입니다.
```json
{
  "timestamp": "2026-06-08T14:23:11",
  "level": "ERROR",
  "event": "app_error",
  "code": "INSUFFICIENT_BALANCE",
  "request_id": "abc-123-def",
  "user_id": "user_456"
}
```
→ "14시 23분에 user_456이 잔액 부족으로 이체 실패했다"

### 메트릭 (Metric) - "얼마나 자주, 얼마나 빠르게?"

숫자 형태의 측정값입니다.
```
voice_pipeline_stage_duration_seconds{stage="stt"} = 0.45
app_error_total{code="INSUFFICIENT_BALANCE"} = 12
transfer_total{status="success"} = 847
```
→ "STT가 평균 0.45초 걸리고, 잔액부족 에러가 12번 났고, 이체는 847건 성공했다"

### 추적 (Trace) - "요청이 어디서 어디로 갔나?"

하나의 요청이 시스템 여러 곳을 거쳐가는 경로를 추적합니다.
우리는 **request_id**라는 고유 번호로 구현했습니다.

```
request_id: "abc-123-def"
 ├── 미들웨어에서 생성
 ├── STT 호출 시 로그에 포함
 ├── 에이전트 실행 시 로그에 포함
 ├── 이체 실행 시 로그에 포함
 └── TTS 호출 시 로그에 포함
```
→ OpenSearch에서 "abc-123-def"를 검색하면 이 요청의 전체 여정이 보임

---

## 5. 음성 요청이 들어오면 무슨 일이 벌어지나?

사용자가 **"우리은행에 10만원 보내줘"** 라고 말하는 순간부터 끝까지 추적해 봅니다.

### Step 1: 미들웨어 진입 (RequestLoggingMiddleware)

```
파일: backend/app/core/middleware.py
```

요청이 들어오는 순간 가장 먼저 만나는 문지기입니다.

**하는 일:**
- `request_id` 생성 (= 이 요청만의 고유 번호. UUID 형식: "a1b2c3d4-...")
- 요청 시작 로그 기록 (언제, 어떤 경로로 왔는지)
- 응답이 나갈 때 종료 로그 기록 (몇 초 걸렸는지, 성공했는지)
- HTTP 메트릭 카운터 증가

```python
# 요청 시작 시
logger.info("request_start", extra={
    "event": "request_start",
    "method": "POST",
    "path": "/api/voice/voice",
    "feature": "voice"
})

# 응답 나갈 때
logger.info("request_end", extra={
    "event": "request_end",
    "status_code": 200,
    "duration_ms": 1234.5
})
```

### Step 2: ASV 화자 인증

```
파일: backend/app/features/voice/router.py
```

"이 목소리가 진짜 등록된 사용자인가?" 확인합니다.

**하는 일:**
- ASV 서버에 음성 파일 전송
- 결과: pass / fail 중 하나 반환
- `asv_verification_total` 카운터 증가 (Prometheus — 실시간 모니터링용)
- `voice_pipeline` 인덱스에 `asv_result` 레코드 기록 (OpenSearch — 누적 집계용)

```python
asv_verification_total.labels(result="pass").inc()
# → Prometheus에 "pass가 1번 더 일어났다" 기록 (실시간)

asyncio.create_task(write_voice_pipeline_record_async({
    "asv_result": "pass",  # "fail"
    "user_id": user_id,
    "success": True,
}))
# → OpenSearch voice_pipeline에 누적 기록 (재시작 후에도 유지)
```

### Step 3: Clova STT (음성 → 텍스트)

```
파일: backend/app/features/voice/router.py
```

음성 파일을 텍스트로 변환합니다.

**하는 일:**
- Clova API에 음성 파일 전송 → "우리은행에 10만원 보내줘" 텍스트 반환
- STT 처리 시간 측정 후 기록
- 외부 API 호출 성공/실패 기록

```python
with voice_stage_duration.labels(stage="stt").time():
    text = await call_clova_stt(audio_file)
# → STT 걸린 시간이 자동으로 Prometheus에 기록됨

external_api_calls_total.labels(service="clova_stt", status="success").inc()
# → Prometheus Counter 증가 (실시간 에러율 패널용)

logger.info("external_api_call", extra={
    "event": "external_api_call",
    "service": "clova_stt",
    "status": "success"  # or "error"
})
# → app_logs에 기록 (서비스별 누적 성공/실패 패널용)
```

### Step 4: LangGraph 에이전트

```
파일: backend/app/shared/agent/graph.py
```

텍스트를 분석해서 "이체를 해야 한다"고 결정하고, 실행합니다.

**에이전트 내부 흐름:**
```
"우리은행에 10만원 보내줘"
    │
    ▼
[분석 노드] → 인텐트: transfer (이체), 금액: 100,000
    │
    ▼
[execute_node] → transfer Tool 선택 및 실행
    │
    ├── agent_node_executions_total{node="pending_action"}.inc()
    │   → "이체 툴이 1번 실행됐다" 카운터 증가
    │
    └── agent_tool_duration_seconds{node="transfer"}.observe(0.85)
        → "이체 툴 실행에 0.85초 걸렸다" 기록
```

### Step 5: 이체 Tool 실행

```
파일: backend/app/shared/agent/tools/transfer.py
```

실제 이체를 처리합니다.

**하는 일:**
- PostgreSQL에서 계좌 확인
- 잔액 확인
- 이체 실행
- 결과 기록

```python
transfer_total.labels(status="success").inc()
# → "이체 성공이 1번 더 일어났다" 카운터 증가
```

### Step 6: Azure TTS (텍스트 → 음성)

```
파일: backend/app/features/voice/router.py
```

"10만원 이체가 완료되었습니다" 텍스트를 음성으로 변환합니다.

```python
with voice_stage_duration.labels(stage="tts").time():
    audio = await call_azure_tts(response_text)
# → TTS 걸린 시간 자동 기록

external_api_calls_total.labels(service="azure_tts", status="success").inc()
```

### Step 7: OpenSearch에 최종 기록

```
파일: backend/app/core/opensearch_writer.py
```

모든 처리가 끝난 뒤, 이 요청의 요약 정보를 OpenSearch에 저장합니다.

```json
{
  "timestamp": "2026-06-08T14:23:11",
  "request_id": "abc-123-def",
  "user_id": "user_456",
  "intent": "transfer",
  "stt_ms": 450,
  "agent_ms": 850,
  "tts_ms": 320,
  "success": true
}
```
→ `voice_pipeline` 인덱스에 저장. 90일 보관.

### 에러가 발생한 경우

```
파일: backend/app/main.py (app_error_handler)
```

어느 단계에서든 에러가 나면:

```python
logger.error("app_error", extra={
    "event": "app_error",
    "code": "INSUFFICIENT_BALANCE",
    "status_code": 422,
    "feature": "transfer"   # ← 요청 URL에서 자동 추출 (신규 추가)
})
app_error_total.labels(code="INSUFFICIENT_BALANCE").inc()
```

→ 로그는 OpenSearch `app_logs`에 (`code`·`feature` 필드 포함),  
→ 카운터는 Prometheus에 각각 기록됩니다.

OpenSearch의 `code`·`feature` 필드를 이용해 **AppError 코드별 발생 건수**·**기능별 에러 분포** 패널을 재시작 후에도 정확하게 표시합니다.

---

## 6. 데이터 수집 방법

### 6-1. Prometheus 메트릭 수집

```
파일: backend/app/core/metrics.py
```

Prometheus는 **2가지 주요 도구**로 데이터를 측정합니다.

#### Counter (카운터) - "총 몇 번 일어났나?"

오직 **증가만** 가능한 카운터입니다. 절대 줄어들지 않습니다.
차량 주행거리계와 같습니다 (항상 늘어나기만 함).

```python
# 정의
app_error_total = Counter("app_error_total", "에러 횟수", labelnames=["code"])

# 사용 (에러 발생 시)
app_error_total.labels(code="INSUFFICIENT_BALANCE").inc()
# → INSUFFICIENT_BALANCE 카운터가 1 증가
```

우리가 Counter로 측정하는 것들:
| 메트릭 이름 | 무엇을 세나 | 레이블(분류 기준) |
|------------|------------|-----------------|
| `app_error_total` | 에러 발생 횟수 | code (에러 코드) |
| `asv_verification_total` | ASV 인증 결과 횟수 | result (pass/fail) |
| `external_api_calls_total` | 외부 API 호출 횟수 | service, status |
| `transfer_total` | 이체 실행 횟수 | status (success/fail) |
| `agent_node_executions_total` | 에이전트 노드 실행 횟수 | node |
| `auto_transfer_scheduler_runs_total` | 자동이체 스케줄러 실행 횟수 | status |

#### Histogram (히스토그램) - "얼마나 걸렸나? 분포는 어떤가?"

**처리 시간**을 측정하고, 분포(분포도)를 기록합니다.
"0.5초 이하 요청이 80%, 1초 이하가 95%..." 이런 식으로 파악 가능합니다.

```python
# 정의
voice_stage_duration = Histogram(
    "voice_pipeline_stage_duration_seconds",
    "단계별 처리 시간",
    labelnames=["stage"],
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]  # 초 단위 기준점
)

# 사용 (자동으로 시간 측정)
with voice_stage_duration.labels(stage="stt").time():
    result = await call_clova_stt(audio)
# → STT가 0.45초 걸렸다면: 0.1초 버킷은 초과, 0.5초 버킷에 포함됨
```

우리가 Histogram으로 측정하는 것들:
| 메트릭 이름 | 무엇을 측정하나 | 레이블 |
|------------|----------------|--------|
| `voice_pipeline_stage_duration_seconds` | STT/Agent/TTS 각 단계 처리 시간 | stage |
| `agent_tool_duration_seconds` | 각 Tool 실행 시간 | node |

#### Histogram에서 파생되는 PromQL 쿼리

Histogram 하나를 정의하면 Prometheus에서 3가지 메트릭이 자동 생성됩니다:

```
voice_pipeline_stage_duration_seconds_count  → 총 관측 횟수
voice_pipeline_stage_duration_seconds_sum    → 처리 시간 합계
voice_pipeline_stage_duration_seconds_bucket → 버킷별 횟수
```

이걸로 Grafana에서 이렇게 씁니다:
```promql
# 평균 처리 시간 계산
rate(voice_pipeline_stage_duration_seconds_sum[5m])
/ rate(voice_pipeline_stage_duration_seconds_count[5m])

# P95 계산 (95%의 요청이 이 시간 이하)
histogram_quantile(0.95, rate(voice_pipeline_stage_duration_seconds_bucket[5m]))
```

### 6-2. 로그 수집

```
파일: backend/app/core/logging_config.py
```

Python `logging` 모듈을 커스터마이징해서 **JSON 형태**로 로그를 출력합니다.

일반 로그:
```
2026-06-08 14:23:11 - ERROR - 잔액이 부족합니다
```

우리 JSON 로그:
```json
{
  "timestamp": "2026-06-08T14:23:11.123Z",
  "level": "ERROR",
  "logger": "app.features.transfer",
  "message": "app_error",
  "request_id": "abc-123-def",
  "event": "app_error",
  "code": "INSUFFICIENT_BALANCE"
}
```

JSON 형태가 좋은 이유: OpenSearch가 각 필드를 개별적으로 인식해서 검색/필터링이 쉬워집니다.

**OpenSearch로 전송되는 경로:**
```
백엔드 로그 출력 (stdout/stderr)
    │
    ▼
Logstash (로그 수집기) → OpenSearch에 저장
```

### 6-3. request_id로 요청 추적

```
파일: backend/app/core/request_context.py
```

하나의 요청이 여러 함수와 서비스를 거쳐가는데, 각 로그에 같은 `request_id`를 붙여서 나중에 "이 요청 전체 경로"를 조회할 수 있게 합니다.

```python
# ContextVar 사용 - 각 요청마다 독립적인 값을 가짐
request_id_var = ContextVar("request_id", default="")

# 미들웨어에서 설정
set_request_id("abc-123-def")

# 어느 함수에서든 꺼내서 사용
get_request_id()  # → "abc-123-def"
```

**ContextVar가 특별한 이유:**  
FastAPI는 여러 요청을 동시에 처리합니다. 일반 전역 변수를 쓰면 A요청의 request_id가 B요청에 섞일 수 있습니다. ContextVar는 각 실행 흐름(task)마다 독립적인 값을 가지므로 이 문제가 없습니다.

---

## 7. 데이터는 어디에 저장되나?

### 저장소 비교표

| 저장소 | 저장하는 것 | 보관 기간 | 특징 |
|--------|-----------|-----------|------|
| **Prometheus TSDB** | 메트릭(숫자) | 90일 | 백엔드 재시작 시 in-memory 초기화, TSDB는 유지 |
| **OpenSearch app_logs** | 일반/에러 로그 | 30일 | 텍스트 검색 최적화, 재시작 무관 |
| **OpenSearch voice_pipeline** | 음성 처리 기록 | 90일 | 요청별 전체 파이프라인 요약 |
| **OpenSearch transfer_audit** | 이체 감사 로그 | 365일 | 금융 규제 대응, 1년 보관 |
| **PostgreSQL** | 비즈니스 데이터 | 영구 | 이체 이력, 자동이체 설정, 계좌 정보 |

### Prometheus가 데이터를 저장하는 방식

Prometheus는 **시계열 데이터베이스(TSDB)**입니다.
같은 메트릭을 시간순으로 쭉 저장합니다.

```
app_error_total{code="INSUFFICIENT_BALANCE"}
  14:00 → 5
  14:01 → 5
  14:02 → 7   ← 14:02에 에러 2건 발생
  14:03 → 7
  14:04 → 9   ← 14:04에 에러 2건 발생
```

이 데이터를 가지고 Grafana에서 그래프를 그립니다.

### 백엔드 재시작 시 어떻게 되나?

**Prometheus Counter**는 백엔드 메모리에 값을 유지합니다.
백엔드를 재시작하면 → 카운터가 0으로 초기화됩니다.

하지만 **Prometheus TSDB에는 재시작 전 기록이 그대로 남아 있습니다.**
그래서 Grafana 그래프에서 재시작 전 데이터는 볼 수 있지만, 재시작 직후 카운터 값이 갑자기 0으로 내려갑니다.

**OpenSearch와 PostgreSQL은 영향 없습니다.**  
별도의 독립적인 서버이기 때문에 백엔드가 재시작돼도 데이터가 그대로 유지됩니다.

---

## 8. 누적 데이터 vs 실시간 데이터

대시보드 패널을 보다 보면 두 가지 종류가 있습니다.

### 누적 데이터 (Cumulative)

**"지금까지 총 몇 건이야?"** 를 보여주는 패널들입니다.

예시:
- 이체 성공/실패 총 건수
- ASV 인증 결과 분포 (pass/fail 총 횟수)
- AppError 코드별 총 발생 건수

**좋은 점:** 전체적인 규모와 비율을 파악할 수 있음  
**나쁜 점:** 백엔드 재시작 시 0으로 리셋될 수 있음 (Prometheus 기반인 경우)

**Grafana에서 보는 방법 (올바른 소스):**

| 패널 | 올바른 소스 | 이유 |
|------|-----------|------|
| ASV 인증 결과·통과율 | OpenSearch `voice_pipeline` (`asv_result`) | 재시작 후에도 유지 |
| AppError 코드별 건수·기능별 에러 | OpenSearch `app_logs` (`event:app_error`) | 재시작 후에도 유지 |
| 이체 성공/실패 건수 | OpenSearch `transfer_audit` (`status`) | 365일 감사 로그 활용 |
| 자동이체 스케줄러 성공/실패 | OpenSearch `app_logs` (`event:auto_transfer_executed`) | 재시작 후에도 유지 |
| 서비스별 성공/실패 누적 | OpenSearch `app_logs` (`event:external_api_call`) | 재시작 후에도 유지 |
| 에이전트 액션별 실행 횟수 | OpenSearch `voice_pipeline` (`intent`) | 재시작 후에도 유지 |

### 실시간 데이터 (Real-time)

**"지금 이 순간 어떤 상태야?"** 를 보여주는 패널들입니다.

예시:
- 파이프라인 성공률 (최근 5분 기준)
- 전체 에러율 (최근 5분 기준)
- 초당 음성 요청 수

**좋은 점:** 현재 상태 즉각 파악, 재시작해도 영향 없음  
**나쁜 점:** 요청이 없으면 No Data 뜸

**Grafana에서 보는 방법:**
```promql
rate(http_requests_total[5m])    → 최근 5분 평균 초당 요청 수
increase(app_error_total[5m])    → 최근 5분 에러 증가량
```

### 핵심 PromQL 함수 설명

| 함수 | 의미 | 예시 |
|------|------|------|
| `rate(X[5m])` | 5분 평균 초당 변화량 | `rate(transfer_total[5m])` |
| `increase(X[5m])` | 5분 동안 총 증가량 | `increase(app_error_total[5m])` |
| `sum(X)` | 모든 레이블 합산 | `sum(asv_verification_total)` |
| `topk(1, X)` | 가장 큰 값 1개 | `topk(1, app_error_total)` |
| `histogram_quantile(0.95, ...)` | 상위 95% 지점 값 (P95) | P95 응답시간 |

---

## 9. 대시보드 4개 완전 해설

Grafana에 4개의 대시보드가 있습니다.

### 9-1. 음성 파이프라인 현황

**"우리 음성 서비스가 지금 잘 돌아가고 있나?"** 를 한눈에 봅니다.

| 패널 | 무엇을 보나 | 데이터 소스 | 판단 기준 |
|------|-----------|------------|---------|
| 파이프라인 성공률 | 최근 5분 음성 API 성공 비율 | Prometheus | 95% 이상이면 정상 |
| P50/P95/P99 응답시간 | 사용자 대기 시간 분위 | Prometheus | P95 3초 이하면 양호 |
| STT/Agent/TTS 단계별 레이턴시 | 어느 단계가 병목인가 | Prometheus | 상대적 비교 |
| ASV 인증 결과 | pass/fail 건수 분포 | **OpenSearch** `voice_pipeline` | fail 급증 시 경보 |
| ASV 통과율 | ASV 인증 성공 비율 | **OpenSearch** `voice_pipeline` | 80% 이상이면 정상 |
| 단계별 레이턴시 시계열 | 시간에 따른 레이턴시 변화 | Prometheus | 급등 구간 발견 |
| 초당 음성 요청 수 | 트래픽 추이 | Prometheus | 갑자기 급증하면 부하 의심 |
| Tool별 평균 실행시간 | 어떤 Tool이 가장 느린가 | Prometheus | 특정 Tool만 느리면 해당 기능 점검 |
| Tool별 실행시간 추이 | Tool 실행시간 시계열 | Prometheus | 특정 시각 이후 느려졌다면 원인 추적 |
| 에이전트 액션별 실행 횟수 | 어떤 기능이 많이 쓰이나 | **OpenSearch** `voice_pipeline` | 사용 패턴 파악 |
| 인텐트 분포 | 이체/잔액조회/거래내역 등 비율 | OpenSearch `voice_pipeline` | 가장 정확한 누적 사용 패턴 |

### 9-2. 에러 분석

**"어떤 에러가 얼마나, 언제 발생했나?"** 를 진단합니다.

| 패널 | 무엇을 보나 | 데이터 소스 |
|------|-----------|------------|
| HTTP 5xx 발생 건수 | 최근 5분 서버 에러 건수 | Prometheus |
| 전체 에러율 | 4xx + 5xx 비율 | Prometheus |
| 최다 발생 에러 코드 | 지금 가장 많이 나는 에러 | Prometheus |
| HTTP 4xx/5xx 비율 시계열 | 에러율 변화 추이 | Prometheus |
| AppError 코드별 발생 건수 | 에러 코드별 누적 건수 | **OpenSearch** `app_logs` |
| 에러 스파이크 타임라인 | 에러가 언제 급증했나 | Prometheus |
| 에러 코드별 발생 추이 | 특정 에러가 언제 시작됐나 | Prometheus |
| 에러 로그 검색 | 실제 에러 메시지 원문 확인 | OpenSearch `app_logs` |
| 기능별 에러 분포 | 어느 기능(인증/이체/ASV...)에 에러 집중 | **OpenSearch** `app_logs` |

**에러 코드 분류:**

| 카테고리 | 에러 코드들 |
|---------|-----------|
| 인증 | TOKEN_INVALID, UNAUTHORIZED, USER_NOT_FOUND |
| 음성 처리 | STT_FAILED, VOICE_AUDIO_INVALID_FORMAT, VOICE_AUDIO_TOO_LARGE 등 |
| ASV | ASV_NOT_ENROLLED, ASV_SERVER_ERROR, ASV_TIMEOUT |
| 이체 | INSUFFICIENT_BALANCE, ACCOUNT_NOT_FOUND, TRANSFER_PENDING 등 |
| 자동이체 | AUTO_ORDER_NOT_FOUND, AUTO_ORDER_STATUS_INVALID 등 |
| 에이전트 | AGENT_CONFIG_ERROR, AGENT_INIT_FAILED |
| 이벤트 | EVENT_NOT_FOUND, ALREADY_PARTICIPATED |
| 기타 | INTERNAL_ERROR, SERVICE_UNAVAILABLE 등 |

### 9-3. 금융 거래 현황

**"이체와 자동이체가 잘 처리되고 있나?"** 를 봅니다.

| 패널 | 무엇을 보나 | 데이터 소스 |
|------|-----------|------------|
| 이체 성공/실패 건수 | 이체 결과 누적 건수 | **OpenSearch** `transfer_audit` |
| 자동이체 스케줄러 누적 성공/실패 | 스케줄러 누적 실행 결과 | **OpenSearch** `app_logs` |
| 자동이체 누적 실행 이력 | 전체 자동이체 실행 총 건수 | PostgreSQL |
| 자동이체 등록 건수 | 현재 활성 자동이체 수 | PostgreSQL |
| 이체 실패율 시계열 | 시간에 따른 이체 실패율 변화 | Prometheus |
| 시간대별 이체 건수 | 몇 시에 이체가 많이 발생하나 | OpenSearch `transfer_audit` |
| 최근 이체 감사 로그 | 최근 이체 상세 내역 | OpenSearch `transfer_audit` |

### 9-4. 외부 API 상태

**"Clova STT와 Azure TTS가 정상인가?"** 를 봅니다.

| 패널 | 무엇을 보나 | 데이터 소스 |
|------|-----------|------------|
| Clova STT 에러율 | STT API 실패 비율 | Prometheus |
| Azure TTS 에러율 | TTS API 실패 비율 | Prometheus |
| /health 엔드포인트 상태 | 백엔드 서버가 살아있나 | Prometheus |
| Clova STT 응답시간 추이 | STT 응답 속도 변화 | Prometheus |
| Azure TTS 응답시간 추이 | TTS 응답 속도 변화 | Prometheus |
| 서비스별 성공/실패 누적 | 각 외부 서비스 총 성공/실패 건수 | **OpenSearch** `app_logs` |

---

## 10. 알림 시스템

Grafana Alerting을 사용해 이상 상황을 Slack으로 자동 통보합니다.

### 알림 상태 흐름

```
Normal → Pending → Firing → Resolved
```

| 상태 | 의미 |
|------|------|
| **Normal** | 정상. 임계값 이하 |
| **Pending** | 임계값 초과 중. 아직 알림 미전송 (오탐 방지를 위해 일정 시간 대기) |
| **Firing** | 임계값 초과 상태가 지속됨. Slack 알림 전송 |
| **Resolved** | 다시 정상으로 돌아옴. Slack에 해제 알림 전송 |

### 왜 Pending 상태가 있나?

잠깐 스파이크가 생겼다가 바로 회복되는 경우에 알림이 뜨면 피로감이 쌓입니다.
Pending 시간(보통 1~5분) 동안 계속 임계값을 초과해야만 실제 알림이 갑니다.

### Grafana Alerting 설정 위치

```
Grafana UI → Alerting → Alert rules
```

현재 설정은 Grafana UI에서 직접 했기 때문에 **grafana-data Docker 볼륨**에 저장됩니다.
버전 관리를 원하면 YAML 파일로 내보내서 저장소에 보관해야 합니다.

---

## 11. 자주 겪는 문제와 해석법

### 패널에 "No Data"가 뜨는 경우

**원인 1:** 아직 해당 이벤트가 한 번도 발생하지 않았음  
→ 기다리거나 테스트 요청을 보내서 데이터 생성

**원인 2:** rate() 함수인데 요청 빈도가 너무 낮음  
→ 시간 범위를 늘리거나 쿼리 window를 늘림 (예: [5m] → [30m])

**원인 3:** 백엔드 재시작 직후 Prometheus 스크래핑 전  
→ 15~30초 대기

### 그래프가 갑자기 0으로 떨어지는 경우

**원인:** 백엔드가 재시작됨  
→ Prometheus Counter가 초기화됨  
→ `업타임 / 마지막 재시작 시각` 패널 확인

### 인텐트 분포 패널에 값이 안 뜨는 경우

**원인:** ASV 인증을 통과해야 인텐트가 기록됨  
→ ASV pass 없이는 voice_pipeline 로그가 OpenSearch에 안 들어감  
→ ASV 인증 결과 패널에서 pass 건수 확인

### 같은 에러 코드가 여러 줄로 나뉘어 보이는 경우

**원인:** 백엔드 재시작으로 Prometheus 라벨 시리즈가 새로 생성됨  
→ sum() 으로 감싸서 합산하거나 기간 필터 사용

---

---

## 12. 수집하는 모든 데이터 흐름 상세

---

### 전체 데이터 흐름 한눈에 보기

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI 백엔드                                │
│                                                                     │
│  [HTTP 요청 진입]                                                    │
│       │                                                             │
│       ▼                                                             │
│  [prometheus-fastapi-instrumentator]  ──► http_requests_total       │
│                                          http_request_duration_sec  │
│       │                                                             │
│       ▼                                                             │
│  [middleware.py]  ──────────────────► request_id (ContextVar)       │
│       │           구조화 JSON 로그     request_start / request_end   │
│       │                                                             │
│       ▼                                                             │
│  [voice/router.py]                                                  │
│       ├─► ASV 호출 ───────────────────► asv_verification_total      │
│       ├─► Clova STT 호출 ─────────────► voice_stage_duration(stt)   │
│       │                                external_api_calls_total     │
│       ├─► LangGraph 에이전트 ─────────► voice_stage_duration(agent) │
│       │       └─► [graph.py]           agent_node_executions_total  │
│       │               └─► Tool 실행    agent_tool_duration_seconds  │
│       ├─► Azure TTS 호출 ─────────────► voice_stage_duration(tts)   │
│       │                                external_api_calls_total     │
│       └─► opensearch_writer ──────────► voice_pipeline 인덱스       │
│                                                                     │
│  [transfer/service.py] ───────────────► transfer_total             │
│                         감사 로그      transfer_audit 인덱스        │
│                                                                     │
│  [scheduler.py] ──────────────────────► auto_transfer_scheduler    │
│                                          _runs_total               │
│                                                                     │
│  [main.py - app_error_handler] ───────► app_error_total            │
│                                  로그  app_logs 인덱스             │
└─────────────────────────────────────────────────────────────────────┘
         │ (모든 로그 stdout/stderr)          │ (모든 Prometheus 메트릭)
         ▼                                   ▼
    [Logstash]                         [Prometheus /metrics 스크래핑]
         │                                   │ 15초마다
         ▼                                   ▼
    [OpenSearch]                        [Prometheus TSDB]
    ├── app_logs (30일)                 (90일 보관)
    ├── voice_pipeline (90일)
    └── transfer_audit (365일)
                    │                        │
                    └──────────┬─────────────┘
                               ▼
                    [PostgreSQL] ◄── 비즈니스 데이터
                               │
                               ▼
                          [Grafana]
                    ├── 음성 파이프라인 현황
                    ├── 에러 분석
                    ├── 금융 거래 현황
                    └── 외부 API 상태
```

---

### 데이터 1: HTTP 요청/응답 메트릭

**무엇을 측정하나:** API 요청의 수, 응답 상태, 응답 시간

```
[사용자 앱]
    │  POST /api/voice/voice
    ▼
[FastAPI]
    │
    ▼
[prometheus-fastapi-instrumentator]   ← 자동 계측 라이브러리
    │  모든 HTTP 요청/응답을 자동으로 가로채서 기록
    │
    ├─► http_requests_total{handler, method, status}
    │       예) http_requests_total{handler="/api/voice/voice", status="2xx"} = 1234
    │
    └─► http_request_duration_seconds{handler}
            예) P95 응답시간: 1.23초
    │
    ▼
[/metrics 엔드포인트]  ← GET http://backend:8000/metrics 로 노출
    │
    ▼  (15초마다 자동 수집)
[Prometheus]
    │  저장 형식: 시계열 (시각 + 값)
    │  보관: 90일
    ▼
[Grafana - 음성 파이프라인 현황]
    ├── 파이프라인 성공률
    │     rate(http_requests_total{status="2xx"}[5m])
    │     / rate(http_requests_total[5m]) * 100
    │
    ├── P50/P95/P99 응답시간
    │     histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
    │
    └── 초당 음성 요청 수
          rate(http_requests_total{handler="/api/voice/voice"}[1m])

[Grafana - 에러 분석]
    ├── HTTP 5xx 발생 건수
    │     increase(http_requests_total{status="5xx"}[5m])
    │
    ├── 전체 에러율
    │     rate(http_requests_total{status=~"4xx|5xx"}[5m])
    │     / rate(http_requests_total[5m]) * 100
    │
    └── HTTP 4xx/5xx 비율 시계열
          (위와 동일, 시계열 그래프로 표시)
```

**핵심 포인트:**
- `handler` 레이블: 어느 API 경로인지 (`/api/voice/voice`, `/api/transfer/execute` 등)
- `status` 레이블: `2xx`, `4xx`, `5xx` 중 하나
- 라이브러리가 자동으로 처리하므로 개발자가 코드 추가할 필요 없음

---

### 데이터 2: ASV 화자 인증 결과

**무엇을 측정하나:** 음성 인증의 pass/fail 건수

```
[voice/router.py]
    │
    │  사용자 음성 → ASV 서버에 전송
    ▼
[ASV 서버 응답]
    │
    ├── result = "pass" → 본인 목소리로 인증됨
    └── result = "fail" → 목소리 불일치
    │
    ▼
[metrics.py - asv_verification_total.labels(result=result).inc()]
    │  asv_verification_total{result="pass"} += 1
    │  asv_verification_total{result="fail"} += 1
    ▼
[/metrics 엔드포인트]
    │
    ▼  (15초마다)
[Prometheus TSDB]
    │  보관: 90일
    │  재시작 시 in-memory 리셋, TSDB는 유지
    │
    │  누적 집계용 → OpenSearch voice_pipeline 직접 기록
    ├─► asyncio.create_task(write_voice_pipeline_record_async({
    │       "asv_result": "pass",  # "fail"
    │       "user_id": user_id,
    │       "success": True
    │   }))
    │
    ▼ 두 경로로 동시에 저장

  [경로 A: Prometheus — 실시간 에러율/추이]
    /metrics → Prometheus TSDB
    ▼
  [Grafana - 음성 파이프라인 현황 (실시간 참고용)]
      asv_verification_total (재시작 시 리셋 주의)

  [경로 B: OpenSearch — 누적 집계]
    write_voice_pipeline_record_async()
    → voice_pipeline 인덱스 (asv_result 필드)
    ▼
  [Grafana - 음성 파이프라인 현황]
    ├── ASV 인증 결과 (bargauge)
    │     index: voice_pipeline
    │     query: asv_result:pass / asv_result:fail
    │     → 재시작 후에도 누적값 유지
    │
    └── ASV 통과율 (stat)
          pass count / total count → percentunit
          → 재시작 후에도 정확한 통과율
```

**주의점:**
- Prometheus Counter는 실시간 에러율/추이에만 사용
- 누적 분포·통과율은 OpenSearch voice_pipeline에서 조회

---

### 데이터 3: 음성 파이프라인 단계별 레이턴시

**무엇을 측정하나:** STT, Agent, TTS 각 단계가 얼마나 걸렸는지

```
[voice/router.py]

  ┌─── STT 단계 ───────────────────────────────────────┐
  │  with voice_stage_duration.labels(stage="stt").time():
  │      text = await call_clova_stt(audio_file)
  │  → STT 처리 시작부터 응답 받을 때까지 자동 측정     │
  └───────────────────────────────────────────────────┘
         │ observe(0.45초 걸렸다면)
         ▼
  voice_pipeline_stage_duration_seconds{stage="stt"}
      _count += 1          (호출 횟수)
      _sum   += 0.45       (누적 시간)
      _bucket{le="0.5"} += 1  (0.5초 이하 버킷 증가)

  ┌─── Agent 단계 ──────────────────────────────────────┐
  │  with voice_stage_duration.labels(stage="agent").time():
  │      response = await run_agent(text)               │
  └───────────────────────────────────────────────────┘
         │ observe(1.20초 걸렸다면)
         ▼
  voice_pipeline_stage_duration_seconds{stage="agent"}
      _sum += 1.20

  ┌─── TTS 단계 ───────────────────────────────────────┐
  │  with voice_stage_duration.labels(stage="tts").time():
  │      audio = await call_azure_tts(response_text)   │
  └───────────────────────────────────────────────────┘
         │ observe(0.30초 걸렸다면)
         ▼
  voice_pipeline_stage_duration_seconds{stage="tts"}
      _sum += 0.30

    ▼ (모든 단계 누적)
[/metrics]
    │
    ▼  (15초마다)
[Prometheus TSDB]
    ▼
[Grafana - 음성 파이프라인 현황]
    ├── STT/Agent/TTS 단계별 평균 레이턴시 (bargauge)
    │     rate(voice_pipeline_stage_duration_seconds_sum{stage="stt"}[5m])
    │     / rate(voice_pipeline_stage_duration_seconds_count{stage="stt"}[5m])
    │     * 1000  → ms 단위
    │
    ├── 단계별 레이턴시 시계열 (timeseries)
    │     → 위와 동일 쿼리, 시간 축으로 그래프
    │
    └── P50/P95/P99 전체 응답시간 (stat)
          histogram_quantile(0.95,
            rate(http_request_duration_seconds_bucket[5m]))
```

**Histogram이 특별한 이유:**
```
observe(0.45)가 호출되면 자동으로:
  bucket{le="0.1"}  → 초과 (0.45 > 0.1)
  bucket{le="0.3"}  → 초과 (0.45 > 0.3)
  bucket{le="0.5"}  → 포함 ✓ (0.45 ≤ 0.5)
  bucket{le="1.0"}  → 포함 ✓
  bucket{le="2.0"}  → 포함 ✓
  ...

이 버킷 정보로 나중에 "P95는 몇 초인가?"를 역산할 수 있음
```

---

### 데이터 4: 외부 API 호출 성공/실패

**무엇을 측정하나:** Clova STT, Azure TTS API 각각 성공/실패 건수

```
[voice/router.py]

  ── Clova STT 호출 ──────────────────────────────────────
  try:
      text = await call_clova_stt(audio)
      external_api_calls_total
          .labels(service="clova_stt", status="success").inc()
                                  │
  except Exception:               │
      external_api_calls_total    │
          .labels(service="clova_stt", status="error").inc()
  ─────────────────────────────────────────────────────────

  ── Azure TTS 호출 ──────────────────────────────────────
  try:
      audio = await call_azure_tts(text)
      external_api_calls_total
          .labels(service="azure_tts", status="success").inc()

  except Exception:
      external_api_calls_total
          .labels(service="azure_tts", status="error").inc()
  ─────────────────────────────────────────────────────────

    ▼
[/metrics]
    │
    ▼  (15초마다)
[Prometheus TSDB]
    │
    │  구조화 로그 추가 → app_logs로 전송
    ├─► logger.info("external_api_call", extra={
    │       "event": "external_api_call",
    │       "service": "clova_stt",  # or "azure_tts"
    │       "status": "success"      # or "error"
    │   })
    │
    ▼ 두 경로로 동시에 저장

  [경로 A: Prometheus — 실시간 에러율]
    /metrics → Prometheus TSDB
    ▼
  [Grafana - 외부 API 상태 (실시간)]
    ├── Clova STT 에러율 (stat)
    │     rate(external_api_calls_total{service="clova_stt",status="error"}[5m])
    │     / rate(external_api_calls_total{service="clova_stt"}[5m]) * 100
    │
    └── Azure TTS 에러율 (stat)
          rate(external_api_calls_total{service="azure_tts",status="error"}[5m])
          / rate(external_api_calls_total{service="azure_tts"}[5m]) * 100

  [경로 B: OpenSearch — 누적 성공/실패]
    JSON 로그 → Fluent Bit → app_logs 인덱스
    ▼
  [Grafana - 외부 API 상태]
    └── 서비스별 성공/실패 누적 (bargauge)
          index: app_logs
          query: event:external_api_call AND service:clova_stt AND status:success
          → 재시작 후에도 전체 누적값 유지
```

---

### 데이터 5: 에이전트 Tool 실행 횟수 및 시간

**무엇을 측정하나:** 각 Tool(잔액조회, 이체, 거래내역 등)이 몇 번 실행됐고 얼마나 걸렸는지

```
[agent/graph.py - execute_node 함수]
    │
    │  LangGraph가 Tool 실행을 결정하면 execute_node에 도달
    │
    ├─► agent_node_executions_total.labels(node="pending_action").inc()
    │       → "이 Tool이 1번 더 실행됐다"
    │
    └─► with agent_tool_duration_seconds.labels(node=tool_name).time():
            result = tool.invoke(args)
        → Tool 실행 시간 자동 측정
        → agent_tool_duration_seconds{node="get_total_balance"} 에 기록

    ▼
[/metrics]
    │
    ▼  (15초마다)
[Prometheus TSDB]
    ▼
[Grafana - 음성 파이프라인 현황]
    ├── 에이전트 액션별 실행 횟수 (bargauge)
    │     agent_node_executions_total
    │     → 각 node 레이블별 막대
    │
    ├── Tool별 평균 실행시간 (bargauge)
    │     agent_tool_duration_seconds_sum
    │     / agent_tool_duration_seconds_count * 1000
    │
    └── Tool별 실행시간 추이 (timeseries)
          histogram_quantile(0.95,
            rate(agent_tool_duration_seconds_bucket[$__rate_interval])) * 1000
```

**중요한 제약:**
```
execute_node는 에이전트가 Tool 실행을 "결정"했을 때만 도달합니다.
사용자가 말을 해도:
  - 잘못된 인텐트 분류 → execute_node 미도달 → 카운터 증가 안 함
  - ASV 실패 → 에이전트 자체 실행 안 됨 → 카운터 증가 안 함

따라서 이 데이터는 "실제 Tool이 실행된 경우"만 카운트합니다.
인텐트 분포(OpenSearch)와 숫자가 다를 수 있습니다.
```

---

### 데이터 6: 이체 실행 결과

**무엇을 측정하나:** 이체 성공/실패 건수

```
[features/transfer/service.py 또는 agent/tools/transfer.py]
    │
    │  이체 처리 시도
    │
    ├── 성공 시:
    │     transfer_total.labels(status="success").inc()
    │
    └── 실패 시:
          transfer_total.labels(status="fail").inc()

    ▼ (동시에 감사 로그도 기록)
    logger.info("transfer_audit", extra={
        "event": "transfer_audit",
        "from_account": "...",
        "to_account":   "...",
        "amount":       50000,
        "status":       "success",
        "request_id":   get_request_id()  ← 추적용
    })

    ▼
[두 갈래로 분리]

  [갈래 1 - Prometheus — 실시간 추이]
    /metrics → Prometheus 스크래핑 → TSDB
    ▼
  [Grafana - 금융 거래 현황 (실시간)]
      └── 이체 실패율 시계열 (timeseries)
            rate(transfer_total{status="fail"}[5m])
            / rate(transfer_total[5m]) * 100

  [갈래 2 - OpenSearch — 누적 + 감사 로그]
    JSON 로그 → stdout → Fluent Bit → OpenSearch transfer_audit 인덱스
    보관: 365일 (금융 규제 대응)
    ▼
  [Grafana - 금융 거래 현황]
      ├── 이체 성공/실패 건수 (stat)  ← Prometheus에서 이전
      │     index: transfer_audit
      │     query: status:success / status:failed → reduce sum
      │
      ├── 최근 이체 감사 로그 (table)
      │     raw_data 쿼리, 최신 50건
      │
      └── 시간대별 이체 건수 (timeseries)
            date_histogram 집계
```

---

### 데이터 7: 자동이체 스케줄러 실행 결과

**무엇을 측정하나:** APScheduler가 자동이체를 실행할 때마다 성공/실패 건수

```
[APScheduler 스케줄러]
    │
    │  매일 설정된 시각에 자동 실행
    │
    ├── 성공 시:
    │     auto_transfer_scheduler_runs_total.labels(status="success").inc()
    │     logger.info("auto_transfer_executed", extra={"event": "auto_transfer_executed", "status": "success"})
    │
    └── 실패 시:
          auto_transfer_scheduler_runs_total.labels(status="failed").inc()
          logger.info("auto_transfer_executed", extra={"event": "auto_transfer_executed", "status": "failed"})

    ▼ 두 경로로 동시에 저장

  [경로 A: Prometheus — 실시간 참고]
    /metrics → TSDB (재시작 시 리셋)

  [경로 B: OpenSearch — 누적 집계]
    JSON 로그 → Fluent Bit → app_logs 인덱스
    ▼
  [Grafana - 금융 거래 현황]
    └── 자동이체 스케줄러 누적 성공/실패 (stat)  ← Prometheus에서 이전
          index: app_logs
          query: event:auto_transfer_executed AND status:success/failed

[PostgreSQL] ← 별도로 실행 이력 저장 (비즈니스 데이터)
    ▼
[Grafana - 금융 거래 현황]
    ├── 자동이체 누적 실행 이력 (stat)
    │     PostgreSQL 직접 쿼리: SELECT COUNT(*) FROM auto_transfer_logs
    │
    └── 자동이체 등록 건수 (stat)
          PostgreSQL 직접 쿼리: SELECT COUNT(*) FROM auto_transfer_orders
```

---

### 데이터 8: 에러 데이터 (가장 복잡 - 두 경로 동시)

**무엇을 측정하나:** 어떤 에러가 언제, 얼마나 발생했는지

에러 데이터는 **Prometheus(숫자)** 와 **OpenSearch(원문 로그)** 두 곳에 동시에 기록됩니다.

```
[애플리케이션 어느 곳에서든 AppError 발생]
    │
    │  예) 잔액이 부족한 경우:
    │      raise AppError(code="INSUFFICIENT_BALANCE", ...)
    │
    ▼
[main.py - app_error_handler]  ← 전역 에러 핸들러
    │
    │  두 가지 작업을 동시에 수행:
    │
    ├─► [경로 A: Prometheus 메트릭 — 실시간 추이]
    │       app_error_total.labels(code="INSUFFICIENT_BALANCE").inc()
    │       │
    │       ▼
    │   /metrics → 15초마다 Prometheus 스크래핑 → TSDB (90일)
    │       │
    │       ▼
    │   [Grafana - 에러 분석 (실시간)]
    │       ├── 최다 발생 에러 코드    topk(1, app_error_total)
    │       ├── 에러 코드별 발생 추이  timeseries
    │       └── HTTP 4xx/5xx 비율·스파이크 타임라인
    │
    └─► [경로 B: OpenSearch 로그 — 누적 집계 + 원문]
            logger.error("app_error", extra={
                "event":        "app_error",
                "code":         "INSUFFICIENT_BALANCE",
                "status_code":  422,
                "feature":      "transfer",    ← 요청 URL에서 자동 추출 (신규)
                "request_id":   "abc-123-def"  ← 추적 가능
            })
            │
            │  JSON 형태로 stdout 출력
            ▼
        [_AppJsonFormatter] ← logging_config.py
            {
              "timestamp":  "2026-06-08T14:23:11",
              "level":      "ERROR",
              "request_id": "abc-123-def",
              "event":      "app_error",
              "code":       "INSUFFICIENT_BALANCE",
              "feature":    "transfer"
            }
            │
            ▼
        [Fluent Bit] ← stdout 수집
            │  인덱스 라우팅: → app_logs
            ▼
        [OpenSearch - app_logs] (30일 보관)
            │
            ▼
        [Grafana - 에러 분석]
            ├── AppError 코드별 발생 건수  ← Prometheus에서 이전
            │     event:app_error + terms agg on code
            ├── 기능별 에러 분포           ← Prometheus에서 이전
            │     event:app_error + terms agg on feature
            └── 에러 로그 검색 (table)
                  level:ERROR 필터, 최신 30건
                  → 실제 에러 메시지 원문 확인 가능
```

**왜 두 군데에 저장하나?**

| | Prometheus (숫자) | OpenSearch (원문) |
|--|--|--|
| 용도 | "에러가 몇 번?" 집계 | "정확히 어떤 에러였나?" 디버깅 |
| 검색 | PromQL로 집계/비율 계산 | 키워드로 원문 검색 |
| 보관 | 90일 | 30일 |
| 장점 | 빠른 집계, 그래프 | 상세 맥락, request_id 추적 |

---

### 데이터 9: 음성 파이프라인 요약 로그 (OpenSearch)

**무엇을 측정하나:** 음성 요청 하나의 전체 처리 결과 요약

```
[voice/router.py]
    │
    │  모든 처리(STT, 에이전트, TTS)가 완료된 직후
    │
    ▼
[opensearch_writer.py - write_voice_pipeline_record_async()]
    │
    │  비동기 fire-and-forget 방식
    │  (응답 속도에 영향 없도록 백그라운드 실행)
    │
    ▼
[OpenSearch 클라이언트]
    │  직접 HTTP POST → OpenSearch
    │  (Logstash를 거치지 않음, 백엔드가 직접 전송)
    │
    ▼
[OpenSearch - voice_pipeline 인덱스] (90일 보관)
    │
    │  저장되는 문서 예시:
    │  {
    │    "timestamp":  "2026-06-08T14:23:11",
    │    "request_id": "abc-123-def",
    │    "user_id":    "user_456",
    │    "intent":     "transfer",
    │    "stt_ms":     450,
    │    "agent_ms":   850,
    │    "tts_ms":     320,
    │    "success":    true
    │  }
    │
    ▼
[Grafana - 음성 파이프라인 현황]
    └── 인텐트 분포 (bargauge)
          intent:transfer   → count
          intent:balance    → count
          intent:auto_transfer → count
          intent:history    → count
          intent:unknown    → count
```

**fire-and-forget가 뭔가요?**
```
일반 방식:
  처리 → OpenSearch 전송 완료 대기 → 응답 반환
  (OpenSearch가 느리면 사용자도 기다려야 함)

fire-and-forget 방식:
  처리 → 응답 먼저 반환 → 백그라운드에서 OpenSearch 전송
  (사용자는 기다리지 않음, 전송 실패해도 서비스 영향 없음)

단점: OpenSearch가 다운되면 이 데이터는 유실됨 (로그만 경고 출력)
```

---

### 데이터 10: request_id 전파 흐름

**무엇을 측정하나:** 요청 하나의 전체 여정 추적

```
[클라이언트 앱]
    │  헤더에 X-Request-ID 포함 가능 (선택)
    │  없으면 서버가 자동 생성
    ▼
[middleware.py - RequestLoggingMiddleware]
    │
    │  1. X-Request-ID 헤더 확인
    │     있으면 → 그 값 사용
    │     없으면 → UUID 새로 생성 (예: "a1b2c3d4-e5f6-...")
    │
    │  2. ContextVar에 저장
    │     request_id_var.set("a1b2c3d4-e5f6-...")
    │
    │  3. 응답 헤더에 포함
    │     response.headers["X-Request-ID"] = "a1b2c3d4-e5f6-..."
    │
    ▼
[_RequestIdFilter - logging_config.py]
    │
    │  모든 로그 출력 시 자동으로 request_id 필드 추가
    │  개발자가 직접 넣지 않아도 됨
    │
    ▼
[모든 로그에 자동 포함]
  request_start:        {"request_id": "a1b2c3d4-..."}
  STT 호출 로그:        {"request_id": "a1b2c3d4-..."}
  에이전트 실행 로그:   {"request_id": "a1b2c3d4-..."}
  이체 실행 로그:       {"request_id": "a1b2c3d4-..."}
  app_error 로그:       {"request_id": "a1b2c3d4-..."}
  request_end:          {"request_id": "a1b2c3d4-..."}
    │
    ▼
[OpenSearch]
    │
    │  Grafana에서 검색:
    │  request_id:"a1b2c3d4-e5f6-..."
    │
    ▼
[결과: 이 요청의 전체 여정이 순서대로 조회됨]
  14:23:10.001  request_start   feature=voice
  14:23:10.150  asv_pass        result=pass
  14:23:10.600  stt_complete    duration_ms=450
  14:23:11.450  agent_complete  intent=transfer
  14:23:11.460  transfer_done   amount=50000 status=success
  14:23:11.780  tts_complete    duration_ms=330
  14:23:11.781  request_end     status=200 duration_ms=1780
```

**ContextVar가 필요한 이유:**
```
FastAPI는 여러 요청을 동시에 처리합니다.

전역 변수로 저장하면:
  요청A가 request_id = "aaa" 저장
  요청B가 request_id = "bbb" 저장 (덮어씀!)
  요청A의 로그가 "bbb"로 기록됨 → 추적 불가

ContextVar는:
  요청A의 실행 흐름에서는 항상 "aaa"
  요청B의 실행 흐름에서는 항상 "bbb"
  → 서로 간섭 없음
```

---

### 데이터 11: 사전 초기화된 에러 카운터

**무엇을 측정하나:** 에러 발생 전에도 Grafana에서 0으로 표시하기 위한 초기화

```
[metrics.py - 서버 시작 시 1회 실행]
    │
    │  36개 에러 코드를 미리 등록:
    │
    for _code in ["TOKEN_INVALID", "UNAUTHORIZED", ...36개...]:
        app_error_total.labels(code=_code)
    │
    │  이렇게 하면:
    │  아직 한 번도 발생하지 않은 에러도
    │  Prometheus에 "0"으로 존재함
    │
    ▼
[/metrics]
    app_error_total{code="TOKEN_INVALID"}     0
    app_error_total{code="INSUFFICIENT_BALANCE"} 0
    app_error_total{code="ASV_TIMEOUT"}       0
    ... (36개 모두 0으로 노출)
    │
    ▼
[Grafana - 에러 분석 - AppError 코드별 발생 건수]
    → 에러가 한 번도 안 났어도 모든 코드가 0으로 표시
    → "이 에러는 아직 발생 안 했다"는 정보 자체가 의미 있음
```

**사전 초기화 안 하면?**
```
에러가 발생하기 전까지는 Prometheus에 해당 시리즈가 없음
→ Grafana에서 아예 표시되지 않음
→ "없는 에러" = "한 번도 안 난 에러" 구분 불가
```

---

### 데이터 12: 로그 구조화 및 Logstash 전송 흐름

**무엇을 측정하나:** 모든 텍스트 로그가 OpenSearch에 도달하는 경로

```
[백엔드 어느 파일에서든]
    │
    │  logger.info("balance_query_result", extra={
    │      "event": "balance_query_result",
    │      "user_id": user_id,
    │      "total": 1500000
    │  })
    │
    ▼
[logging_config.py - _AppJsonFormatter]
    │
    │  Python LogRecord를 JSON 문자열로 변환:
    │  {
    │    "timestamp": "2026-06-08T14:23:11.123Z",
    │    "level":     "INFO",
    │    "logger":    "app.shared.agent.tools.balance",
    │    "message":   "balance_query_result",
    │    "request_id":"abc-123-def",     ← _RequestIdFilter가 자동 추가
    │    "event":     "balance_query_result",
    │    "user_id":   "user_456",
    │    "total":     1500000
    │  }
    │
    ▼
[Docker stdout/stderr]
    │  컨테이너가 표준 출력을 캡처
    │
    ▼
[Logstash 컨테이너]
    │  Docker 로그 드라이버 또는 파일 수집
    │
    │  인덱스 라우팅 규칙:
    │  level=ERROR  → app_logs
    │  level=INFO, event="transfer_audit" → transfer_audit
    │  level=INFO, 나머지 → app_logs
    │
    ▼
[OpenSearch]
    ├── app_logs       (30일)  ← 일반/에러 로그
    └── transfer_audit (365일) ← 이체 감사 로그

    ▼
[Grafana]
    ├── 에러 로그 검색 (table)
    │     index: app_logs, query: level:ERROR
    │
    └── 최근 이체 감사 로그 (table)
          index: transfer_audit, raw_data
```

---

### 전체 데이터 종합 요약표

| 데이터 | 수집 위치 | 수집 방법 | 저장소 | 보관 | 대시보드 패널 |
|--------|---------|---------|--------|------|-------------|
| HTTP 요청/응답 메트릭 | 자동 계측 라이브러리 | Histogram + Counter | Prometheus | 90일 | 성공률, 응답시간, 요청수 |
| ASV 인증 결과 | voice/router.py | Counter.inc() | Prometheus | 90일 | ASV 인증 결과, 통과율 |
| 음성 단계 레이턴시 | voice/router.py | Histogram.time() | Prometheus | 90일 | 단계별 레이턴시, 시계열 |
| 외부 API 성공/실패 | voice/router.py | Counter.inc() | Prometheus | 90일 | STT/TTS 에러율 |
| Tool 실행 횟수/시간 | agent/graph.py | Counter + Histogram | Prometheus | 90일 | 액션별 횟수, Tool 시간 |
| 이체 결과 | transfer/service.py | Counter.inc() | Prometheus | 90일 | 이체 성공/실패, 실패율 |
| 자동이체 스케줄러 | scheduler.py | Counter.inc() | Prometheus | 90일 | 스케줄러 성공/실패 |
| 에러 건수 | main.py (전역 핸들러) | Counter.inc() | Prometheus | 90일 | 에러 코드별 건수, 분포 |
| 에러 원문 로그 | main.py (전역 핸들러) | logger.error() | OpenSearch app_logs | 30일 | 에러 로그 검색 |
| 음성 파이프라인 요약 | opensearch_writer.py | 직접 HTTP 전송 | OpenSearch voice_pipeline | 90일 | 인텔트 분포 |
| 이체 감사 로그 | transfer/service.py | logger.info() | OpenSearch transfer_audit | 365일 | 감사 로그 테이블 |
| 자동이체 이력 | scheduler/service.py | DB write | PostgreSQL | 영구 | 누적 실행 이력 |
| 자동이체 등록 | auto_transfer API | DB write | PostgreSQL | 영구 | 등록 건수 |
| request_id | middleware.py | ContextVar | 모든 로그에 포함 | 로그와 동일 | 로그 검색 시 추적 |

---

## 핵심 파일 위치 정리

```
backend/
├── app/
│   └── core/
│       ├── metrics.py           ← Prometheus 메트릭 정의 (Counter, Histogram 8개)
│       ├── logging_config.py    ← JSON 로그 포매터, request_id 필터
│       ├── middleware.py        ← 요청 시작/종료 로그, request_id 생성
│       ├── request_context.py   ← request_id ContextVar 관리
│       └── opensearch_writer.py ← OpenSearch에 비동기 로그 전송
│
infra/
├── docker-compose.yml           ← 전체 서비스 실행 설정
├── prometheus/
│   └── prometheus.yml           ← 스크래핑 대상 설정 (백엔드 주소)
├── grafana/
│   └── provisioning/
│       └── dashboards/          ← 대시보드 JSON 파일 4개
│           ├── voice_pipeline.json
│           ├── errors.json
│           ├── financial.json
│           └── external_api.json
└── logstash/                    ← 로그 수집 → OpenSearch 전송 설정
```

---

## 한 줄 요약

```
사용자 음성 요청
    → FastAPI 미들웨어 (request_id 생성)
    → ASV 인증 (asv_verification_total 기록)
    → Clova STT (voice_stage_duration + external_api_calls_total 기록)
    → LangGraph 에이전트 (agent_node_executions_total + agent_tool_duration 기록)
    → Tool 실행 (transfer_total 등 기록)
    → Azure TTS (voice_stage_duration + external_api_calls_total 기록)
    → OpenSearch voice_pipeline 인덱스에 요약 저장
    → 에러 시 → OpenSearch app_logs + app_error_total 기록
    → Prometheus가 15초마다 메트릭 수집
    → Grafana가 Prometheus/OpenSearch/PostgreSQL 조회해서 대시보드 표시
    → 임계값 초과 시 Grafana Alerting → Slack 알림
```

---

## 13. `app_logs` 인덱스 완전 정리

### 저장 경로

```
Python 앱 → ~/woori-logs/app.log (JSON lines)
                    ↓
              Fluent Bit tail
              ┌──────────────────────────────────────┐
              │  event 값이 일치하면 transfer_audit   │
              │  (transfer_executed, agent_auto_*)    │ ← 이중 기록 (keep=true)
              └──────────────────────────────────────┘
                    ↓ 전체
              OpenSearch app_logs
```

### 인덱스 매핑 (명시 선언된 필드)

| 필드 | 타입 | 설명 |
|------|------|------|
| `timestamp` | date | KST 로그 시각 |
| `level` | keyword | INFO / WARNING / ERROR |
| `logger` | keyword | Python 모듈명 (app.core.middleware 등) |
| `request_id` | keyword | X-Request-ID (UUID) |
| `event` | keyword | 이벤트 식별자 (아래 표 참조) |
| `message` | text | 로그 메시지 원문 (full-text search 가능) |
| `feature` | keyword | voice / transfer / auth / asset 등 |
| `status_code` | integer | HTTP 상태코드 |
| `duration_ms` | integer | 처리 시간 (ms) |
| `method` | keyword | GET / POST 등 |
| `path` | keyword | /api/voice/voice 등 |
| `code` | keyword | AppError 코드 (`app_error` 이벤트 전용) |
| `service` | keyword | clova_stt / azure_tts (`external_api_call` 이벤트 전용) |
| `status` | keyword | success / error / failed (이벤트별 상태값) |

나머지 이벤트별 필드는 OpenSearch **dynamic mapping** 자동 생성

### 저장되는 이벤트 목록

| event 값 | 출처 | 추가 필드 |
|----------|------|----------|
| `request_start` | middleware.py | method, path, feature |
| `request_end` | middleware.py | status_code, duration_ms, feature |
| `app_error` | main.py | code, status_code, error_message, **feature** |
| `auto_transfer_executed` | main.py | job_id, status, [error] |
| `external_api_call` | stt_service.py / tts_service.py | **service** (clova_stt / azure_tts), **status** (success / error) |
| `voice_pipeline_complete` | voice/service.py | user_id, stt_ms, agent_ms, tts_ms, total_ms, intent, navigate_to |
| `agent_tool_call_start` | graph.py | tool, action, user_id, [amount] |
| `agent_tool_call_end` | graph.py | tool, action, user_id, duration_ms, success |
| `agent_transfer_completed` | graph.py | tx_id, user_id, amount |
| `agent_transfer_failed` | graph.py | user_id, reason |
| `agent_auto_transfer_registered` | graph.py / execute_auto_transfer.py | order_id, user_id, [amount, to_bank, recipient] |
| `auto_transfer_register_failed` | execute_auto_transfer.py | user_id, error_code, [error] |
| `transfer_executed` | transfer/service.py | user_id, tx_id, amount, to_bank, to_account_masked, status, duration_ms |
| `balance_query_result` | balance.py | user_id, total |
| `lookup_recipient_start` | lookup_recipient.py | user_id, recipient |
| `lookup_recipient_result` | lookup_recipient.py | user_id, result |
| `lookup_recipient_failed` | lookup_recipient.py | user_id, error |
| `execute_transfer_error` | transfer.py (tool) | user_id, code |
| `execute_transfer_failed` | transfer.py (tool) | user_id, error |
| `add_note_error` | transfer.py (tool) | user_id, code |
| `add_note_failed` | transfer.py (tool) | user_id, tx_id, error |

### `app_logs`로 오지 않는 데이터

| 데이터 | 이유 |
|--------|------|
| voice_pipeline 레이턴시 원본 | `voice_pipeline` 인덱스에 직접 기록 (OpenSearch Writer 별도 경로) |
| ASV 인증 결과 | `voice_pipeline` 인덱스에 직접 기록 (`asv_result` 필드) |

> STT/TTS 외부 API 성공/실패는 `event:external_api_call`로 **app_logs에 기록됨** (서비스별 성공/실패 누적 패널용)

### 이중 저장 (app_logs + transfer_audit 동시)

`transfer_executed`, `agent_auto_transfer_registered` 이벤트는  
Fluent Bit `rewrite_tag` 필터로 `transfer_audit`에도 복사됨  
(Fluent Bit `keep=true` 옵션 → app_logs에도 그대로 유지)

---

## 14. `voice_pipeline` 인덱스 완전 정리

### 저장 경로

```
voice/service.py
  └─ _handle_normal_flow() 완료
       └─ _record_voice_pipeline() 호출
            └─ opensearch_writer.py
                 └─ write_voice_pipeline_record_async()
                      └─ asyncio.create_task() → fire-and-forget
                           └─ OpenSearch voice_pipeline 인덱스 직접 기록
```

Fluent Bit를 거치지 않음 — 앱이 OpenSearch API를 직접 호출

### 기록 조건

| 조건 | 기록 여부 | 기록 내용 |
|------|----------|----------|
| 정상 흐름 (STT → Agent → TTS) 성공 | ✅ 기록 | stt_ms, agent_ms, tts_ms, intent, success=true |
| ASV 인증 흐름 — pass | ✅ 기록 | asv_result="pass", success=true |
| ASV 인증 흐름 — fail | ✅ 기록 | asv_result="fail", success=false |
| 파이프라인 도중 예외 발생 | ❌ 기록 안됨 | — |

ASV 인증 레코드에는 `stt_ms`, `agent_ms`, `tts_ms`, `total_ms` 필드가 없고 `asv_result` 필드만 있음

### 인덱스 매핑 (명시 선언된 필드)

| 필드 | 타입 | 설명 |
|------|------|------|
| `timestamp` | date | KST 기록 시각 |
| `request_id` | keyword | X-Request-ID (UUID) |
| `user_id` | keyword | JWT 사용자 ID |
| `stt_ms` | integer | Clova STT 소요 시간 (ms) |
| `agent_ms` | integer | LangGraph 에이전트 소요 시간 (ms) — LLM + tool + DB 포함 |
| `tts_ms` | integer | Azure TTS 소요 시간 (ms) |
| `total_ms` | integer | 파이프라인 전체 소요 시간 (ms) |
| `intent` | keyword | 감지된 인텐트 (transfer / balance / history 등, 미감지 시 "unknown") |
| `navigate_to` | keyword | 에이전트가 지정한 화면 이동 경로 |
| `success` | boolean | 정상 흐름 true / ASV 실패 false |
| `asv_result` | keyword | ASV 인증 결과 (pass / fail) — ASV 레코드 전용 |

`asv_result`가 없는 레코드 = 정상 파이프라인 완료 기록  
`asv_result`가 있는 레코드 = ASV 인증 이벤트 기록

### 저장 예시 레코드

```json
{
  "timestamp": "2026-06-07T14:30:05+09:00",
  "request_id": "a1b2-c3d4-...",
  "user_id": "user-uuid",
  "stt_ms": 320,
  "agent_ms": 1850,
  "tts_ms": 410,
  "total_ms": 2580,
  "intent": "transfer",
  "navigate_to": "transfer_confirm",
  "success": true,
  "error_code": null
}
```

### Grafana에서 활용하는 필드

| 패널 | 활용 필드 | 필터 |
|------|----------|------|
| STT/Agent/TTS 단계별 평균 레이턴시 | `stt_ms`, `agent_ms`, `tts_ms` | asv_result 없는 레코드 |
| 인텐트 분포 | `intent` | intent:transfer 등 |
| 에이전트 액션별 실행 횟수 | `intent` | intent:transfer 등 |
| ASV 인증 결과 | `asv_result` | asv_result:pass/fail |
| ASV 통과율 | `asv_result` | pass count / total count |

---

## 15. `transfer_audit` 인덱스 완전 정리

### 저장 경로

```
Python 앱 → ~/woori-logs/app.log (JSON lines)
                    ↓
              Fluent Bit tail (woori.app 태그)
                    ↓
              [FILTER] rewrite_tag
              event 값이 아래 패턴에 매칭되면 woori.audit 태그로 복사
              패턴: ^(transfer_executed|agent_auto_transfer_registered)$
              keep=true → app_logs에도 동일 레코드 유지
                    ↓
              [OUTPUT] woori.audit → OpenSearch transfer_audit 인덱스
```

### 기록되는 이벤트

| event 값 | 출처 | 기록 조건 |
|----------|------|----------|
| `transfer_executed` | transfer/service.py | 이체 완료(success) 시 |
| `agent_auto_transfer_registered` | graph.py | 자동이체 등록 성공 시 |
| `agent_auto_transfer_registered` | execute_auto_transfer.py | 동일 등록 건에 대해 중복 기록 ⚠️ |

> ⚠️ `agent_auto_transfer_registered`는 graph.py와 execute_auto_transfer.py가 동일 이벤트를 각각 로그로 남겨 **자동이체 1건당 transfer_audit에 2개 레코드**가 생성됨

### 인덱스 매핑 (명시 선언된 필드)

| 필드 | 타입 | 설명 |
|------|------|------|
| `timestamp` | date | KST 로그 시각 |
| `request_id` | keyword | X-Request-ID (UUID) |
| `user_id` | keyword | JWT 사용자 ID |
| `tx_id` | keyword | 거래 ID (transfer_executed 전용) |
| `amount` | integer | 이체 금액 (원) |
| `to_bank` | keyword | 수취 은행명 |
| `to_account_masked` | keyword | 마스킹된 수취 계좌번호 |
| `status` | keyword | completed / failed |
| `duration_ms` | integer | 이체 처리 소요 시간 (ms) |

`agent_auto_transfer_registered` 이벤트는 `order_id`, `recipient` 등 다른 필드 구성 → dynamic mapping 자동 생성

### 이벤트별 실제 필드 비교

| 필드 | `transfer_executed` | `agent_auto_transfer_registered` (graph.py) |
|------|--------------------|--------------------------------------------|
| `tx_id` | ✅ | ❌ |
| `order_id` | ❌ | ✅ |
| `amount` | ✅ | ✅ |
| `to_bank` | ✅ | ✅ (`bank_name` 슬롯) |
| `to_account_masked` | ✅ | ❌ |
| `recipient` | ❌ | ✅ |
| `status` | ✅ (completed) | ❌ |
| `duration_ms` | ✅ | ❌ |

### Grafana에서 활용하는 필드

| 패널 | 활용 필드 |
|------|----------|
| 시간대별 이체 건수 | `timestamp` (date histogram) |
| 최근 이체 감사 로그 | 전체 필드 (table 뷰) |
