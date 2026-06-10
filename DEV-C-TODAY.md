# Dev-C 오늘 작업 정리 (2026-06-09)

> 발표용 정리. 브랜치: `feature/asset-compare`

---

## 오늘 한 것 요약

AssetAgent에 **기간 비교 기능**을 추가하고, 비교 전용 화면까지 완성했습니다.

---

## 1. 버그 수정

### Bug 1 — 멀티턴 컨텍스트 깨짐
**증상:** "지출 얼마야?" → "이번 달" 답하면 잔액 조회로 잘못 라우팅됨

**원인:** 두 번째 발화(기간만 말한 것)를 새로운 질문으로 처리해서 `action=balance`로 분류

**수정:** `collected_slots.action`(직전 턴의 미완 액션)을 먼저 확인 후, 기간 키워드만 있으면 이전 액션 이어받도록 처리

```python
# subgraphs/asset.py
elif pending_action and _has_period_keyword(user_text):
    action = pending_action  # 직전 액션 이어받기
    period = _fast_period(user_text)
```

---

### Bug 2 — 카테고리 조회 시 빈 결과
**증상:** "이번달 식비 얼마야?" → 결과 없음

**원인:** 이체 시 DB에 `category` 컬럼이 저장되지 않음 (TransferAgent 담당 코드 — Dev-C 수정 범위 외)

**해결:** 테스트용 시드 데이터 삽입 (`seed_category.py`)
- 김지연 유저에 식비/교통/쇼핑/의료비/생활비/문화생활 등 10건 삽입
- 실제 서비스에서는 TransferAgent가 카테고리 저장하도록 수정 필요 (Dev-B 담당)

---

### Bug 3 — 마이크 꾹 누르기 중간에 멈춤
**원인:** 네트워크 오류로 catch 블록에 떨어지면 audio session이 recording 모드로 남아 다음 녹음 시도 시 `prepareToRecordAsync` 실패

**조치:** `frontend/hooks/useVoiceInput.ts`에 주석으로 수정 방법 명시 (파일 소유권이 다른 팀원이라 코드 수정 대신 주석 처리)

```typescript
// [버그] catch에 떨어지면 audio session이 recording 모드로 남아 다음 녹음 불가
// 수정 방법: catch 블록에 아래 코드 추가
// await Audio.setAudioModeAsync({ allowsRecordingIOS: false, ... }).catch(() => undefined);
```

---

## 2. 신규 기능 — 기간 비교 (Compare)

### 2-1. 지원 발화 예시
| 발화 | 결과 |
|------|------|
| "이번달 지난달 비교해줘" | 전체 지출 비교 |
| "이번달 생활비 지난달이랑 비교해줘" | 생활비만 비교 |
| "이번주 지난주 식비 비교" | 이번주 vs 지난주 식비 |

### 2-2. 백엔드 — LLM 분류 (`subgraphs/asset.py`)

`compare` action 추가 + LLM 프롬프트에 카테고리 추출 명시

```
action=compare일 때 category가 언급되면 반드시 category 필드에 채울 것.
예) "생활비 이번달 지난달 비교" → category=생활비
```

LLM이 반환하는 JSON 예시:
```json
{
  "action": "compare",
  "period": "이번달",
  "compare_period": "지난달",
  "category": "생활비"
}
```

### 2-3. 백엔드 — 서비스 (`service.py`)

`query_compare_tts()` — 에이전트 TTS 응답용
```
이번달 생활비 지출은 4,500원으로, 지난달 50,000원보다 45,500원 줄었습니다.
```

`get_compare_data()` — 프론트 화면용 구조화 데이터 반환
```json
{
  "period": "이번달",
  "compare_period": "지난달",
  "category": "생활비",
  "period_amount": 4500,
  "compare_amount": 50000,
  "diff": -45500
}
```

### 2-4. 백엔드 — API (`router.py`)

```
GET /api/asset/compare
  ?period=이번달
  &compare_period=지난달
  &category=생활비   (선택)
Authorization: Bearer {token}
```

### 2-5. 프론트 — 서비스 (`assetService.ts`)

```typescript
fetchExpenseCompare(period, comparePeriod, category?)
  → CompareResult { period_amount, compare_amount, diff, ... }
```

### 2-6. 프론트 — 비교 화면 (`app/asset/compare.tsx`)

음성 명령 → `navigate_to: "asset/compare"` → 화면 이동

화면 구성:
```
[← 뒤로]       [기간 비교]

[TTS 버블] 탭하면 다시 듣기
"이번달 생활비 vs 지난달"

[이번달]   vs   [지난달]
 4,500원        50,000원

[생활비]
▼ 45,500원 감소
```

- 음성 명령 재진입 시 같은 화면에서 데이터 갱신 (리마운트 없음)
- TTS 버블 탭하면 결과 다시 읽어줌

---

## 3. Dev-A(남길)에게 전달 사항

`ROUTING_CONSTANTS.py`의 `ASSET_NAVIGATE_VALUES`에 `"asset/compare"` 추가 필요

**이유:** `compare` 기능 추가로 전용 화면(`frontend/app/asset/compare.tsx`)이 생겼고, 해당 값이 없으면 navigate_to 계약 검증에서 `"asset"`으로 폴백되어 화면 이동이 안 됨

```python
# ROUTING_CONSTANTS.py — ASSET_NAVIGATE_VALUES에 추가
ASSET_NAVIGATE_VALUES: frozenset[str | None] = frozenset({
    "asset", "asset/history", "asset/compare",  # ← 추가
    "balance", "report", None,
})
```

---

## 4. 수정 파일 목록 (Dev-C 범위)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/features/asset/service.py` | `get_compare_data()` 추가, 기간 범위 파싱 개선 |
| `backend/app/features/asset/router.py` | `GET /api/asset/compare` 엔드포인트 추가 |
| `backend/app/shared/agent/subgraphs/asset.py` | compare action 추가, 멀티턴 버그 수정, LLM 프롬프트 개선 |
| `frontend/services/assetService.ts` | `fetchExpenseCompare`, `CompareResult` 타입 추가 |
| `frontend/app/asset/compare.tsx` | 기간 비교 화면 신규 생성 |
| `frontend/hooks/useVoiceInput.ts` | 마이크 버그 수정 방법 주석 추가 (코드 수정 X) |

---

## 5. 동작 확인 로그

```
[INFO] supervisor_node: domain=asset, text='이번달 생활비 지난달이랑 비교해줘'
[INFO] collected_slots: {'action': 'compare', 'period': '이번달', 'compare_period': '지난달', 'category': '생활비'}
[INFO] navigate_to: 'asset/compare'
GET /api/asset/compare?period=이번달&compare_period=지난달&category=생활비 → 200 OK
TTS: "이번달 생활비 지출은 4,500원으로, 지난달 50,000원보다 45,500원 줄었습니다."
```
