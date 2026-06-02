# 음성 파이프라인 플로우 및 담당자별 Scope

## 전체 플로우

```
[사용자 롱프레스]
      │
      ▼
_layout.tsx (글로벌)
  ├─ 녹음 시작/종료 (useVoiceInput)
  ├─ POST /api/voice/voice
  └─ VoiceResponseData 수신
        ├─ audio        → TTS 재생
        ├─ navigate_to  → router.push() 화면 이동
        ├─ awaiting_asv_audio / awaiting_confirmation / awaiting_memo_decision
        │                     → VoiceStatusOverlay 상태 변경
        ├─ navigate_to=transfer/complete + collected_slots.txId
        │                     → transferStore.txReceipt (이체 영수증)
        └─ setLastResponse(data) → Zustand 업데이트

[화면 담당자]
  useVoiceResponseStore()
    └─ collected_slots → stepResolver → 세부 UI 분기
```

---

## 에이전트 노드 구성 및 라우팅

```
intent_node
    │ (이체 직후 메모 제안 턴: awaiting_memo_decision=true 이면 LLM 생략,
    │  memo_decision.build_memo_decision_update() 규칙 처리)
    │ route_after_intent
    ├─ awaiting_memo_decision=true → END   (메모 제안 대기, 다음 롱프레스)
    ├─ awaiting_asv_audio=true     → END   (ASV 인증 대기)
    ├─ execution_ready=true        → execute_node
    ├─ pending_action 없음         → END   (챗봇 직답)
    ├─ alias 있음 + validated=false → resolve_node   ← alias 즉시 검증
    ├─ 슬롯 누락                   → slot_fill_node
    ├─ SLOT_SCHEMA 없는 액션       → execute_node   (balance, event)
    └─ 슬롯 완전 수집              → confirm_node

resolve_node
    │ route_after_resolve
    ├─ 수취인 찾음  → alias=정규화된 이름, validated=true
    │    ├─ 다른 슬롯 누락  → slot_fill_node
    │    └─ 모든 슬롯 완전  → confirm_node
    └─ 없음        → alias=None, validated=false → slot_fill_node

slot_fill_node → END
confirm_node   → END
execute_node   → END
```

---

## navigate_to vs stepResolver 역할 분리

| 담당 | 역할 | 예시 |
|------|------|------|
| `navigate_to` + `_layout.tsx` | 기능 진입 / 기능 종료 | `"transfer"` → transfer 화면<br>`"transfer/complete"` → 완료 화면<br>`"home"` → 메모 저장·건너뛰기 후 홈 |
| `stepResolver` (화면 담당자) | 슬롯 수집 중 세부 단계 분기 | alias 없음 → 수신인 입력<br>amount 없음 → 금액 입력<br>모두 있음 → 확인 |

### 이체 전체 흐름 예시

```
"엄마한테 이체해줘"
  → navigate_to="transfer"         → /transfer 진입
  → alias="엄마" 감지              → resolve_node 즉시 실행
  → 엄마 = 홍어머니 (DB 조회 성공) → validated=true
  → stepResolver: amount 없음      → AmountInputView
  → TTS: "얼마를 보낼까요?"

"30만원"
  → navigate_to=null               → 현재 화면 유지
  → stepResolver: 모두 있음        → ConfirmView
  → TTS: "홍어머니에게 삼십만 원 이체할까요?"

"네"
  → awaiting_asv_audio=true        → VoiceStatusOverlay(인증 대기)
  → stepResolver: awaiting_asv     → AsvPendingView

[ASV 인증 성공]
  → execute_node: execute_transfer
  → last_tx_id, collected_slots.txId 저장
  → navigate_to="transfer/complete" → /transfer/complete 이동
  → TTS: "이체가 완료되었습니다." + MEMO_OFFER_SUFFIX
  → awaiting_memo_decision=true
  → VoiceStatusOverlay: awaiting_memo

[다음 롱프레스 — 음성 메모]
  "식비" / "교통비" 등
    → intent_node (memo_decision) → execution_ready + add_note
    → execute_node → add_note(last_tx_id) → TTS 완료 → navigate_to=home

  "건너뛰기" / "괜찮아요" 등
    → intent_node → navigate_to=home, awaiting_memo_decision=false

  "네" (카테고리 없음)
    → intent_node → pending_action=add_note, memo 슬롯 질문 TTS
    → 다음 발화로 카테고리 수집 후 execute_node

[complete 화면 — 터치 보조]
  → 로컬 TTS 없음 (메모 제안·안내는 에이전트 TTS만)
  → 카테고리 버튼 → saveMemo(txId) API (음성과 병행 가능)
  → 건너뛰기 버튼 → router.replace('/home')
```

### 이체 직후 메모 제안 (그래프 멀티턴)

```
execute_node (execute_transfer 성공)
      │
      ├─ last_tx_id = txId
      ├─ collected_slots.txId = txId
      ├─ awaiting_memo_decision = true
      └─ TTS += MEMO_OFFER_SUFFIX
            │
            ▼
      route_after_intent → END (화면: transfer/complete, 오버레이: awaiting_memo)
            │
            ▼ [사용자 롱프레스]
      intent_node (awaiting_memo_decision)
            │
            ├─ is_memo_skip(text)     → home, 플래그 해제
            ├─ match_memo_category    → add_note + execution_ready → execute_node
            ├─ 긍정만 (카테고리 없음) → memo 슬롯 질문 → 다음 턴 slot_fill/execute
            └─ 불명확                 → 재안내 TTS, 플래그 유지
```

| 상태 필드 | API·프론트 | 의미 |
|-----------|------------|------|
| `last_tx_id` | (그래프 내부) | 직전 이체 거래 ID — `add_note`에 전달 |
| `awaiting_memo_decision` | `VoiceResponseData` | 메모 제안에 대한 다음 발화 대기 |
| `collected_slots.txId` | `transferStore.txReceipt` | 완료 화면·터치 메모 API용 |

구현: `backend/app/shared/agent/memo_decision.py`, `slot_schema.MEMO_OFFER_SUFFIX`

### 수취인 못 찾는 경우

```
"모르는사람한테 이체해줘"
  → alias="모르는사람" 감지         → resolve_node 즉시 실행
  → DB 조회 실패                    → alias=None, validated=false
  → slot_fill_node
  → TTS: "'모르는사람'을(를) 찾을 수 없습니다. 다시 알려주세요."
```

---

## 수취인 입력 형식 분류 (`classify_recipient_input`)

`features/recipients/service.py`에 정의. `lookup_recipient_by_voice()`가 내부 호출.

| 입력값 | 형식 | 처리 |
|--------|------|------|
| "엄마", "홍길동" | `name` | `match_by_name()` → 1명이면 통과, 0명·동명이인 → None |
| "01012345678" | `phone` | `resolve_by_phone()` |
| "1101234567890" | `account` | 현재 미지원 (은행명 슬롯 추가 필요) → None |

---

## 담당자별 Scope

---

### 에이전트 담당자 (공통 인프라 — 선행 완료)

> 이 작업이 완료되어야 각 화면 담당자가 구현 시작 가능

#### 완료된 작업

| 파일 | 작업 |
|------|------|
| `frontend/store/voiceResponseStore.ts` | ✅ 신규 생성 |
| `frontend/app/_layout.tsx` | ✅ `setLastResponse()` 한 줄 추가 |
| `frontend/context/MicContext.tsx` | ✅ 삭제 (미사용 레거시) |
| `backend/app/shared/agent/slot_schema.py` | ✅ `COMPLETE_SCREEN_MAP`, `RECIPIENT_REQUIRED_ACTIONS` 추가 |
| `backend/app/shared/agent/state.py` | ✅ `recipient_validated` 필드 추가 |
| `backend/app/shared/agent/graph.py` | ✅ `resolve_node`, `route_after_resolve` 추가 + 라우팅 수정 |
| `backend/app/shared/agent/tools/mock_tools.py` | ✅ `mock_lookup_recipient` 추가 |
| `backend/app/features/recipients/service.py` | ✅ `classify_recipient_input`, `lookup_recipient_by_voice` 추가 |

#### 화면 담당자가 사용하는 인터페이스

```typescript
import { useVoiceResponseStore } from '@/store/voiceResponseStore';

// 화면 내에서
const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
const slots = lastResponse?.collected_slots ?? {};
const isAwaitingAsv = lastResponse?.awaiting_asv_audio ?? false;
```

---

### transfer 담당자

#### 생성 파일

| 파일 | 내용 |
|------|------|
| `frontend/app/transfer/index.tsx` | 화면 진입점 — stepResolver로 세부 UI 분기 |
| `frontend/app/transfer/stepResolver.ts` | 슬롯 상태 → 단계 결정 |
| `frontend/app/transfer/complete.tsx` | 완료 화면 — 요약·메모 버튼(터치 보조), TTS는 에이전트 |
| `backend/app/features/transfer/tools.py` | `lookup_recipient`, `execute_transfer` 툴 등록 |

#### stepResolver 로직

```typescript
// stepResolver.ts
export type TransferStep = 'input-alias' | 'input-amount' | 'confirm' | 'asv-pending';

export function resolveTransferStep(
  slots: Record<string, unknown>,
  awaitingAsv: boolean,
): TransferStep {
  if (awaitingAsv)   return 'asv-pending';
  if (!slots.alias)  return 'input-alias';
  if (!slots.amount) return 'input-amount';
  return 'confirm';
}
```

> `alias` 슬롯이 채워지면 에이전트가 즉시 resolve_node를 실행해 수취인 검증함.
> 검증 실패 시 alias가 null로 초기화되어 input-alias 단계로 복귀함.

#### index.tsx 구조

```typescript
export default function TransferScreen() {
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
  const slots = lastResponse?.collected_slots ?? {};
  const awaitingAsv = lastResponse?.awaiting_asv_audio ?? false;
  const step = resolveTransferStep(slots, awaitingAsv);

  if (step === 'asv-pending') return <AsvPendingView />;
  if (step === 'input-alias') return <AliasInputView />;
  if (step === 'input-amount') return <AmountInputView />;
  return <ConfirmView />;
}
```

#### complete.tsx 구조

- **음성**: 이체 완료·메모 제안 TTS는 `execute_node` + `MEMO_OFFER_SUFFIX` (에이전트만 재생).
- **화면**: `transferStore.txReceipt`(txId, 수취인, 금액) 요약, 카테고리 버튼, 건너뛰기.
- **터치 메모**: `saveMemo(txId, category)` — 음성 `add_note`와 동일 거래에 저장.
- 자동 홈 이동(3초 타이머) 없음 — 홈은 음성 건너뛰기·메모 완료 후 에이전트 `navigate_to=home` 또는 버튼.

#### 백엔드 tool 계약

| tool 이름 | 파라미터 | 반환 |
|-----------|----------|------|
| `lookup_recipient` | `user_id`, `alias` | `str` (recipient_name) 또는 `None` |
| `execute_transfer` | `user_id`, `alias`, `amount` | `(message, tx_id)` |
| `add_note` | `user_id`, `memo`, `tx_id` | `str` (TTS 결과 메시지) |

`add_note`는 **최근 거래 조회 없이** `tx_id`/`last_tx_id`로 대상 거래를 지정한다.

---

### auto-transfer 담당자

슬롯 수집 순서: `alias → amount → cycle → scheduled_day`

#### 생성 파일

| 파일 | 내용 |
|------|------|
| `frontend/app/auto-transfer/index.tsx` | 화면 진입점 |
| `frontend/app/auto-transfer/stepResolver.ts` | 4단계 슬롯 분기 |
| `frontend/app/auto-transfer/complete.tsx` | 완료 화면 — 3초 후 홈 이동 |
| `backend/app/features/auto_transfer/tools.py` | `lookup_recipient`, `execute_auto_transfer` 툴 등록 |

#### stepResolver 로직

```typescript
export type AutoTransferStep =
  'input-alias' | 'input-amount' | 'input-cycle' | 'input-day' | 'confirm' | 'asv-pending';

export function resolveAutoTransferStep(
  slots: Record<string, unknown>,
  awaitingAsv: boolean,
): AutoTransferStep {
  if (awaitingAsv)           return 'asv-pending';
  if (!slots.alias)          return 'input-alias';
  if (!slots.amount)         return 'input-amount';
  if (!slots.cycle)          return 'input-cycle';
  if (!slots.scheduled_day)  return 'input-day';
  return 'confirm';
}
```

---

### balance 담당자

슬롯 없는 단순 조회. stepResolver 불필요. TTS가 모든 정보를 전달.
`history` intent는 `SCREEN_MAP`에서 `balance`로 매핑되어 있어 이 화면에서 함께 처리.

#### 생성 파일

| 파일 | 내용 |
|------|------|
| `frontend/app/balance/index.tsx` | 정적 UI — TTS로 결과 전달 |

---

### event 담당자

슬롯 없음. `dev/event/`에 이미 구현 존재 → 정식 경로로 이동.

#### 생성/이동 파일

| 파일 | 내용 |
|------|------|
| `frontend/app/event/index.tsx` | `dev/event/index.tsx` 참고하여 이동 |
| `frontend/app/event/[id].tsx` | 이벤트 상세 |

---

## 작업 순서

```
에이전트 담당자 (완료)
  ✅ voiceResponseStore.ts 생성
  ✅ _layout.tsx 수정
  ✅ slot_schema.py COMPLETE_SCREEN_MAP, RECIPIENT_REQUIRED_ACTIONS 추가
  ✅ state.py recipient_validated 추가
  ✅ graph.py resolve_node 추가 + 라우팅 수정
  ✅ mock_tools.py mock_lookup_recipient 추가
  ✅ recipients/service.py classify_recipient_input, lookup_recipient_by_voice 추가
        ↓
각 화면 담당자 (병렬 진행 가능)
  transfer      → app/transfer/ 생성 + features/transfer/tools.py
  auto-transfer → app/auto-transfer/ 생성 + features/auto_transfer/tools.py
  balance       → app/balance/ 생성
  event         → app/event/ 생성
```

---

## Zustand store 명세

```typescript
// frontend/store/voiceResponseStore.ts
interface VoiceResponseState {
  lastResponse: VoiceResponseData | null;  // 최신 음성 응답 (최초 null)
  setLastResponse: (data: VoiceResponseData) => void;
}
```

`lastResponse`는 매 음성 응답마다 갱신됨. 화면 담당자는 읽기 전용으로만 사용.

---

## 실기기 E2E 체크리스트 (이체 + 메모)

사전 조건: `USE_MOCK_TOOLS=false`, DB·ASV 연결, 테스트 계정 로그인, LAN `EXPO_PUBLIC_API_BASE_URL`.

| # | 단계 | 기대 결과 |
|---|------|-----------|
| 1 | 홈에서 이체 intent (예: "엄마한테 1만원") | transfer 화면, 슬롯 수집 TTS |
| 2 | 확인 후 "네" | ASV 대기 오버레이 |
| 3 | ASV 성공 | complete 화면, TTS에 메모 제안 포함, `awaiting_memo` 오버레이 |
| 4a | 롱프레스 → "식비" | 메모 저장 TTS 후 홈 이동 |
| 4b | 롱프레스 → "건너뛰기" | 홈 이동, 메모 없음 |
| 5 | 3번 후 complete에서 카테고리 버튼 | API 메모 저장, 화면 완료 안내 |
| 6 | 3번 후 complete에서 건너뛰기 버튼 | 홈 이동 |

로그: 백엔드 `[Graph →intent_node] awaiting_memo_decision`, `last_tx_id` / `execute_transfer` txId.
