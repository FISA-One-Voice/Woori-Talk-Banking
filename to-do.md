# to-do.md

프로젝트 작업 이력 및 후속 과제를 기록합니다. (최신 항목이 위)

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

### 후속 과제 (선택)

- [x] `voice-pipeline-flow.md` 플로우 다이어그램 갱신
- [ ] Mock 모드(`USE_MOCK_TOOLS=true`)에서 이체 후 `txId`·메모 턴 연동
- [ ] LLM 인텐트 프롬프트에 `add_note` / 메모 제안 예시 발화 추가
- [ ] 버튼으로 메모 저장 시에도 에이전트 TTS 완료 안내 통일 여부 검토

---

## 2026-06-02 (이전) — `asset_router` import 수정

- `backend/app/main.py`에 `asset_router` import 누락 수정

---

## 개발 실행 참고

- 백엔드: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- 프론트: `cd frontend && nvm use && npm start`
- `.env`: `EXPO_PUBLIC_API_BASE_URL=http://<LAN_IP>:8000`, `USE_MOCK_TOOLS=false` (실제 이체·메모 tool)
