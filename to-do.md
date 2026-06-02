# to-do.md

프로젝트 작업 이력 및 후속 과제를 기록합니다. (최신 항목이 위)

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
- [ ] 계좌번호 직접 이체(`classify` account) — `bank_name` 슬롯·`lookup` 경로 구현
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
