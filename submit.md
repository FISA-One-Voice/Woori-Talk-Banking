# [우리FISA 6기] AI 엔지니어링 과정 2팀 <img src="Asset-image/안내견_테두리_색변경.png" height="80" alt="우리톡뱅킹안내견" style="vertical-align: middle; margin-left: 12px;" />

## 1. 프로젝트 개요

### 주제 
- 시각장애인을 위한 음성 AI 멀티 에이전트 기반 뱅킹 앱

### 프로젝트 기획 배경
- 시각장애인은 기존 모바일 뱅킹 앱의 복잡한 화면 구성, 작은 버튼, 보안매체 사용 등으로 인해 송금이나 계좌 조회 같은 기본적인 금융 거래조차 큰 불편을 겪는다. 스크린리더만으로는 여러 단계로 이어지는 이체 흐름을 온전히 따라가기 어렵고, 특히 본인인증 단계에서는 타인의 도움이 필요한 경우가 잦아 금융 자립성과 보안이 동시에 제약된다. 본 프로젝트는 이러한 문제를 해결하기 위해, 음성만으로 뱅킹 앱의 핵심 기능을 수행할 수 있는 배리어프리 뱅킹 서비스를 구축하였다.

### 기술 스택

**앱 · AI · 백엔드**

![React Native](https://img.shields.io/badge/React_Native-20232A?style=flat-square&logo=react&logoColor=61DAFB) ![Expo](https://img.shields.io/badge/Expo-000020?style=flat-square&logo=expo&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat-square&logo=postgresql&logoColor=white) ![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white) ![OpenSearch](https://img.shields.io/badge/OpenSearch-005EB8?style=flat-square&logo=opensearch&logoColor=white)

**인프라 · 운영**

![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![AWS](https://img.shields.io/badge/☁️%20AWS-%23FF9900.svg?style=flat-square&logo=amazon-aws&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white) ![Grafana](https://img.shields.io/badge/Grafana-F46800?style=flat-square&logo=grafana&logoColor=white) ![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat-square&logo=prometheus&logoColor=white) ![Fluent Bit](https://img.shields.io/badge/Fluent_Bit-49BDA5?style=flat-square&logo=fluentbit&logoColor=white)

**기획 · 디자인**

![Figma](https://img.shields.io/badge/Figma-F24E1E?style=flat-square&logo=figma&logoColor=white) ![Mermaid](https://img.shields.io/badge/Mermaid-FF3670?style=flat-square&logo=mermaid&logoColor=white)

---
## 2. 아키텍처

### 2-1-1. 서비스 아키텍처

![서비스 아키텍처](Asset-image/시스템아키텍처.png)
**서비스 흐름**  
사용자의 음성 입력은 앱에서 백엔드로 전달되고, 백엔드는 STT → LangGraph 멀티 에이전트 → TTS 순서로 요청을 처리합니다. 이체처럼 보안이 필요한 기능은 ASV 화자 인증 단계를 거친 뒤 실행되며, 자산 조회·금융 상담·이벤트 조회는 각 도메인 에이전트와 전용 데이터 저장소를 통해 분기 처리됩니다.

**데이터 및 보안**  
PostgreSQL은 계좌·거래 데이터를 저장하고, Redis는 LangGraph 멀티턴 세션 상태를 공유하며, S3는 이체 동의 음성을 보관합니다. OpenSearch는 금융 문서 검색과 로그 분석에 활용하고, 송금 등 민감 기능 수행 시 ASV(화자인증)를 통해 본인 확인을 수행합니다.

**모니터링 및 운영**  
OpenSearch, Postgre, Prometheus, Grafana, Fluent Bit 을 활용한 모니터링 및 로그 관리 환경을 통해 시스템의 안정적인 운영을 지원합니다.

### 2-1-2. AWS 아키텍처

![AWS 아키텍처](Asset-image/AWS%20아키텍처.jpeg)

**인프라 배치**  
백엔드 서버와 모니터링 서버를 별도 EC2로 분리해 운영합니다. 백엔드 EC2는 FastAPI 애플리케이션과 Redis 등 서비스 실행에 필요한 컴포넌트를 담당하고, 모니터링 EC2는 Prometheus와 Grafana를 통해 운영 지표를 수집·시각화합니다.

**CI/CD 및 배포**  
GitHub Actions 기반 CI/CD 파이프라인을 통해 백엔드 Docker 이미지를 빌드하고 EC2에 배포합니다. 배포 스크립트는 최신 이미지를 내려받은 뒤 필요한 컨테이너를 재기동해 코드 변경 사항을 서비스에 반영합니다.


### 2-2. AI 에이전트 워크플로우

![AI에이전트워크플로우](Asset-image/AI에이전트워크플로우.png)

**설명**

**음성 AI 파이프라인**  
Clova STT·GPT·Azure TTS와 연동하여 음성 입력, AI 처리, 음성 응답까지의 흐름을 구성합니다. LangGraph Supervisor가 transfer·asset·RAG 하위 에이전트로 업무를 분기하는 멀티 에이전트 구조를 적용하였습니다.

---
## 3. 주요 기능 소개

### 3-1-1. 핵심 기술 구성

![핵심기술구성](Asset-image/핵심기술구성.png)

### 3-1-2. 모니터링

<table>
  <tr>
    <td align="center"><img src="Asset-image/음성파이프라인대시보드.png" width="330"/></td>
    <td align="center"><img src="Asset-image/에러분석대시보드.png" width="330"/></td>
    <td align="center"><img src="Asset-image/ASV화자인증대시보드.png" width="330"/></td>
  </tr>
  <tr>
    <td align="center">음성 파이프라인 대시보드</td>
    <td align="center">에러 분석 대시보드</td>
    <td align="center">ASV 화자인증 대시보드</td>
  </tr>
</table>




### 3-2. 통합 워크플로우 다이어그램

![통합워크플로우](Asset-image/통합워크플로우.png)

### 3-3. 세부 기능 소개

---

#### [기능 1] LangGraph Supervisor 우선순위 기반 도메인 라우팅

- **파일:** [backend/app/shared/agent/supervisor.py](https://github.com/FISA-One-Voice/Woori-Talk-Banking/blob/main/backend/app/shared/agent/supervisor.py)
- **설명:** 단순 LLM 분류가 아니라 키워드 패스트패스 → 세션 유지 → 도메인 전환 감지 → LLM 폴백 순의 6단계 우선순위 체계로 응답 속도와 정확도를 동시에 확보. gpt-4.1-nano는 최후 수단으로만 호출

**핵심 코드**

```python
async def _decide_domain(text: str, state: VoiceState) -> str:
    if _is_navigation_utterance(text):
        return "cancel"                              # 1순위: 홈 이동 키워드 (세션 무관)
    if _is_cancel_utterance(text) and _has_active_session(state):
        return "cancel"                              # 2순위: 취소 + 활성 세션
    if _has_active_session(state):
        return "transfer"                            # 3순위: 이체 세션 유지
    if state.get("agent_domain") == "asset" and not _is_domain_switch_utterance(text):
        return "asset"                               # 4순위: asset 연속 세션 유지
    if is_plain_transfer_start(text):
        return "transfer"                            # 5순위: 이체 키워드 패스트패스
    if "이벤트" in _normalize(text):
        return "event"                               # 5순위: 이벤트 키워드
    return await _llm_classify_domain(text)          # 6순위: gpt-4.1-nano LLM 폴백
```

---

#### [기능 2] 에이전트별 상태 변경 계약 검증

- **파일:** [backend/app/shared/agent/subgraphs/transfer.py](https://github.com/FISA-One-Voice/Woori-Talk-Banking/blob/main/backend/app/shared/agent/subgraphs/transfer.py)
- **설명:** 멀티 에이전트 구조에서는 각 에이전트가 자기 책임 범위의 상태만 수정해야 한다. TransferAgent가 반환할 수 있는 상태 필드를 제한하고, 허용되지 않은 필드나 화면 이동 값이 나오면 즉시 `AGENT_CONTRACT_VIOLATION`으로 차단한다. 이를 통해 서브그래프가 소유권 밖 필드를 오염시키지 못하도록 방어했다

**핵심 코드**

```python
TRANSFER_WRITE: frozenset[str] = frozenset(
    {
        "messages",
        "navigate_to",
        "pending_action",
        "collected_slots",
        "awaiting_confirmation",
        "awaiting_asv_audio",
        "execution_ready",
        "recipient_validated",
        "asv_retry_count",
        "awaiting_memo_decision",
        "last_tx_id",
        "tool_execution_ms",
    }
)

def validate_transfer_delta(delta: dict) -> dict:
    invalid_fields = set(delta) - TRANSFER_WRITE
    if invalid_fields:
        raise AgentError(
            code="AGENT_CONTRACT_VIOLATION",
            message="TransferAgent가 허용되지 않은 상태 필드를 반환했습니다.",
            status_code=500,
            user_message="이체 처리 중 일시적인 오류가 발생했습니다.",
        )

    if "navigate_to" in delta and delta["navigate_to"] not in TRANSFER_NAVIGATE_VALUES:
        raise AgentError(code="AGENT_CONTRACT_VIOLATION", ...)
    return delta
```

---

#### [기능 3] ASV 이후 이체 실행·동의 음성 업로드 2단계 처리

- **파일:** [backend/app/shared/voice/service.py](https://github.com/FISA-One-Voice/Woori-Talk-Banking/blob/main/backend/app/shared/voice/service.py)
- **설명:** ASV 인증 성공 직후 DB 커밋과 S3 업로드를 한 번에 처리하지 않고, 먼저 `execution_ready=True` 상태와 `execution_pending=True` 응답을 반환해 사용자에게 "처리 중" TTS를 들려준다. 이후 프론트가 `/api/voice/proceed`를 호출하면 2차 단계에서 실제 이체를 실행해 DB에 커밋하고, 이체 확인 TTS와 사용자 동의 음성을 합쳐 S3에 백그라운드로 업로드한다

**핵심 코드**

```python
async def _return_processing_tts(config: dict, graph) -> VoiceResponseData:
    await graph.aupdate_state(
        config,
        {
            "awaiting_asv_audio": False,
            "execution_ready": True,
            "asv_retry_count": 0,
            "agent_domain": "transfer",
        },
        as_node="supervisor_node",
    )
    return VoiceResponseData(
        awaiting_asv_audio=False,
        execution_pending=True,  # 프론트가 TTS 재생 후 /api/voice/proceed 호출
    )

async def _execute_pending_transfer(user_id: str, config: dict, graph) -> VoiceResponseData:
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="인증 완료")], "user_id": user_id},
        config=config,
    )  # execute_node 진입 → 이체 실행 및 DB 커밋

    tx_id = result.get("last_tx_id") or result.get("last_order_id")
    if pending_tts_text and pending_audio_b64 and tx_id:
        audio_mp3, consent_tts_mp3 = await asyncio.gather(
            synthesize_speech(response_text),
            synthesize_speech(pending_tts_text),
        )
        task = asyncio.create_task(
            _upload_consent_task(user_id, tx_id, consent_tts_mp3, pending_audio_b64)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
```

---

#### [기능 4] TransferAgent 조건부 라우팅 상태 머신

- **파일:** [backend/app/shared/agent/subgraphs/transfer.py](https://github.com/FISA-One-Voice/Woori-Talk-Banking/blob/main/backend/app/shared/agent/subgraphs/transfer.py)
- **설명:** 이체·자동이체는 수취인, 금액, 주기, 확인, ASV 인증 등 단계가 많아 단순 LLM 응답만으로 제어하기 어렵다. TransferAgent는 현재 상태를 기준으로 `resolve_node`, `slot_fill_node`, `confirm_node`, `execute_node` 중 다음 노드를 결정해 멀티턴 음성 이체 흐름을 안정적으로 제어한다

**핵심 코드**

```python
def route_after_intent(state: VoiceState) -> str:
    if state.get("awaiting_asv_audio"):
        return END
    if state.get("execution_ready"):
        return "execute_node"

    pending = state.get("pending_action")
    if not pending:
        return END

    slots = state.get("collected_slots", {})
    if (
        pending in RECIPIENT_REQUIRED_ACTIONS
        and slots.get("recipient")
        and not state.get("recipient_validated")
    ):
        return "resolve_node"

    missing = missing_slots(pending, slots)
    if missing:
        return "slot_fill_node"
    if pending not in SLOT_SCHEMA:
        return "execute_node"
    if not state.get("awaiting_confirmation"):
        return "confirm_node"

    return END
```

---

#### [기능 5] Redis Checkpointer 기반 LangGraph 세션 공유

- **파일:** [backend/app/main.py](https://github.com/FISA-One-Voice/Woori-Talk-Banking/blob/main/backend/app/main.py), [backend/app/shared/agent/supervisor.py](https://github.com/FISA-One-Voice/Woori-Talk-Banking/blob/main/backend/app/shared/agent/supervisor.py)
- **설명:** 단일 프로세스에서는 `MemorySaver`로도 멀티턴 상태 유지가 가능하지만, 배포 환경에서 백엔드 워커가 여러 개로 늘어나면 사용자 세션이 워커마다 분리될 수 있다. `REDIS_URL`이 설정된 경우 `AsyncRedisSaver`를 Supervisor 그래프에 주입해 `thread_id=user_id` 기반 대화 상태를 Redis에 공유하고, 미설정 시에는 기존 `MemorySaver`로 폴백한다

**핵심 코드**

```python
@app.on_event("startup")
async def startup_redis_graph():
    global _redis_saver_cm
    if not _settings.REDIS_URL:
        logger.info("[Startup] REDIS_URL 미설정 — MemorySaver 폴백")
        return

    from langgraph.checkpoint.redis.aio import AsyncRedisSaver
    from app.shared.voice.service import initialize_graph

    _redis_saver_cm = AsyncRedisSaver.from_conn_string(
        _settings.REDIS_URL,
        ttl={"default_ttl": 600},
    )
    checkpointer = await _redis_saver_cm.__aenter__()
    await checkpointer.setup()
    initialize_graph(checkpointer)

def build_supervisor(checkpointer=None):
    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
```
