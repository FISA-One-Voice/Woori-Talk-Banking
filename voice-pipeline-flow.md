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
        ├─ awaiting_*   → VoiceStatusOverlay 상태 변경
        └─ setLastResponse(data) → Zustand 업데이트

[화면 담당자]
  useVoiceResponseStore()
    └─ collected_slots → stepResolver → 세부 UI 분기
```

---

## 에이전트 노드 구성 및 라우팅

```
intent_node
    │ route_after_intent
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
| `navigate_to` + `_layout.tsx` | 기능 진입 / 기능 종료 | `"transfer"` → transfer 화면<br>`"transfer/complete"` → 완료 화면 |
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
  → execute_node 실행
  → navigate_to="transfer/complete" → /transfer/complete 이동
  → TTS: "이체가 완료되었습니다"
  → 3초 후 router.replace('/home')
```

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
| `frontend/app/transfer/complete.tsx` | 완료 화면 — 3초 뒤 홈 이동 |
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

```typescript
export default function TransferCompleteScreen() {
  const router = useRouter();

  useEffect(() => {
    const timer = setTimeout(() => router.replace('/home'), 3000);
    return () => clearTimeout(timer);
  }, []);

  return <CompleteView />;
}
```

#### 백엔드 tool 계약

| tool 이름 | 파라미터 | 반환 |
|-----------|----------|------|
| `lookup_recipient` | `user_id`, `alias` | `str` (recipient_name) 또는 `None` |
| `execute_transfer` | `user_id`, `alias`, `amount` | `str` (TTS 결과 메시지) |

`lookup_recipient` 내부에서 `lookup_recipient_by_voice()` 호출.

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
