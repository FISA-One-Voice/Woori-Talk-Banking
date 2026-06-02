# to-do.md

프로젝트 작업 이력 및 후속 과제를 기록합니다. (최신 항목이 위)

---

## 2026-06-02 — 계좌번호 음성 이체 (슬롯 통합)

> 계획 문서: `계좌번호_음성_이체_4ea8c234.plan.md`  
> 선행 작업: [애매한 수취인 힌트 + TTS STT 에코 수정](#2026-06-02--애매한-수취인-힌트전화계좌만--tts-stt-에코-수정) (`transfer_clarification`, `message_utils`)  
> REST 이체 API(`execute_transfer`)는 원래 계좌+은행 직접 이체를 지원했으나, **음성 에이전트·resolve·execute 경로만 막혀 있던 상태**를 해소.

### 배경·문제

| 이슈 | 원인 |
|------|------|
| `classify`가 `account`인데 항상 실패 | `lookup_recipient_by_voice`의 account 분기가 `None` 고정 (주석: 은행명 필요) |
| 등록 계좌도 은행명을 다시 물음 | `registered_recipients`에 `bank_name`·`account_number`가 있음에도 조회 미구현 |
| resolve 후 execute 실패 | `find_recipient_by_voice`가 **이름 문자열만** 반환 → `recipient`를 실명으로 덮어쓴 뒤 계좌번호로 재조회 불가 |
| 확인 화면에 은행 미표시 | 프론트 `recipientFromSlots`가 `toBankName: ''` 고정 |

### 설계 원칙 (경로별 슬롯 분리 안 함)

- **문서화 슬롯**: `SLOT_SCHEMA["transfer"]` = `recipient`, `amount` 그대로.
- **경로 판별**: `classify_recipient_input(slots["recipient"])` → `name` | `phone` | `account`.
- **조건부 추가**: `account`이고 **등록 매칭 실패**(`recipient_id` 없음)일 때만 `bank_name`을 `transfer_missing_slots()`로 누락 처리.
- **resolve 결과 enrich**: 실행·UI용으로 `bank_name`, `account_number`, `recipient_id`를 `collected_slots`에 **보강** (별도 `recipient_kind` 메타 필드 없음).

### `collected_slots` 예시 (resolve 성공 후)

| 경로 | recipient (안내/TTS) | bank_name | account_number | recipient_id |
|------|----------------------|-----------|----------------|--------------|
| 별명·이름 | `엄마` (alias 우선) | DB | DB 평문 | UUID |
| 전화 | 가입자 실명 | 주계좌 은행 | 주계좌 번호 | `null` |
| 등록 계좌번호 | `엄마` (alias) | DB | DB 평문 | UUID |
| 미등록 계좌번호 | `수취인` 또는 별명 | 발화·슬롯 | 정규화 digits | `null` |

---

### Phase 1 — Recipients (`backend/app/features/recipients/service.py`)

| 함수 | 역할 |
|------|------|
| `normalize_account_digits(value)` | `-`/공백 제거, 10~14자리 검증 (`execute_transfer`와 동일) |
| `match_by_registered_account(db, user_uuid, digits)` | 본인 `registered_recipients` 전건 복호화 비교. 0건/2건+ → `None`, 1건 → 행 반환 |
| `resolve_by_registered_account(...)` | 1건 매칭 시 `resolve_by_id`와 동일한 `ResolvedRecipient` |
| `resolve_direct_account(digits, bank_name, …)` | 미등록 직접 이체용 (`recipient_id=None`) |
| `lookup_recipient_by_voice` | `account` → 등록 계좌 조회; 미등록·은행 없음 → `None` |
| `lookup_recipient_for_transfer(..., bank_name=)` | account + `bank_name` 있으면 `resolve_direct_account` |
| `find_recipient_by_voice(...)` | **`ResolvedRecipient \| None`** 반환으로 변경 (graph·execute 공용) |

**암호화**: AES-GCM이라 `WHERE account_number = ?` 불가 → 사용자별 등록 수취인 **선형 복호화 비교** (수량 적음 전제).

---

### Phase 2 — Agent

#### `slot_schema.py`

- `transfer_missing_slots(collected_slots)` — transfer 전용 누락 목록 (`recipient` → `bank_name`(조건부) → `amount`).
- `SLOT_QUESTIONS["bank_name"]` — `"어느 은행 계좌인가요? …"`.
- `graph._missing_slots` / `_all_slots_filled` — `pending_action == "transfer"`일 때 위 헬퍼 사용.

#### `graph.py`

- **`resolve_node`**
  - `find_recipient_by_voice(user_id, recipient, bank_name)` 호출.
  - 성공 → `_enrich_slots_from_resolved()` (`recipient`, `bank_name`, `account_number`, `recipient_id`).
  - `account` + `bank_name` 없음 → `recipient_validated=False`, **digits 유지**, "찾을 수 없습니다" TTS 없음 → `slot_fill`이 은행 질문.
  - 그 외 실패 → 기존처럼 recipient 초기화 + 재입력 TTS.
- **`_format_confirm_message`**
  - `bank_name` + `account_number` 있으면 마스킹 계좌(`transfer.service._mask_account`) 포함 확인 문구.
- **`intent_node` 프롬프트**
  - `extracted_slots`에 `bank_name` 추출 예시 (`우리은행 110…`).

#### `tools/transfer.py` — `run_execute_transfer(..., collected_slots=)`

| 우선순위 | 조건 | 실행 |
|----------|------|------|
| 1 | `recipient_id` in slots | `resolve_by_id` → `execute_transfer` |
| 2 | `account_number` + `bank_name` in slots | `resolve_direct_account` → `execute_transfer` |
| 3 | 그 외 | `lookup_recipient_for_transfer(recipient, bank_name)` |

`execute_node`에서 `collected_slots=slots` 전달.

#### `transfer_clarification.py` (연동, 로직 변경 최소)

- 「네」 후 `pending_action=transfer`, `collected_slots={recipient: draft}`, `navigate_to=transfer`, `recipient_validated=False`.
- 다음 라우팅에서 **`resolve_node`** 진입 → 등록 계좌면 `bank_name` 질문 **생략**.

---

### Phase 3 — Frontend (`frontend/app/transfer/index.tsx`)

- `recipientFromSlots`: `bank_name` / `bankName` → `toBankName`, `recipient_id` → `recipientId`, `account_number` → `accountMasked`(간단 마스킹).
- **`stepResolver.ts` 변경 없음** — 여전히 `recipient`·`amount`만으로 단계 판단.
- `ConfirmStepView`는 기존대로 `bankName` 행 표시.

---

### Phase 4 — 테스트·문서

| 파일 | 내용 |
|------|------|
| `backend/tests/test_recipients.py` | `match_by_registered_account`, `lookup` account, `lookup_recipient_for_transfer` |
| `backend/tests/test_transfer_missing_slots.py` | 동적 `bank_name` 누락 3케이스 |
| `backend/tests/test_transfer_tools.py` | `lookup_recipient_for_transfer` mock, `recipient_id` 슬롯 execute |
| `voice-pipeline-flow.md` | `account` 행: 등록 조회 / 미등록 `bank_name` slot_fill |
| `to-do.md` | 본 섹션 |

**로컬 테스트 (DB 필요)**

```bash
cd backend
CRYPTO_NOOP=true pytest tests/test_recipients.py -v
```

**DB 없이 단위만**

```bash
pytest tests/test_transfer_tools.py tests/test_transfer_clarification.py tests/test_transfer_missing_slots.py --noconftest -q
```

---

### 음성 플로우 (시나리오별)

#### A. 등록된 계좌번호 (`123-456-789012` = 엄마 계좌)

```
[발화] "123456789012" 또는 "이체해줘" + 계좌
  → (선택) transfer_clarification → "네"
  → intent=transfer, navigate_to=transfer
  → resolve_node: match_by_registered_account → enrich (엄마, 국민은행, recipient_id)
  → slot_fill: "얼마를 보낼까요?"  (bank_name 질문 없음)
  → confirm TTS: "엄마님 국민은행 계좌 123456***9012로 오만 원 이체할까요?"
  → ASV → execute_node (recipient_id 경로)
```

#### B. 미등록 계좌번호

```
[발화] "99998888777766"
  → clarification → "네" → resolve (등록 없음, bank 없음)
  → slot_fill: "어느 은행 계좌인가요?"
[발화] "신한은행"
  → slots.bank_name 채움 → resolve → validated
  → amount → confirm → ASV → execute (account_number + bank_name 경로)
```

#### C. 한 턴에 은행+계좌+금액 (LLM 추출)

```
[발화] "우리은행 1101234567890 삼만원 이체해줘"
  → extracted_slots: recipient, bank_name, amount
  → resolve (등록/미등록/직접) → confirm → …
```

#### D. 전화만 (`010 1111 0003`)

- **본 작업 범위 밖** — 기존 `transfer_clarification` + `resolve_by_phone` 그대로.

---

### 3계층과의 관계

| 계층 | 계좌 이체 시 |
|------|----------------|
| 에이전트 `resolve_node` | 등록 계좌 DB 매칭·슬롯 enrich |
| `_layout` `navigate_to=transfer` | 최초 진입만 |
| `stepResolver` | `recipient` 있으면 amount/confirm (은행은 Confirm UI에만) |

---

### 후속 과제

- [ ] **실기기 E2E**: 등록 계좌 / 미등록 계좌 / `우리은행 + 계좌 + 금액` 한 턴
- [ ] **`test_agent_multiturn.py`**: mock LLM으로 account + `bank_name` 시나리오 추가 (계획 Phase 4)
- [ ] **`auto_transfer`**: `transfer_missing_slots` 패턴 복제
- [ ] **은행 코드 STT** (`1002` → 우리은행) — `parse_voice_transfer_hints` 등 (선택)
- [ ] 동일 계좌 **2명 이상 등록** 시 TTS로 별명 선택 유도 (현재는 `None` + 재입력)

### 커밋 제안 (미커밋 시)

1. `feat(recipients): match_by_registered_account 및 account lookup`
2. `feat(agent): 동적 bank_name·resolve enrich·execute 슬롯 분기`
3. `feat(transfer-ui): collected_slots bank_name 매핑` + tests/docs

---


## 2026-06-02 — 애매한 수취인 힌트(전화·계좌만) + TTS STT 에코 수정

### 배경

- `010 1111 0003`처럼 **전화·계좌만** 말하면 `intent=null`, `navigate_to=null` → 화면 미이동.
- `intent_node`가 AIMessage를 추가하지 않을 때 `voice/service.py`가 **`messages[-1]`(HumanMessage)** 를 TTS로 읽어 STT와 동일하게 들림.
- `SYSTEM_PROMPT`의 「의도 불명확 시 재질문」과 `intent_node` 규칙(`direct_response`에 슬롯 질문 금지)이 맞지 않아 LLM만으로는 송금 확인이 보장되지 않음.

### 완료한 작업

| 영역 | 내용 |
|------|------|
| `backend/app/shared/voice/message_utils.py` | `tts_text_from_messages()` — 마지막 AIMessage만 TTS, 없으면 기본 안내 |
| `backend/app/shared/voice/service.py` | 정상·ASV 흐름 TTS 추출 교체, `awaiting_transfer_clarification` 응답 |
| `backend/app/shared/agent/transfer_clarification.py` | 전화/계좌만 감지, 송금 확인 멀티턴(네→transfer, 아니오→취소, 잔액→balance) |
| `backend/app/shared/agent/state.py` | `awaiting_transfer_clarification`, `draft_recipient` |
| `backend/app/shared/agent/graph.py` | clarification 분기·fallback·`route_after_intent` END |
| `backend/app/shared/voice/schema.py` | API 필드 `awaiting_transfer_clarification` |
| `frontend/types/voice.ts` | 동일 필드 타입(선택) |
| `backend/tests/test_transfer_clarification.py` | 감지·멀티턴·TTS 추출 단위 테스트 9건 |

### 음성 플로우 (송금 확인)

```
"010 1111 0003" (이체·금액 키워드 없음)
  → awaiting_transfer_clarification=true
  → TTS: "송금을 도와드릴까요? 네 또는 아니오로 …"
  → navigate_to=null
       ↓ [다음 롱프레스]
"네"
  → pending_action=transfer, recipient=010 1111 0003
  → navigate_to=transfer → resolve_node → slot_fill(amount) …
"아니요"
  → 상태 초기화, TTS 안내
```

### 체크포인트 (되돌리기)

- 수정 **직전** 커밋: `chore(transfer): 3계층 리팩터 체크포인트 (음성 clarification 수정 전)` (`3cca292`)

### 후속 과제

- [ ] `VoiceStatusOverlay`에 `awaiting_transfer_clarification` 전용 UI (선택)
- [x] 계좌번호 직접 이체(`classify` account) — `bank_name` 슬롯·`lookup` 경로 구현
- [ ] 실기기: 전화만 → 확인 TTS → 「네」 후 `/transfer`·amount 질문 E2E

---

## 2026-06-02 — 이체 직후 메모 제안: 그래프 멀티턴 + `tx_id` 연동

### 배경

- 모든 음성은 에이전트가 통제하는 원칙에 맞춰, 메모 제안·수집을 **LangGraph 멀티턴**으로 이동.
- `add_note`는 **최근 거래 DB 조회** 대신 **`tx_id` / `last_tx_id`** 로 정확한 거래에 메모 저장.

### 완료한 작업

| 영역 | 내용 |
|------|------|
| `backend/app/shared/agent/state.py` | `awaiting_memo_decision`, `last_tx_id` |
| `backend/app/shared/agent/memo_decision.py` | 메모 제안 턴 발화 파싱 (건너뛰기 / 카테고리 / 재질문) |
| `backend/app/shared/agent/slot_schema.py` | `MEMO_OFFER_SUFFIX`, `add_note` 슬롯 |
| `backend/app/shared/agent/graph.py` | 이체 성공 시 메모 제안 TTS + `awaiting_memo_decision`; `intent_node` 메모 턴 처리; `route_after_intent` 분기 |
| `backend/app/shared/agent/tools/transfer.py` | `run_execute_transfer` → `txId`; `add_note(tx_id)` |
| `backend/app/shared/voice/schema.py` | `awaiting_memo_decision` 응답 필드 |
| `backend/app/shared/voice/service.py` | API 응답에 필드 전달 |
| `frontend/types/voice.ts` | `awaiting_memo_decision` 타입 |
| `frontend/components/VoiceStatusOverlay.tsx` | `awaiting_memo` 오버레이 |
| `frontend/app/_layout.tsx` | `txId` → `transferStore`, 메모 대기 오버레이 |
| `frontend/app/transfer/complete.tsx` | 로컬 TTS 제거, 요약·카테고리 버튼만 (터치 보조) |
| `backend/tests/test_memo_decision.py` | 메모 발화 파싱 테스트 |
| `backend/tests/test_transfer_tools.py` | `tx_id` 기반 tool 테스트 |

### 음성 플로우 (이체 + 메모)

```
이체 확인 → ASV → execute_transfer
  → TTS: "이체 완료. 메모를 남기시겠어요? …"
  → awaiting_memo_decision=true, last_tx_id 저장
  → navigate_to: transfer/complete (UI 요약·버튼)
       ↓ [다음 롱프레스]
"식비" / "건너뛰기"
  → intent_node (memo_decision)
  → add_note(last_tx_id) 또는 홈 이동
```

### 2026-06-02 — 화면 제어 3계층 리팩터 (transfer + complete)

- `_layout`: `router.replace`, `navigateFromAgent`, home 시 `transferStore.reset`
- `transfer/stepResolver.ts`, `views/*`, `index.tsx` (store 구독, TtsBubble 제거)
- `complete.tsx`: `goHome` + replace, `completeStepResolver`, views 분리
- `.cursorrules`, `voice-pipeline-flow.md` 3계층 문서

### 후속 과제 (선택)

- [x] `voice-pipeline-flow.md` 플로우 다이어그램 갱신
- [ ] 실기기 E2E (voice-pipeline 체크리스트) — 3계층 리팩터 후 재검증 권장
- [ ] Mock 모드(`USE_MOCK_TOOLS=true`)에서 이체 후 `txId`·메모 턴 연동
- [ ] LLM 인텐트 프롬프트에 `add_note` / 메모 제안 예시 발화 추가
- [ ] 버튼으로 메모 저장 시에도 에이전트 TTS 완료 안내 통일 여부 검토

---

## 2026-06-02 — 화면 제어 3계층 리팩터 (transfer + complete) — 상세

> 메모·`tx_id` 작업 **이후** 진행. 요약은 위 「화면 제어 3계층 리팩터」 항목 참고.

### 배경

- 「분기」를 세 계층으로 분리해 역할 혼선을 줄임.
  1. **백엔드 에이전트** — 슬롯·TTS·`navigate_to` (`resolve_node` = 수취인 DB 검증)
  2. **`_layout.tsx`** — `router.replace(navigate_to)` 로 **라우트만**
  3. **`stepResolver.ts` + `index.tsx`** — 같은 `/transfer` URL 안 **뷰만** 전환
- auto-transfer 담당자 `stepResolver` 패턴을 **참고만** 하고, 구현 scope는 **transfer + complete** 만.
- 스택은 `router.replace()` 단일 유지 (뒤로가기 시 transfer/complete 잔류 방지).

### 완료한 작업

| 계층 | 파일 | 내용 |
|------|------|------|
| Layer 2 | `frontend/app/_layout.tsx` | `navigateFromAgent()` — 전 경로 `router.replace`; `home` 시 `transferStore.reset()`; `transfer/complete` 시 `txReceipt` 유지 |
| Layer 3 | `frontend/app/transfer/stepResolver.ts` | `resolveTransferStep(slots, awaitingAsv)` — `input-alias` / `input-amount` / `confirm` / `asv-pending`, `STEP_INDEX`, `STEP_TOTAL=3`, `formatAmount` |
| Layer 3 | `frontend/app/transfer/index.tsx` | `useVoiceResponseStore` 구독 → `step = touchStep ?? voiceStep`; `switch(step)` 뷰만; `TtsBubble autoPlay` 제거 |
| Layer 3 | `frontend/app/transfer/views/` | `AliasStepView`, `AmountStepView`, `ConfirmStepView`, `AsvStepView` |
| Complete | `frontend/app/transfer/complete.tsx` | `goHome()` = `reset` + `replace('/home')`; `router.back()` 제거 |
| Complete | `frontend/app/transfer/completeStepResolver.ts` | 터치 phase: `summary` / `memo_done` / `error` |
| Complete | `frontend/app/transfer/views/Complete*.tsx` | `CompleteSummaryView`, `CompleteMemoDoneView`, `CompleteErrorView` |
| Dev | `frontend/app/dev/transfer-test.tsx` | mock에 `awaiting_memo_decision` 추가, `router.replace` |
| 문서 | `.cursorrules` | 3계층 표, `router.replace`, `resolve_node` ≠ `stepResolver` |
| 문서 | `voice-pipeline-flow.md` | 3계층 섹션, `router.replace`, transfer `stepResolver`·complete 라우트 분리 |

### 3계층 동작 요약 (이체 시나리오)

| 사용자 발화 | 에이전트 | `_layout` | `stepResolver` → index |
|-------------|----------|-----------|-------------------------|
| "엄마한테 이체해줘" | `resolve_node`, `navigate_to=transfer` | `replace('/transfer')` | `input-amount` (recipient 있음) |
| "30만원" | `navigate_to=null`, slots에 amount | 라우트 유지 | `confirm` |
| "네" | `awaiting_asv_audio=true` | Overlay `awaiting_asv` | `asv-pending` |
| ASV 후 이체 성공 | `navigate_to=transfer/complete` | `replace('/transfer/complete')` | (unmount) |
| "식비" / "건너뛰기" | 메모 저장 또는 `navigate_to=home` | `replace('/home')` + reset | complete unmount |

### 검증

- `cd frontend && npx tsc --noEmit` 통과
- 시뮬: `/dev/transfer-test` 시나리오 ①~④
- [ ] 실기기 E2E (`voice-pipeline-flow.md` 체크리스트 — Layer 2·3·Complete)

### 후속 과제 (3계층 리팩터 기준)

- [ ] 실기기: 슬롯 턴 시 URL `/transfer` 유지, confirm/ASV 뷰 전환, 메모 음성·터치
- [ ] 터치 메모 후 음성 `awaiting_memo_decision` 잔존 시 중복 저장 여부 확인

---

## 2026-06-02 (이전) — `asset_router` import 수정

- `backend/app/main.py`에 `asset_router` import 누락 수정

---

## 개발 실행 참고

- 백엔드: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- 프론트: `cd frontend && nvm use && npm start`
- `.env`: `EXPO_PUBLIC_API_BASE_URL=http://<LAN_IP>:8000`, `USE_MOCK_TOOLS=false` (실제 이체·메모 tool)
