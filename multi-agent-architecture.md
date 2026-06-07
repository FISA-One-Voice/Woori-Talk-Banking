# 멀티에이전트 아키텍처 설계

> 작성일: 2026-06-04  
> 참조 계획: `docs/01-plan/multiagent-upgrade-plan.md`  
> 리뷰 이력: Round 1 (2026-06-04) · Round 2 (2026-06-04) · Round 3 (2026-06-04) · Round 6 (2026-06-05)

---

## 0. 4인 개발 범위 분담

> 이 섹션이 팀 전체의 계약서다. 구현 시작 전에 모든 담당자가 숙지해야 한다.

### 담당자 배정

| 담당자 | 담당 컴포넌트 | 주요 파일 |
|--------|-------------|-----------|
| **Dev-A** | SupervisorAgent + 공유 인프라 | `supervisor.py`, `state.py`, `slot_schema.py`, `tools/__init__.py`, `ROUTING_CONSTANTS.py` |
| **Dev-B** | TransferAgent | `subgraphs/transfer.py`, `tools/transfer.py`, `tools/auto_transfer.py`, `tools/cancel_auto_transfer.py`, `tools/lookup_recipient.py` |
| **Dev-C** | AssetAgent + analytics API | `subgraphs/asset.py`, `tools/spending_analysis.py`, `features/analytics/` |
| **Dev-D** | RAGAgent + 외부 데이터 툴 | `subgraphs/consultation.py`, `tools/financial_qa.py`, `tools/market_info.py` |

### 입력/출력 계약 요약

각 담당자가 **받는 것(입력)**과 **반환하는 것(출력)**을 명확히 정의한다.

#### Dev-A (Supervisor)
- **입력**: `VoiceState` 전체 (HTTP 레이어에서 주입)
- **출력**: 어느 하위 에이전트로 라우팅할지 결정 + navigation 시 `{navigate_to, agent_domain}` delta
- **절대 하지 않는 것**: `pending_action`, `collected_slots`, `awaiting_*` 등 하위 에이전트 소유 필드 수정

#### Dev-B (TransferAgent)
- **입력**: `VoiceState` 전체
- **출력 필드**: `messages`, `navigate_to`, `pending_action`, `collected_slots`, `awaiting_confirmation`, `awaiting_asv_audio`, `execution_ready`, `recipient_validated`, `asv_retry_count`, `awaiting_memo_decision`, `awaiting_transfer_clarification`, `draft_recipient`, `last_tx_id`, `last_order_id`
- **반환 형식**: 변경된 필드만 포함하는 dict (delta 패턴)
- **절대 하지 않는 것**: `agent_domain`, `analytics_period` 수정

#### Dev-C (AssetAgent)
- **입력**: `messages`, `user_id`, `analytics_period`, `agent_domain`
- **출력 필드**: `messages`, `navigate_to`, `analytics_period`
- **반환 형식**: 변경된 필드만 포함하는 dict (delta 패턴)
- **절대 하지 않는 것**: `pending_action`, `awaiting_*`, `collected_slots` 수정

#### Dev-D (RAGAgent)
- **입력**: `messages`, `user_id`
- **출력 필드**: `messages`, `navigate_to` (항상 `None`)
- **반환 형식**: `{"messages": [...], "navigate_to": None}`
- **절대 하지 않는 것**: `navigate_to`에 None 이외의 값 설정, 다른 모든 필드 수정

### 개발 의존성 그래프

```
Dev-A (Supervisor)
    ├── ROUTING_CONSTANTS.py 작성 후 → Dev-B, Dev-C, Dev-D에 공유 (블로커)
    ├── state.py 신규 필드 추가 → 전원 공유
    └── supervisor.py 완성 → 통합 테스트 가능

Dev-B (TransferAgent)   : ROUTING_CONSTANTS.py 수령 후 독립 개발 가능
Dev-C (AssetAgent)      : ROUTING_CONSTANTS.py 수령 후 독립 개발 가능
Dev-D (RAGAgent)        : ROUTING_CONSTANTS.py 수령 후 독립 개발 가능

통합 테스트             : Dev-A supervisor.py + Dev-B, C, D 서브그래프 모두 필요
```

---

### Dev-A 첫 커밋 명세 (팀 착수 전 선행 필수)

> Dev-B/C/D는 아래 파일들이 `develop` 브랜치에 머지된 후 자기 브랜치를 생성한다.

#### 커밋에 포함할 파일 4개

**① `backend/app/shared/agent/ROUTING_CONSTANTS.py` (신규)**

Supervisor가 Sub-agent 내부 로직을 알 필요는 없다. 이 파일에는 **에이전트 간 계약**만 둔다. 각 에이전트의 domain action 집합(TRANSFER_DOMAIN_ACTIONS 등)은 해당 Sub-agent 파일 내부에서 정의한다.

```python
"""멀티에이전트 라우팅 계약 상수. Dev-A 정의, 나머지 3명은 import 전용.

포함하는 것  : 에이전트 간 읽기/쓰기 경계, navigate_to 허용값
포함 안 하는 것: 각 에이전트의 domain action 집합 — 해당 subgraph 파일 내부에 정의
"""

# ── 1. 각 에이전트의 읽기 계약 ────────────────────────────────────────────────
# 에이전트는 이 집합 밖의 필드를 읽으면 안 된다.
# 단독 테스트 시 최소 mock state 구성 기준으로 사용한다.

TRANSFER_READ: frozenset[str] = frozenset({
    "messages", "user_id",
    "pending_action", "collected_slots",
    "awaiting_confirmation", "awaiting_asv_audio",
    "execution_ready", "recipient_validated", "asv_retry_count",
    "awaiting_memo_decision", "awaiting_transfer_clarification",
    "draft_recipient", "last_tx_id", "last_order_id",
})

ASSET_READ: frozenset[str] = frozenset({
    "messages", "user_id", "analytics_period", "agent_domain",
})

RAG_READ: frozenset[str] = frozenset({
    "messages", "user_id",
})

# ── 2. 각 에이전트가 설정 가능한 navigate_to 값 ──────────────────────────────
# 이 목록 밖의 값을 반환하면 계약 위반 — 코드 리뷰 시 거부 사유가 된다.

SUPERVISOR_NAVIGATE_VALUES: frozenset[str | None] = frozenset({"home", None})

TRANSFER_NAVIGATE_VALUES: frozenset[str | None] = frozenset({
    "transfer", "transfer/complete",
    "auto-transfer", "auto-transfer/complete",
    "home", None,
})

ASSET_NAVIGATE_VALUES: frozenset[str | None] = frozenset({
    "balance", "report", None,
})

RAG_NAVIGATE_VALUES: frozenset[str | None] = frozenset({None})
```

**② `backend/app/shared/agent/state.py` — 필드 2개 추가**

기존 `VoiceState` TypedDict 하단에 아래 두 줄만 추가한다:

```python
agent_domain: str | None      # Supervisor가 기록 ("transfer"|"asset"|"rag"|"navigate")
analytics_period: str | None  # AssetAgent용 ("이번달"|"지난달"|"3개월")
```

**③ `backend/app/shared/agent/tools/__init__.py` — 섹션 주석 4개 삽입**

각 담당자가 자기 구역에만 import를 추가하도록 미리 섹션을 분리한다:

```python
# ── Dev-B (TransferAgent tools) ──────────────────────────────────────────────
from app.shared.agent.tools.transfer import ...        # 기존 유지

# ── Dev-C (AssetAgent tools) ─────────────────────────────────────────────────
# Dev-C: 이 구역에만 추가
# from app.shared.agent.tools.spending_analysis import get_monthly_spending_report

# ── Dev-D (RAGAgent tools) ───────────────────────────────────────────────────
# Dev-D: 이 구역에만 추가
# from app.shared.agent.tools.financial_qa import search_financial_docs
# from app.shared.agent.tools.market_info import get_exchange_rate, get_base_rate
```

**④ `backend/app/shared/agent/subgraphs/__init__.py` — 빈 파일 생성**

패키지 인식에 필요한 빈 파일.

#### 각 담당자의 ROUTING_CONSTANTS.py import 방법

```python
# Dev-B (subgraphs/transfer.py) — 계약 준수 확인용
from app.shared.agent.ROUTING_CONSTANTS import TRANSFER_READ, TRANSFER_NAVIGATE_VALUES

# Dev-C (subgraphs/asset.py)
from app.shared.agent.ROUTING_CONSTANTS import ASSET_READ, ASSET_NAVIGATE_VALUES

# Dev-D (subgraphs/consultation.py)
from app.shared.agent.ROUTING_CONSTANTS import RAG_READ, RAG_NAVIGATE_VALUES

# Dev-A (supervisor.py) — Supervisor는 domain action 목록을 import하지 않는다
# Supervisor는 state 플래그로만 라우팅하므로 불필요
```

#### 각 Sub-agent가 자기 파일 내부에 정의하는 domain action 집합

```python
# subgraphs/transfer.py (Dev-B 내부)
TRANSFER_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "transfer", "auto_transfer", "cancel_auto_transfer",
    "add_note", "add_auto_transfer_note",
})

# subgraphs/asset.py (Dev-C 내부)
ASSET_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "balance", "history", "spending_analysis", "monthly_report",
})

# subgraphs/consultation.py (Dev-D 내부)
RAG_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "financial_qa", "exchange_rate", "interest_rate", "event",
})
```

이 상수들은 Supervisor에서 import하지 않는다. Sub-agent 내부에서 intent 검증용으로만 쓴다.

#### 첫 커밋 완료 체크리스트

| # | 확인 항목 | 확인 명령 |
|---|---------|---------|
| 1 | `ROUTING_CONSTANTS.py` 커밋됨 | `git show HEAD -- ROUTING_CONSTANTS.py` |
| 2 | `state.py`에 신규 필드 2개 추가됨 | `grep -n "agent_domain" state.py` |
| 3 | `tools/__init__.py`에 섹션 주석 추가됨 | `grep -n "Dev-" tools/__init__.py` |
| 4 | `subgraphs/__init__.py` 빈 파일 생성됨 | `ls subgraphs/` |
| 5 | import 오류 없음 | `cd backend && .venv/bin/python -c "from app.shared.agent.ROUTING_CONSTANTS import TRANSFER_READ; print('OK')"` |

이 커밋이 `develop`에 머지된 후 Dev-B/C/D가 각자 브랜치를 생성한다.

---

### graph.py 이전 브랜치 전략

`graph.py`는 Dev-A(supervisor 연결)와 Dev-B(노드 추출)가 동시에 수정하는 충돌 지점이다. 아래 순서를 반드시 지킨다.

```
1. Dev-B: feature/transfer-subgraph 브랜치 생성
          graph.py 노드 → subgraphs/transfer.py 이동
          graph.py의 build_graph()는 아직 그대로 유지
          PR → develop 머지 (리뷰어: Dev-A)

2. Dev-A: feature/supervisor 브랜치 생성 (Dev-B PR 머지 후 base 갱신)
          graph.py의 build_graph() → build_supervisor() 교체
          supervisor.py 작성
          PR → develop 머지
```

Dev-A가 Dev-B보다 먼저 graph.py를 수정하면 Dev-B가 이전 기준 노드를 추출하므로 충돌이 발생한다.

### tools/__init__.py 동시 편집 규칙

Dev-C와 Dev-D는 `tools/__init__.py`의 같은 파일을 동시에 수정한다. git 충돌을 방지하기 위해 **파일 내 담당 구역을 사전 분리**한다.

```python
# tools/__init__.py 구역 분리 (Dev-A가 초안에서 미리 섹션 주석 추가)

# ── Dev-B (TransferAgent tools) ───────────────────────────────────────────────
from app.shared.agent.tools.transfer import ...

# ── Dev-C (AssetAgent tools) ──────────────────────────────────────────────────
# Dev-C: 아래 구역에만 추가
# from app.shared.agent.tools.spending_analysis import ...

# ── Dev-D (RAGAgent tools) ────────────────────────────────────────────────────
# Dev-D: 아래 구역에만 추가
# from app.shared.agent.tools.financial_qa import ...
# from app.shared.agent.tools.market_info import ...
```

각 담당자는 자신의 구역 밖은 건드리지 않는다.

---

## 목표 아키텍처

```
POST /api/voice/voice
        │
        ▼
[SupervisorAgent]  — 도메인 분류 + 취소 처리 + navigation 직접 처리
        │
   ┌────┼──────────────┬────────────┐
   ▼    ▼              ▼            ▼
[cancel [Transfer  [Asset     [RAG
 _node]  Agent]     Agent]     Agent]
 취소+   이체/      잔액/      금융FAQ/
 홈이동  자동이체/  내역/      환율/금리/
        ASV       지출분석    이벤트(TTS)
```

`shared/voice/service.py`와 `shared/voice/router.py`는 **변경 없음**.
`_get_graph()`의 반환값을 supervisor graph로 교체하는 것만으로 연결된다.

### 전체 호출 흐름 (발화 1건 기준)

```
사용자 음성
    │
    ▼ STT (Clova) → HumanMessage 생성
[voice/service.py] ── graph.ainvoke(state, config) ──▶ [Supervisor 노드]
                                                              │
                                                    ┌─────── state 플래그 확인 ────────────────────────┐
                                                    │         (LLM 없음 — 패스트패스)                  │
                                          [최우선] 취소 발화                              agent_domain=="asset"
                                          + active_session?                               (5자 이상, 도메인 전환 없음)
                                          pending_action is not None                                   │
                                          awaiting_asv_audio=True                                      │
                                          awaiting_confirmation=True                                   │
                                          awaiting_memo_decision=True                                  │
                                          execution_ready=True                                         │
                                                    │                                                  │
                                                    ▼                                                  │
                                         조건 없으면 LLM 분류                                          │
                                         gpt-4o-mini                                                  │
                                         → "transfer"|"asset"|"rag"|"navigate"                        │
                                                    │                                                  │
                         ┌──────────────────────────┼──────────────────┬──────────┐                  │
                         ▼                          ▼                  ▼          ▼                   ▼
                  [cancel_node]            [TransferAgent]       [AssetAgent] [RAGAgent]        END (navigate)
                  (Supervisor 내부)        (subgraphs/           (subgraphs/  (subgraphs/       navigate_to 설정 후 종료
                  상태 전체 초기화          transfer.py)           asset.py)    consultation.py)
                  navigate_to="home"              │                  │              │
                         │                   delta dict         delta dict      delta dict
                         ▼                    반환               반환            반환
                        END                       └──────────────────┴──────────────┘
                                                    │
                                                    ▼
                                         [voice/service.py]
                                         tts_text_from_messages()
                                                    │
                                                    ▼
                                          Azure TTS → 음성 응답
```

**Sub-agent 도메인 지식 경계**:

- Supervisor는 state 플래그(awaiting_*, pending_action is not None, agent_domain)로 라우팅하고, 새 발화는 LLM 도메인 분류로 처리한다. Sub-agent의 구체적인 intent 목록(TRANSFER_DOMAIN_ACTIONS 등)을 Supervisor가 알 필요는 없다.
- 각 domain action 집합은 **해당 Sub-agent 파일 내부에서만 정의하고 사용**한다.

---

## 1. SupervisorAgent (Dev-A 담당)

### 역할
- 인텐트 도메인 분류 → 하위 에이전트 라우팅
- `home` 등 순수 navigation 인텐트 직접 처리
- LLM 호출 최소화: 상태 기반 패스트패스 우선

### 파일
`backend/app/shared/agent/supervisor.py`

### Supervisor 쓰기 허용 필드
Supervisor는 아래 규칙으로만 state를 수정한다.

| 상황 | 쓰는 필드 |
|------|---------|
| 모든 라우팅 결정 | `agent_domain` |
| domain == "navigate" | `agent_domain`, `navigate_to` |
| **cancel_node 실행 (예외)** | **TransferAgent 소유 필드 전체 + `navigate_to`** |

> **cancel_node 예외 이유**: 취소는 모든 sub-agent를 초월하는 전역 관심사다. Sub-agent마다 취소 로직을 두면 AssetAgent·RAGAgent도 세션 상태가 없는데 취소 로직을 가져야 하는 구조적 중복이 발생한다. cancel_node는 Supervisor 그래프 내부 노드로서 P4의 유일한 예외이며, TransferAgent 소유 필드를 전부 초기화할 수 있다.

### Supervisor 노드 구조

Supervisor는 **노드 함수**로 구현한다. 조건부 엣지 함수(`route()`)와 분리하여, 노드가 state delta를 반환하고 엣지가 다음 목적지를 결정한다.

```python
# supervisor.py — 노드 함수 (state 변경 허용)
async def supervisor_node(state: VoiceState) -> dict:
    """도메인 분류 후 agent_domain 기록. navigate이면 navigate_to도 설정."""
    domain = await _decide_domain(state)

    if domain == "navigate":
        target = _resolve_navigate_target(last_user_text(state["messages"]))
        return {"agent_domain": "navigate", "navigate_to": target}

    return {"agent_domain": domain}   # "transfer"|"asset"|"rag"|"cancel"


# supervisor.py — cancel_node (Supervisor 그래프 내부 노드)
def cancel_node(state: VoiceState) -> dict:
    """취소 발화 수신 시 모든 세션 상태를 초기화하고 홈으로 이동한다.
    P4 예외: TransferAgent 소유 필드를 직접 초기화한다.
    """
    return {
        "messages": [
            *clear_conversation_messages(),
            AIMessage(content="취소되었습니다. 홈 화면으로 이동합니다."),
        ],
        "navigate_to": "home",
        "agent_domain": None,
        "pending_action": None,
        "collected_slots": {},
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "asv_retry_count": 0,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "execution_ready": False,
        "recipient_validated": False,
        "last_tx_id": None,
        "last_order_id": None,
    }


# supervisor.py — 조건부 엣지 함수 (state 변경 불가, 문자열만 반환)
def route_after_supervisor(state: VoiceState) -> str:
    """supervisor_node 이후 어느 노드/서브그래프로 이동할지 결정."""
    domain = state["agent_domain"]
    if domain == "navigate":
        return END
    if domain == "cancel":
        return "cancel_node"
    return domain   # "transfer" | "asset" | "rag"
```

### 도메인 결정 로직 `_decide_domain`

```python
async def _decide_domain(state: VoiceState) -> str:
    """도메인 결정. LLM을 호출하는 경우 async 필수."""
    # ── 패스트패스 (LLM 없음) ──────────────────────────────────────────
    pending = state.get("pending_action")
    user_text = last_user_text(state.get("messages", []))

    # 0. [최우선] 취소 인터셉터
    #    취소는 어느 sub-agent 담당인지와 무관한 전역 관심사다.
    #    active_session 여부와 관계없이 취소 발화는 Supervisor cancel_node가 처리한다.
    #    cancel_node가 모든 세션 상태를 초기화하므로 MemorySaver 잔류 문제가 없다.
    active_session = (
        state.get("awaiting_asv_audio") or
        state.get("awaiting_confirmation") or
        state.get("awaiting_memo_decision") or
        state.get("awaiting_transfer_clarification") or
        state.get("execution_ready") or
        pending is not None
    )
    if _is_cancel_utterance(user_text) and active_session:
        return "cancel"         # cancel_node가 상태 초기화 + navigate_to="home" 처리

    # 0-b. 세션 없는 상태에서 순수 navigation 발화
    if _is_navigation_utterance(user_text) and not active_session:
        return "navigate"

    # 1. 진행 중인 이체 세션 — TransferAgent 유지
    if active_transfer:
        return "transfer"

    # 2. 이전 턴에서 asset 도메인이었고 새 인텐트 신호 없음 → 유지
    #    단, 5글자 미만 단문("네", "응", "맞아")은 패스트패스 제외 — LLM 분류로 넘김
    #    (컨텍스트 없는 단문을 asset으로 오발동 방지)
    if state.get("agent_domain") == "asset" and len(user_text) >= 5:
        if not _is_domain_switch_utterance(user_text):
            return "asset"

    # 3. transfer 키워드 패스트패스
    if is_plain_transfer_start(user_text) or is_recipient_only_utterance(user_text):
        return "transfer"

    # ── LLM 분류 (ambiguous 케이스만) ─────────────────────────────────
    return await _llm_classify_domain(user_text)   # "transfer"|"asset"|"rag"|"navigate"
```

> **supervisor_node는 `async def`로 선언한다**: `_decide_domain`이 LLM을 호출하므로 코루틴이다. `supervisor_node`도 `async def`로 선언하고 `await _decide_domain(state)`를 호출해야 한다.

### 미정의 헬퍼 함수 명세 (Dev-A 구현 책임)

아래 헬퍼 함수들은 `supervisor.py` 내부에서 Dev-A가 구현한다.

```python
# 취소 키워드 — 세션 진행 중에만 cancel_node로 분기
CANCEL_KEYWORDS: frozenset[str] = frozenset({
    "취소", "그만", "그만해", "중단", "안 할래", "취소해줘", "됐어", "하지 마",
})

# 순수 navigation 키워드 — 세션 없는 상태에서만 navigate로 분기
NAVIGATION_KEYWORDS: frozenset[str] = frozenset({
    "홈으로", "처음으로", "돌아가", "홈 화면",
})

def _is_cancel_utterance(text: str) -> bool:
    """취소 의도 발화인지 판별한다. active_session과 AND 조건으로 사용한다."""
    return any(kw in text for kw in CANCEL_KEYWORDS)

def _is_navigation_utterance(text: str) -> bool:
    """순수 화면 이동 발화인지 판별한다. not active_session과 AND 조건으로 사용한다."""
    return any(kw in text for kw in NAVIGATION_KEYWORDS)

def _is_domain_switch_utterance(text: str) -> bool:
    """asset 도메인 진행 중 다른 도메인으로 전환하는 발화."""
    return is_plain_transfer_start(text) or _is_cancel_utterance(text)

def _resolve_navigate_target(text: str) -> str:
    """navigate 도메인 발화에서 Expo Router 경로명을 결정한다."""
    # 현재 Supervisor가 직접 처리하는 navigate는 "home"뿐
    return "home"
```

> **취소 vs navigation 분리**: "취소"는 active_session과 AND 조건이고, "홈으로"는 not active_session과 AND 조건이다. 두 키워드가 겹치지 않도록 집합을 분리한다. 만약 세션 없이 "취소"를 말하면 두 조건 모두 false → LLM 분류로 넘어가 "navigate"로 처리된다.

> **navigate 제한**: Supervisor가 직접 처리하는 navigation은 `"home"` 경로만이다. 다른 화면(`transfer`, `balance`, `report`)은 해당 에이전트가 설정한다. Supervisor에서 "이체 화면으로 가줘"를 직접 처리하지 않는다 — transfer 도메인으로 라우팅하면 TransferAgent가 `navigate_to="transfer"`를 설정한다.

### 도메인 분류 LLM 프롬프트

```
다음 발화가 어느 도메인에 해당하는지 한 단어로 답하시오.
- transfer: 이체, 송금, 자동이체, 수취인, 계좌 이동
- asset: 잔액, 내역, 지출, 소비, 분석, 카드값
- rag: 금리, 환율, 수수료, 상품 안내, FAQ, 이벤트 안내
- navigate: 홈으로, 처음으로 (순수 화면 이동만)

발화: "{user_text}"
```

> **이벤트 처리 방침**: "이벤트 화면으로 이동"이 아닌 "이벤트 안내"는 RAGAgent가 TTS로 답변한다. navigate 도메인에는 `"event"` 케이스를 포함하지 않는다. (근거: 시각장애인 사용자에게는 화면 이동보다 음성 안내가 우선이다.)

모델: `gpt-4o-mini` (도메인 분류만, 저비용)

### Supervisor → SubAgent 데이터 흐름 명세

Supervisor는 **도메인 라우터**다. intent 분류·slot 추출을 하지 않는다.  
SubAgent는 원본 `HumanMessage`를 직접 읽어 처음부터 처리한다.

```
STT transcript
    │
    ▼ HumanMessage로 messages에 추가
[Supervisor 노드]
    ← 읽는 것: messages (HumanMessage 포함), VoiceState 전체
    → 결정: 도메인 ("transfer" | "asset" | "rag" | "navigate")
    → 쓰는 것: agent_domain (+ navigate 시 navigate_to)
    → SubAgent에 전달: 전체 VoiceState 그대로 (intent/slot 미추출)
          │
          ▼
[SubAgent (예: TransferAgent)]
    ← 원본 HumanMessage를 직접 읽어 intent 분류 + slot 추출
    ← Supervisor로부터 별도 intent/slot 정보를 받지 않는다
```

**이중 해석 위험 (Two-Pass Interpretation)**

동일 발화를 Supervisor(도메인 분류)와 TransferAgent `intent_node`(intent 분류)가 독립적으로 해석한다. 두 LLM의 해석이 불일치할 수 있다.

예시: "매달 50만원씩 보내줘"
- Supervisor: "transfer 도메인" → TransferAgent 라우팅
- TransferAgent intent_node: "auto_transfer" (자동이체) 또는 "transfer" (일회성)로 분류

Supervisor가 먼저 분류했으므로 도메인은 맞지만, SubAgent의 세부 intent 분류가 사용자 의도와 다를 수 있다. 이 위험은 TransferAgent의 intent_node 프롬프트 품질에 달려 있다 — Supervisor 프롬프트가 아닌 TransferAgent 프롬프트에서 처리해야 한다.

**ASV 성공 후 `ainvoke` 재진입 문제 (Dev-A + Dev-B 확인 필수)**

`_proceed_after_asv_success()`는 `execution_ready=True`를 주입한 후 `graph.ainvoke`를 재호출한다. Supervisor 그래프에서 이 `ainvoke`는 Supervisor 노드부터 재시작된다.

```python
# service.py 현재 흐름
await graph.aupdate_state(config, {"execution_ready": True, ...}, as_node="intent_node")
result = await graph.ainvoke({"messages": [HumanMessage("인증 완료")], ...}, config=config)
# ↑ Supervisor 그래프 → supervisor_node부터 시작 → execution_ready=True 확인 없이 도메인 재분류?
```

Supervisor의 `_decide_domain`이 `execution_ready=True`를 패스트패스 조건으로 확인하지 않으면 TransferAgent 대신 다른 도메인으로 라우팅될 수 있다.

**수정**: `_decide_domain` 패스트패스 최상단에 `execution_ready` 조건 추가.

```python
async def _decide_domain(state: VoiceState) -> str:
    # [ASV 성공 후 실행 준비] — 최우선 패스트패스
    if state.get("execution_ready"):
        return "transfer"   # execution_ready는 항상 transfer 도메인에서 발생
    ...
```

---

## 2. TransferAgent (Dev-B 담당)

### 역할
현재 `graph.py`의 이체 관련 노드를 그대로 추출한다. **로직 변경 없음**.

### 파일
`backend/app/shared/agent/subgraphs/transfer.py`

### 서브그래프 컴파일 규칙

```python
# subgraphs/transfer.py
transfer_graph = builder.compile(checkpointer=None)
# ↑ 반드시 checkpointer=None — 부모(Supervisor) MemorySaver를 공유한다.
# 독립 MemorySaver를 넘기면 thread_id가 분리되어 상태 충돌 발생.
```

### 담당 인텐트
```python
# subgraphs/transfer.py 내부에 정의 (Dev-B 소유 — Supervisor는 import하지 않음)
TRANSFER_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "transfer", "auto_transfer", "cancel_auto_transfer",
    "add_note", "add_auto_transfer_note",
})
```

### 노드 구성
```
intent_node (transfer-focused 프롬프트)
    │
    ├─ resolve_node       (수취인 검증)
    ├─ slot_fill_node
    ├─ confirm_node
    └─ execute_node
```

기존 `graph.py`에서 balance·event·home 인텐트 규칙 제거 → 프롬프트 **약 40% 단축**.

### ASV 흐름 보존
`awaiting_asv_audio` 처리는 `service.py`의 `_handle_asv_flow()`에서 유지.
Supervisor가 `awaiting_asv_audio=True`이면 패스트패스로 TransferAgent 라우팅 → ASV 흐름 보존.

### LLM 호출 횟수 트레이드오프 (팀 공유 사항)

| 케이스 | 단일 에이전트 | 멀티 에이전트 |
|--------|------------|------------|
| 이체 키워드 패스트패스 | LLM 1회 | LLM **0회** (Supervisor 패스트패스 → TransferAgent 패스트패스) |
| 모호한 첫 발화 | LLM 1회 | LLM **2회** (Supervisor 분류 + TransferAgent intent_node) |
| 잔액/내역 조회 | LLM 1회 | LLM **1회** (Supervisor 분류만, AssetAgent 노 슬롯) |

모호한 첫 발화에서 2회 호출이 발생하지만, `gpt-4o-mini` 사용으로 비용 증가는 미미하다.
이 트레이드오프를 팀이 인지하고 수용한다.

### 취소 처리 — Supervisor cancel_node 위임

TransferAgent는 취소 발화를 수신하지 않는다. 취소는 Supervisor의 `cancel_node`가 처리하므로 TransferAgent의 `intent_node` 프롬프트에 취소 인텐트 규칙을 포함하지 않는다.

이 분리의 이점:
- TransferAgent 프롬프트에서 `user_cancelled` 처리 로직 제거 가능
- 취소 상태 초기화 로직이 한 곳(`cancel_node`)에만 존재
- AssetAgent·RAGAgent도 동일하게 취소를 신경 쓰지 않아도 됨

---

## 3. AssetAgent (Dev-C 담당)

### 역할
잔액·거래내역 조회 + 지출 분석. 슬롯 없음, 확인 없음, ASV 없음.

### 파일
`backend/app/shared/agent/subgraphs/asset.py`

### 서브그래프 컴파일 규칙
```python
asset_graph = builder.compile(checkpointer=None)   # TransferAgent와 동일 규칙
```

### 담당 인텐트
```python
# subgraphs/asset.py 내부에 정의 (Dev-C 소유 — Supervisor는 import하지 않음)
ASSET_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "balance", "history",
    "spending_analysis", "monthly_report",
})
```

### 노드 구성
```
query_node → execute_node → END
```

- `query_node`: 발화에서 기간·카테고리 추출 + `analytics_period` 업데이트
  - 단순 잔액 조회는 LLM 없이 즉시 `execute_node`로
- `execute_node`: 기존 tool 호출

### `analytics_period` 초기화 정책

`query_node`에서 다음 규칙으로 초기화한다:

```python
def query_node(state: VoiceState) -> dict:
    user_text = last_user_text(state["messages"])
    period = _extract_period(user_text)   # "이번달" | "지난달" | "3개월" | None

    # 발화에 기간 힌트 없으면 이전 값 초기화 (새 질의로 간주)
    analytics_period = period if period else None

    ...
    return {"analytics_period": analytics_period, ...}
```

이전 턴에서 설정된 `analytics_period`는 **매 query_node 호출 시 덮어쓴다**. 이전 값을 이어받으려면 사용자가 다시 기간을 말해야 한다.

### navigate_to
- 잔액·내역 조회: `"balance"`
- 지출 분석: `"report"` → 신규 `app/report/index.tsx`

---

## 4. RAGAgent (Dev-D 담당)

### 역할
금융 FAQ, 환율/금리, 이벤트 TTS 안내. OpenSearch `financial_docs` 검색 후 LLM 요약.

### 파일
`backend/app/shared/agent/subgraphs/consultation.py`

### 서브그래프 컴파일 규칙
```python
# langgraph >= 0.2.0 에서 state_schema 파라미터 지원
# backend/requirements.txt 확인 필요: langgraph>=0.2.0
rag_agent = create_react_agent(
    llm,
    tools=[search_financial_docs, get_exchange_rate, get_base_rate, get_event_list],
    state_modifier=RAG_SYSTEM_PROMPT,
    state_schema=VoiceState,   # ← 반드시 명시 — 부모 VoiceState와 스키마 일치
)
# create_react_agent 결과를 subgraph로 사용할 때 checkpointer=None 컴파일 불필요
# (create_react_agent는 체크포인터를 별도 설정하지 않으면 부모를 자동 상속)
```

> **버전 사전 확인**: Dev-D는 `create_react_agent(state_schema=...)` 호출 전에 현재 프로젝트의 LangGraph 버전을 확인한다. 버전이 낮으면 `state_schema` 파라미터가 없어 `TypeError`가 발생한다. 확인 명령: `cd backend && .venv/bin/pip show langgraph | grep Version`

### 담당 인텐트
```python
# subgraphs/consultation.py 내부에 정의 (Dev-D 소유 — Supervisor는 import하지 않음)
RAG_DOMAIN_ACTIONS: frozenset[str] = frozenset({
    "financial_qa", "exchange_rate", "interest_rate", "event",
})
```

### 이벤트 처리 방침
"이벤트 화면 이동"은 navigate 도메인이 아닌 RAGAgent가 처리한다.
RAGAgent는 `get_event_list` tool로 이벤트 목록을 가져와 TTS로 읽어준다.
`navigate_to`는 항상 `None` — RAGAgent는 화면을 이동하지 않는다.

### RAGAgent tool 메시지와 TTS 오염 주의 (Dev-D)

`create_react_agent`의 ReAct 패턴은 `VoiceState.messages`에 아래 순서로 메시지를 추가한다:

```
1. HumanMessage("자동이체 수수료 면제 조건이 뭐야?")
2. AIMessage(tool_calls=[...])    ← tool 호출 JSON — TTS로 읽히면 안 됨
3. ToolMessage(content="...")     ← tool 결과 원문 — TTS로 읽히면 안 됨
4. AIMessage(content="수수료는...")← 최종 요약 ← TTS 대상
```

`voice/service.py`의 TTS 추출 함수가 `tool_calls`가 없는 마지막 AIMessage를 사용하는지 확인한다.

```python
# tts_text_from_messages — 확인 포인트
def tts_text_from_messages(messages) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content
    return DEFAULT_TTS_FALLBACK
```

Dev-D는 RAGAgent 통합 테스트에서 최종 `messages` 목록을 출력하여 tool 메시지가 TTS로 전달되지 않는지 확인한다.

### 신규 Tool: `search_financial_docs`
파일: `tools/financial_qa.py` (Dev-D 담당)

```python
@tool
def search_financial_docs(query: str, user_id: str) -> str:
    """금융 FAQ를 OpenSearch financial_docs 인덱스에서 검색합니다."""
    client = get_os_client()
    try:
        result = client.search(
            index=FINANCIAL_DOCS_INDEX,
            body={
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^2", "content"]
                    }
                },
                "size": 3
            }
        )
    except OpenSearchException as e:
        raise OpenSearchError(
            code="SEARCH_FAILED",
            message="금융 FAQ 검색 중 오류가 발생했습니다.",
        ) from e
    hits = [h["_source"]["content"] for h in result["hits"]["hits"]]
    if not hits:
        return "해당 내용을 찾을 수 없습니다. 우리은행 고객센터(1588-5000)로 문의해 주세요."
    return "\n".join(hits[:3])
```

---

## 5. 상태 관리

### MemorySaver 위치
Supervisor 그래프 레벨에만 `MemorySaver` 설정.  
모든 서브그래프는 `checkpointer=None`으로 컴파일하여 부모 체크포인트를 공유한다.

```python
# shared/voice/service.py — 변경은 1줄
def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_supervisor()   # 기존: build_graph(ALL_TOOLS)
    return _graph
```

### MemorySaver 공유 규칙 (Dev-B, C, D 공통)

```
부모 그래프: MemorySaver(thread_id=user_id) ← 체크포인트 저장소
    ├── subgraphs/transfer.py   compile(checkpointer=None) ← 부모 공유
    ├── subgraphs/asset.py      compile(checkpointer=None) ← 부모 공유
    └── subgraphs/consultation.py  create_react_agent(state_schema=VoiceState) ← 부모 공유
```

서브그래프에 독립 `MemorySaver()`를 주면 같은 `user_id`에 대해 체크포인트가 분리된다. 이체 중 잔액 조회 발화 시 `pending_action`이 소실되어 ASV 흐름이 깨진다.

### VoiceState 신규 필드 (state.py에 추가, Dev-A 담당)

```python
class VoiceState(TypedDict):
    # ... 기존 15개 필드 전부 유지 ...
    agent_domain: str | None      # Supervisor가 기록 ("transfer"|"asset"|"rag"|"navigate")
    analytics_period: str | None  # AssetAgent용 ("이번달"|"지난달"|"3개월")
```

### 신규 필드 초기값 (voice/service.py 또는 graph 진입점)

LangGraph StateGraph는 첫 `ainvoke` 시 state를 생성할 때 TypedDict의 모든 필드가 존재해야 한다. 기존 `build_graph()` 진입점에서 이미 초기 state를 주입하는 위치가 있다면, 거기에 두 필드의 기본값을 추가한다.

```python
# voice/service.py — _invoke_graph() 또는 초기 state 생성 위치에 추가
initial_state_defaults = {
    # 기존 필드들 ...
    "agent_domain": None,       # 첫 발화 전까지 도메인 미결정
    "analytics_period": None,   # 기간 미지정 상태
}
```

이 두 필드는 TypedDict에 `| None`으로 선언되어 있으므로, 기존 세션(MemorySaver에 이미 저장된)에는 해당 키가 없다. LangGraph는 누락된 TypedDict 키를 `None`으로 처리하지 않고 KeyError를 발생시킬 수 있다. Dev-A는 첫 배포 시 기존 세션과의 호환성을 확인해야 한다.

---

## 6. 에이전트 간 통신 프로토콜

> **구현 시작 전에 모든 담당자가 아래 계약을 숙지해야 한다.**

---

### 기본 원칙

| 번호 | 원칙 |
|------|------|
| P1 | 하위 에이전트는 **자신의 출력 계약에 명시된 필드만 쓴다** |
| P2 | 모든 에이전트는 `messages`에 **append**한다 — `add_messages` 리듀서 자동 처리 |
| P3 | 에러는 exception을 **그대로 raise**한다 — `AppError` 서브클래스를 써서 `main.py`의 단일 핸들러가 처리하게 한다 |
| P4 | Supervisor는 `agent_domain`과 navigation 시 `navigate_to`만 쓴다. **예외**: `cancel_node`는 세션 상태 전체를 초기화하기 위해 TransferAgent 소유 필드를 포함한 모든 필드를 초기화할 수 있다 |

> **P3 상세**: 에이전트 내부에서 `except Exception → AIMessage` 패턴은 **금지**한다. `AppError.message`가 TTS 에러 메시지의 단일 진실 원천이며, `main.py`의 `exception_handler`가 이를 음성으로 변환한다. 에이전트가 예외를 삼키면 이 체계가 붕괴된다.
>
> ```python
> # 금지 패턴
> except Exception as e:
>     return {"messages": [AIMessage(content="오류...")]}  # ← AppError 체계 파괴
>
> # 올바른 패턴
> except SomeException as e:
>     raise AgentError(code="AGENT_TOOL_FAILED", message="처리 중 오류.") from e
> ```

---

### VoiceState 필드 소유권

| 필드 | 쓰는 담당자 | 읽는 담당자 |
|------|------------|------------|
| `pending_action` | **Dev-B** | Dev-A (Supervisor) |
| `collected_slots` | **Dev-B** | Dev-A |
| `awaiting_confirmation` | **Dev-B** | Dev-A |
| `awaiting_asv_audio` | **Dev-B** | Dev-A |
| `execution_ready` | **Dev-B** | Dev-A |
| `recipient_validated` | **Dev-B** | — |
| `asv_retry_count` | **Dev-B** | Dev-A |
| `awaiting_memo_decision` | **Dev-B** | Dev-A |
| `awaiting_transfer_clarification` | **Dev-B** | Dev-A |
| `draft_recipient` | **Dev-B** | — |
| `last_tx_id` | **Dev-B** | — |
| `last_order_id` | **Dev-B** | — |
| `navigate_to` | **Dev-A** (navigate시) + **Dev-B, Dev-C** | `_layout.tsx` |
| `messages` | **모든 담당자** | TTS pipeline |
| `user_id` | `voice/service.py` 주입 | 모든 담당자 (읽기 전용) |
| `agent_domain` | **Dev-A** | Dev-A (패스트패스) |
| `analytics_period` | **Dev-C** | — |

---

### 입력 계약 (각 에이전트가 읽는 필드)

`ROUTING_CONSTANTS.py`의 `TRANSFER_READ`, `ASSET_READ`, `RAG_READ`로 공식화된 계약이다. 에이전트는 이 집합 밖의 필드를 읽어서는 안 되며, 단독 테스트 시 최소 mock state 구성의 기준으로 사용한다.

```python
# ROUTING_CONSTANTS.py (Dev-A가 정의, 각 Sub-agent는 import해서 테스트에 사용)

TRANSFER_READ = {
    "messages", "user_id",
    "pending_action", "collected_slots",
    "awaiting_confirmation", "awaiting_asv_audio",
    "execution_ready", "recipient_validated", "asv_retry_count",
    "awaiting_memo_decision", "awaiting_transfer_clarification",
    "draft_recipient", "last_tx_id", "last_order_id",
}

ASSET_READ = {"messages", "user_id", "analytics_period", "agent_domain"}

RAG_READ = {"messages", "user_id"}
```

> **ROUTING_CONSTANTS의 범위**: TRANSFER_DOMAIN_ACTIONS, ASSET_DOMAIN_ACTIONS, RAG_DOMAIN_ACTIONS 같은 도메인 action 집합은 이 파일에 두지 않는다. 이 집합들은 각 Sub-agent가 자기 파일 내부에서 정의하고 사용한다. Supervisor는 state 플래그만으로 라우팅하므로 구체적인 action 이름을 알 필요가 없다.

---

### 출력 계약 (각 에이전트가 반환하는 필드)

변경한 필드만 반환한다 (LangGraph 델타 업데이트 패턴).

```python
# TransferAgent — 이체 완료 후 (Dev-B)
{
    "messages": [AIMessage(content="이체가 완료되었습니다.")],
    "navigate_to": "transfer/complete",
    "pending_action": None,
    "collected_slots": {},
    "awaiting_confirmation": False,
    "awaiting_asv_audio": False,
    "execution_ready": False,
    "last_tx_id": "uuid-...",
    "awaiting_memo_decision": True,
}

# TransferAgent — 슬롯 수집 중간 턴 (Dev-B)  ← navigate_to=None 명시 필수
{
    "messages": [AIMessage(content="얼마를 보낼까요?")],
    "navigate_to": None,        # ← 반드시 None 명시. 생략하면 이전 턴 "transfer" 값이 잔류
    "collected_slots": {"recipient": "엄마"},
}

# AssetAgent — 잔액 조회 (Dev-C)
{
    "messages": [AIMessage(content="전체 잔액은 삼십만 원입니다.")],
    "navigate_to": "balance",
    "analytics_period": None,   # 기간 미지정이면 항상 None으로 초기화
}

# RAGAgent — FAQ 응답 (Dev-D)
{
    "messages": [AIMessage(content="자동이체 수수료는 우대 고객에게 면제됩니다.")],
    "navigate_to": None,        # Dev-D는 항상 None — 절대 변경 금지
}
```

> **`navigate_to` 오염 방지 규칙**: 화면 이동이 없는 모든 중간 턴에서 `navigate_to=None`을 **명시적으로 반환**한다. 필드를 생략하면 LangGraph는 이전 체크포인트 값을 그대로 유지한다. 이전 턴의 `"transfer"` 값이 남아있으면 프론트엔드가 동일 화면으로 반복 이동한다.

---

### navigate_to 값 계약

| 담당자 | 가능한 navigate_to 값 |
|--------|----------------------|
| **Dev-A** (Supervisor) | `"home"`, `None` |
| **Dev-B** (TransferAgent) | `"transfer"`, `"transfer/complete"`, `"auto-transfer"`, `"auto-transfer/complete"`, `None` |
| **Dev-C** (AssetAgent) | `"balance"`, `"report"`, `None` |
| **Dev-D** (RAGAgent) | **항상 `None`** — 절대 변경 금지 |

---

### ASV 흐름 보호 규칙 (Dev-B 전용)

`awaiting_asv_audio=True` → `False` 로 바꾸는 코드는 **아래 두 곳에만** 허용된다:

1. ASV 인증 성공: `service.py`의 `_proceed_after_asv_success()`
2. 3회 초과 실패: `service.py`의 `_handle_asv_flow()`

다른 코드에서 이 필드를 `False`로 바꾸면 인증 흐름이 중단된다.

---

### 단독 테스트 계약 (각 담당자 격리 테스트)

각 에이전트는 Supervisor 없이 **최소 필수 필드만** 주입하여 독립 테스트한다.
(전체 VoiceState를 주입하면 신규 필드 추가 시마다 테스트가 깨진다.)

```python
# Dev-C: AssetAgent 단독 테스트 예시
from app.shared.agent.subgraphs.asset import asset_graph
from langchain_core.messages import HumanMessage

# 최소 필수 필드만 (ASSET_READ 기준)
state = {
    "messages": [HumanMessage(content="잔액 얼마야")],
    "user_id": "test-user-uuid",
    "analytics_period": None,
    "agent_domain": "asset",
}
result = await asset_graph.ainvoke(
    state, config={"configurable": {"thread_id": "test"}}
)
assert "잔액" in result["messages"][-1].content
assert result.get("navigate_to") == "balance"
assert "analytics_period" in result   # 초기화 여부 확인
```

---

## 7. 파일 변경 목록

### Dev-A 신규 생성

```
backend/app/shared/agent/
├── supervisor.py                  ← SupervisorAgent 노드 + 엣지 함수
├── ROUTING_CONSTANTS.py           ← 도메인 상수 (팀 공유 첫 번째 산출물)
└── subgraphs/
    └── __init__.py
```

### Dev-B 신규 생성

```
backend/app/shared/agent/subgraphs/
└── transfer.py                    ← graph.py 이체 노드 추출 (~500줄)
```

### Dev-C 신규 생성

```
backend/app/shared/agent/subgraphs/
└── asset.py                       ← AssetAgent (~120줄)

backend/app/shared/agent/tools/
└── spending_analysis.py           ← get_monthly_spending_report, compare_spending

backend/app/features/analytics/
├── __init__.py
├── router.py                      ← GET /api/analytics/monthly
├── service.py
└── schema.py

frontend/app/report/index.tsx
frontend/services/reportService.ts
frontend/constants/categoryTheme.ts
```

### Dev-D 신규 생성

```
backend/app/shared/agent/subgraphs/
└── consultation.py                ← RAGAgent (~80줄)

backend/app/shared/agent/tools/
├── financial_qa.py                ← search_financial_docs
└── market_info.py                 ← get_exchange_rate, get_base_rate
```

### 수정 필요 (주로 Dev-A)

| 파일 | 변경 내용 | 담당 |
|------|-----------|------|
| `shared/agent/graph.py` | `build_graph()` → supervisor 반환; 노드 → `subgraphs/transfer.py` | Dev-A + Dev-B 협업 |
| `shared/agent/state.py` | `agent_domain`, `analytics_period` 필드 추가 | Dev-A |
| `shared/agent/prompts.py` | TransferAgent 전용 프롬프트 (balance·event 규칙 제거) | Dev-B |
| `shared/agent/slot_schema.py` | 신규 인텐트 추가 | Dev-A |
| `shared/agent/tools/__init__.py` | 신규 tool 등록 (각 Step과 동시에) | 각 담당자 |
| `shared/voice/service.py` | **6곳 변경** — 아래 상세 참조 | Dev-A |
| `main.py` | analytics 라우터 등록 | Dev-C |
| `app/home/index.tsx` | 퀵 메뉴에 "지출 분석", "환율·금리" 추가 | Dev-C |

### service.py 변경 상세 (Dev-A 담당)

실제 `service.py` 코드를 확인한 결과, "1줄 변경"으로 끝나지 않는다. 아래 6곳을 모두 수정해야 한다.

#### 1) import 변경
```python
# 변경 전
from app.shared.agent import build_graph
from app.shared.agent.tools import ALL_TOOLS

# 변경 후
from app.shared.agent import build_supervisor   # build_graph → build_supervisor
# ALL_TOOLS import 제거 — supervisor 내부에서 각 에이전트별로 tool 주입
```

#### 2) `_get_graph()` 변경
```python
# 변경 전
_graph = build_graph(ALL_TOOLS)

# 변경 후
_graph = build_supervisor()
```

#### 3) `_voice_state_reset_payload()` — 신규 필드 추가
```python
# 변경 전: agent_domain, analytics_period 없음 → reset 후 이전 도메인 잔류

# 변경 후
def _voice_state_reset_payload() -> dict:
    return {
        # ... 기존 필드 ...
        "agent_domain": None,        # ← 추가
        "analytics_period": None,    # ← 추가
    }
```

#### 4) `reset_voice_state()` — `as_node` 변경
현재 코드에 `as_node="intent_node"` 가 **4곳** 존재한다 (line 124, 403, 416, 469).  
리팩토링 후 `intent_node`는 TransferAgent 서브그래프 내부에 있으므로 최상위 Supervisor 그래프에서는 존재하지 않는 노드다. `aupdate_state(config, ..., as_node="intent_node")`는 모두 오류가 발생한다.

```python
# 변경 전 (4곳 전부)
await graph.aupdate_state(config, {...}, as_node="intent_node")

# 변경 후 — Supervisor 노드 이름으로 교체
await graph.aupdate_state(config, {...}, as_node="supervisor_node")
```

> **Dev-A 확인 필수**: `supervisor_node`가 Supervisor 그래프에 등록된 실제 노드 이름과 일치하는지 구현 시 재확인한다. LangGraph `aupdate_state`의 `as_node` 파라미터는 그래프에 등록된 노드 이름 문자열과 정확히 일치해야 한다.

#### 5) `_resolve_navigate_to()` — 데드 브랜치 정리
```python
# 현재 코드: pending in ("balance", "history", "event", ...) 폴백 로직
# 멀티에이전트 후: AssetAgent가 navigate_to를 직접 반환하므로 이 폴백은 동작 안 함
# → 코드는 제거하지 않아도 동작에 지장 없으나, 혼란 방지를 위해 주석 처리 권장
```

#### 6) `navigate_to == "home"` 후 reset 흐름 검증
```python
# 현재 흐름: navigate_to == "home" → reset_voice_state() → as_node="intent_node"
# 변경 후:  navigate_to == "home" → reset_voice_state() → as_node="supervisor_node"
# 위 4번 변경이 적용되면 자동으로 해결된다.
```

---

### 변경 없음

- `shared/voice/router.py`, `stt_service.py`, `tts_service.py`
- `features/transfer/`, `features/auto_transfer/`, `features/balance/`, `features/event/`
- 프론트엔드 (report 화면 추가 제외)

---

## 8. 구현 순서

```
[Day 1 — 병렬 진행 가능]

Dev-A: ROUTING_CONSTANTS.py 정의 → 팀 공유 (블로커 해제)
       state.py 필드 2개 추가
       supervisor.py 초안 작성

Dev-B: ROUTING_CONSTANTS.py 수령 후
       subgraphs/transfer.py 노드 추출 시작
       tools/__init__.py에서 기존 transfer 관련 tool 정리

Dev-C: ROUTING_CONSTANTS.py 수령 후
       tools/spending_analysis.py 작성
       → tools/__init__.py에 즉시 등록
       subgraphs/asset.py 작성

Dev-D: ROUTING_CONSTANTS.py 수령 후
       tools/financial_qa.py + tools/market_info.py 작성
       → tools/__init__.py에 즉시 등록 (각 tool 완성 즉시)
       subgraphs/consultation.py 작성
       ※ 사전조건: financial_docs 인덱스에 문서 5건 이상 색인

[Day 2 — 통합]

Dev-A: supervisor.py 완성 (하위 에이전트 서브그래프 import 필요)
       graph.py build_supervisor() 연결
       전체 통합 테스트

Dev-B: subgraphs/transfer.py 완성 + ASV 흐름 회귀 테스트
       ★ 가장 위험한 단계. 별도 PR 권장.

[Day 3 — 마무리]

Dev-C: app/report/index.tsx 화면 구현 (asset.py 완성 후)
Dev-A: slot_schema.py, prompts.py 최종 업데이트
```

> **tools/__init__.py 업데이트 규칙**: 각 담당자는 자신의 tool 파일을 완성하는 즉시 `tools/__init__.py`에 등록한다. Step 6로 미루지 않는다.

---

## 9. 검증

### 회귀 테스트 (Dev-B — transfer 추출 완료 후 필수)

```bash
cd backend
.venv/bin/pytest tests/ -v -k "transfer or asv or auto_transfer"
```

수동 E2E 시나리오:
1. "엄마한테 이체해줘" → `navigate_to="transfer"` 확인
2. 금액 슬롯 수집 → 확인 메시지 확인
3. "네" → `awaiting_asv_audio=True` 확인
4. ASV 인증 성공 → `navigate_to="transfer/complete"` 확인

### Supervisor 라우팅 단위 테스트 (Dev-A)

```python
# tests/test_supervisor_routing.py
assert _decide_domain(state_with(pending="transfer")) == "transfer"   # 패스트패스
assert _decide_domain(state_with(awaiting_asv=True)) == "transfer"    # ASV 패스트패스
assert _decide_domain(state_with(domain="asset")) == "asset"          # agent_domain 패스트패스
assert _decide_domain(state_with_text("잔액 얼마야")) == "asset"       # LLM 분류
assert _decide_domain(state_with_text("자동이체 수수료?")) == "rag"     # LLM 분류
assert _decide_domain(state_with_text("홈으로 가줘")) == "navigate"    # LLM 분류
```

### notification_agent 범위 외
기존 계획 문서의 Feature 3(푸시 알림)은 이 설계에 포함하지 않는다.
음성 파이프라인과 독립된 백그라운드 서비스로, 별도 PDCA 사이클에서 진행한다.
