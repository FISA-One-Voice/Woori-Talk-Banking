# `subgraphs/transfer.py` 도메인 로직 서비스 레이어 추출

## Context

`subgraphs/transfer.py`(800+ 줄)가 과도하게 비대한 이유는 노드 로직과 무관한 도메인 헬퍼 함수들이 파일 내에 직접 정의되어 있기 때문이다.  
더 큰 문제는 `graph.py`에도 동일한 함수들이 중복 정의되어 있다는 것 — 두 파일 모두에서 유지보수해야 하는 상황이다.

이번 작업은 이 함수들을 책임에 맞는 서비스 레이어로 이동하고, 두 파일 모두의 중복을 제거한다.  
결과물: 각 파일은 자신의 노드/그래프 조립 로직만 담고, 도메인 로직은 서비스 레이어에서 단위 테스트 가능해진다.

---

## 변경 파일 목록

| 파일 | 변경 종류 |
|---|---|
| `backend/app/shared/agent/slot_schema.py` | 슬롯 유효성 검사·정규화·파싱 함수 추가 |
| `backend/app/features/transfer/service.py` | TTS 확인 메시지 포맷 함수 추가 |
| `backend/app/features/recipients/service.py` | 슬롯 enrichment 함수 추가 |
| `backend/app/shared/agent/subgraphs/transfer.py` | 로컬 정의 12개 제거 + import 교체 |

> **`graph.py`와 `test_confirm_yes_no_tts.py`는 이번 PR 범위에서 제외한다.**  
> `multi-agent-architecture.md` §"graph.py 이전 브랜치 전략": Dev-B가 먼저 graph.py 노드를 추출해야 Dev-A가 build_supervisor()로 교체 가능. Dev-A가 먼저 수정하면 Dev-B의 추출 기준이 어긋나 충돌 발생.  
> `graph.py`의 로컬 복사본은 그대로 유지하고, Dev-B PR 머지 후 별도 PR에서 import 교체.

---

## 삭제 대상 — Dead Code

`_all_slots_filled()` — `transfer.py:145`, `graph.py:125` 양쪽 모두 never called. 그냥 삭제.

---

## Step 1 — `slot_schema.py`에 슬롯 로직 이동

파일 끝 `transfer_missing_slots()` 정의 **아래**에 두 섹션을 추가한다.

### 추가 내용 (파일 끝에 이어서)

```python
# ── 슬롯 유효성 검사 ─────────────────────────────────────────────────────────────

def valid_scheduled_day(value: object, cycle: object) -> bool:
    """자동이체 주기에 맞는 scheduled_day 값인지 확인한다."""
    if value is None or cycle is None:
        return False
    try:
        day = int(value)
    except (TypeError, ValueError):
        return False
    if cycle == "monthly":
        return 1 <= day <= 31
    if cycle == "weekly":
        return 0 <= day <= 6
    return False


def missing_slots(pending_action: str, collected_slots: dict) -> list[str]:
    """pending_action에 따라 수집되지 않은 슬롯 이름 목록을 반환한다."""
    if pending_action == "transfer":
        return transfer_missing_slots(collected_slots)
    required = SLOT_SCHEMA.get(pending_action, [])
    result: list[str] = []
    for slot_name in required:
        value = collected_slots.get(slot_name)
        if slot_name == "scheduled_day":
            if not valid_scheduled_day(value, collected_slots.get("cycle")):
                result.append(slot_name)
        elif not value:
            result.append(slot_name)
    return result


# ── STT·한국어 금액·요일 파싱 ────────────────────────────────────────────────────

KOR_DOW_MAP: dict[str, int] = {
    "월": 0, "월요일": 0,
    "화": 1, "화요일": 1,
    "수": 2, "수요일": 2,
    "목": 3, "목요일": 3,
    "금": 4, "금요일": 4,
    "토": 5, "토요일": 5,
    "일": 6, "일요일": 6,
}

STT_AMOUNT_ALIASES: dict[str, int] = {
    "전원": 1000,
    "천원": 1000,
    "천": 1000,
    "만원": 10000,
    "만": 10000,
}


def _kor_to_int(text: str) -> int | None:
    """순수 한국어 숫자 문자열을 정수로 변환한다."""
    _DIGIT = {
        "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
        "육": 6, "칠": 7, "팔": 8, "구": 9,
    }
    _SMALL = {"십": 10, "백": 100, "천": 1000}

    def _below_10000(s: str) -> int:
        result, current = 0, 0
        for ch in s:
            if ch in _DIGIT:
                current = _DIGIT[ch]
            elif ch in _SMALL:
                result += (current or 1) * _SMALL[ch]
                current = 0
        return result + current

    total = 0
    if "억" in text:
        parts = text.split("억", 1)
        total += (_below_10000(parts[0]) or 1) * 100_000_000
        text = parts[1]
    if "만" in text:
        parts = text.split("만", 1)
        total += (_below_10000(parts[0]) or 1) * 10_000
        text = parts[1]
    total += _below_10000(text)
    return total if total > 0 else None


def parse_korean_amount(raw: str) -> str | None:
    """한국어·STT 오인식 금액 표현을 정수 문자열로 변환한다."""
    import re as _re
    text = str(raw).strip().replace(" ", "").replace(",", "")
    if not text:
        return None
    if text in STT_AMOUNT_ALIASES:
        return str(STT_AMOUNT_ALIASES[text])
    text_no_won = _re.sub(r"원$", "", text)
    try:
        val = int(text_no_won)
        return str(val) if val > 0 else None
    except ValueError:
        pass
    val = _kor_to_int(text_no_won)
    return str(val) if val is not None and val > 0 else None


def normalize_scheduled_day(slots: dict, extracted_slots: dict) -> dict:
    """STT 오류 보정 및 한글 요일명 → 정수 변환."""
    normalized = dict(slots)
    for key, value in extracted_slots.items():
        if key == "scheduled_day" and value is not None:
            kor_key = str(value).replace(" ", "")
            if kor_key in KOR_DOW_MAP:
                value = KOR_DOW_MAP[kor_key]
            else:
                try:
                    day_int = int(value)
                except (TypeError, ValueError):
                    day_int = None
                if day_int is not None and 32 <= day_int <= 91 and day_int % 10 == 1:
                    value = day_int // 10
        normalized[key] = value
    return normalized
```

> `parse_korean_amount`의 `import re as _re`는 함수 내부 lazy import (파일 상단에 `import re` 추가해도 무방).  
> `slot_schema.py`는 현재 `classify_recipient_input`만 외부 import하며, 새 함수들은 추가 의존성 없음 — 순환 위험 없음.

---

## Step 2 — `features/transfer/service.py`에 TTS 포맷 함수 추가

파일 끝에 `# ── TTS 포맷` 섹션을 추가한다.

```python
# ── TTS 포맷 ────────────────────────────────────────────────────────────────────

from app.shared.agent.slot_schema import (
    ACTION_LABELS,
    ACTIONS_WITH_YES_NO_CONFIRM,
    CONFIRM_YES_NO_SUFFIX,
)


def amount_to_korean(amount: int) -> str:
    """금액을 TTS 친화적 한국어 표현으로 변환한다."""
    if amount <= 0:
        return "영 원"
    units = [
        (100_000_000, "억"),
        (10_000, "만"),
        (1_000, "천"),
        (100, "백"),
        (10, "십"),
    ]
    parts: list[str] = []
    remaining = amount
    for unit_val, unit_name in units:
        if remaining >= unit_val:
            count = remaining // unit_val
            remaining %= unit_val
            parts.append(f"{count}{unit_name}")
    if remaining > 0:
        parts.append(str(remaining))
    return "".join(parts) + " 원"


def format_cycle_parts(cycle: object, scheduled_day: object) -> list[str]:
    """자동이체 주기 슬롯을 확인 메시지 조각으로 변환한다."""
    dow_labels = ["월", "화", "수", "목", "금", "토", "일"]
    parts: list[str] = []
    if cycle == "monthly":
        parts.append("매월")
        if scheduled_day is not None:
            parts.append(f"{scheduled_day}일")
    elif cycle == "weekly":
        parts.append("매주")
        if scheduled_day is not None:
            try:
                parts.append(f"{dow_labels[int(scheduled_day)]}요일")
            except (IndexError, ValueError):
                parts.append(f"{scheduled_day}요일")
    return parts


def format_confirm_message(pending_action: str, collected_slots: dict) -> str:
    """수집된 슬롯을 기반으로 TTS 친화적 확인 메시지를 생성한다."""
    action_label = ACTION_LABELS.get(pending_action, pending_action)
    parts: list[str] = []

    recipient = collected_slots.get("recipient")
    bank_name = collected_slots.get("bank_name")
    account_number = collected_slots.get("account_number")
    amount = collected_slots.get("amount")
    cycle = collected_slots.get("cycle")
    scheduled_day = collected_slots.get("scheduled_day")

    if bank_name and account_number:
        masked = _mask_account(str(account_number))
        target = f"{recipient}님 " if recipient else ""
        parts.append(f"{target}{bank_name} 계좌 {masked}로")
    elif recipient:
        parts.append(f"{recipient}에게")

    parts.extend(format_cycle_parts(cycle, scheduled_day))
    if amount:
        try:
            parts.append(amount_to_korean(int(amount)))
        except (TypeError, ValueError):
            parts.append(str(amount))

    message = f"{' '.join(parts)} {action_label}할까요?"
    if pending_action in ACTIONS_WITH_YES_NO_CONFIRM:
        message += CONFIRM_YES_NO_SUFFIX
    return message
```

**순환 의존성 확인:**  
`transfer/service.py → slot_schema → recipients.service.classify_recipient_input`  
`recipients.service`는 `transfer/service.py`를 import하지 않음 → 순환 없음 ✅

---

## Step 3 — `features/recipients/service.py`에 enrich 함수 추가

파일 끝에 추가. `classify_recipient_input`, `match_by_registered_account`, `get_db`, `uuid`가 모두 이 파일에 이미 있으므로 신규 import 불필요.

```python
def enrich_slots_from_resolved(
    slots: dict,
    resolved: ResolvedRecipient,
    recipient_input: str,
    user_id: str,
) -> dict:
    """resolve 결과를 collected_slots에 반영한다."""
    display = resolved.recipient_name or "수취인"
    if resolved.recipient_id and classify_recipient_input(recipient_input) == "account":
        db = next(get_db())
        try:
            row = match_by_registered_account(db, uuid.UUID(user_id), recipient_input)
            if row and row.alias:
                display = row.alias
        finally:
            db.close()

    slots["recipient"] = display
    slots["bank_name"] = resolved.bank_name
    slots["account_number"] = resolved.account_number
    if resolved.recipient_id:
        slots["recipient_id"] = str(resolved.recipient_id)
    return slots
```

> 기존 `transfer.py`의 `_enrich_slots_from_resolved`는 `get_db`를 lazy import(`from app.core.database import get_db`)했지만, `recipients/service.py`는 파일 상단에 이미 `from app.core.database import get_db`가 있으므로 제거.

---

## Step 4 — `subgraphs/transfer.py` 정리

### 4-a. 제거할 로컬 정의 (현재 줄 번호)

| 제거 대상 | 현재 위치 |
|---|---|
| `_all_slots_filled()` | L145–147 |
| `_missing_slots()` | L150–164 |
| `_valid_scheduled_day()` | L167–179 |
| `_enrich_slots_from_resolved()` | L182–206 |
| `_format_confirm_message()` | L209–238 |
| `_format_cycle_parts()` | L241–256 |
| `_amount_to_korean()` | L259–279 |
| `_KOR_DOW_MAP` | L373–381 |
| `_STT_AMOUNT_ALIASES` | L384–390 |
| `_kor_to_int()` | L393–421 |
| `_parse_korean_amount()` | L424–451 |
| `_normalize_scheduled_day()` | L454–470 |

### 4-b. import 섹션 변경

**제거:**
```python
from app.features.transfer.service import _mask_account
```

**기존 `slot_schema` import 블록에 추가:**
```python
from app.shared.agent.slot_schema import (
    ...기존 imports...,
    missing_slots,
    normalize_scheduled_day,
    parse_korean_amount,
)
```

**기존 `recipients.service` import 블록에 추가:**
```python
from app.features.recipients.service import (
    ...기존 imports...,
    enrich_slots_from_resolved,
)
```

**신규 추가:**
```python
from app.features.transfer.service import format_confirm_message
```

### 4-c. 호출 지점 rename (find & replace)

| 기존 | 변경 |
|---|---|
| `_missing_slots(` | `missing_slots(` |
| `_enrich_slots_from_resolved(` | `enrich_slots_from_resolved(` |
| `_format_confirm_message(` | `format_confirm_message(` |
| `_normalize_scheduled_day(` | `normalize_scheduled_day(` |
| `_parse_korean_amount(` | `parse_korean_amount(` |

---

## Step 5 — `graph.py` / `test_confirm_yes_no_tts.py` (이번 PR 제외)

`graph.py`는 Dev-B가 병렬로 작업 중이므로 이번 PR에서 건드리지 않는다.  
`graph.py`의 로컬 `_format_confirm_message`, `_amount_to_korean`, `_missing_slots` 등은 그대로 유지.  
`test_confirm_yes_no_tts.py`도 변경 없음.

Dev-B 작업 완료 후 별도 PR에서 `graph.py`에 동일한 import 교체를 적용한다.

---

## 순환 의존성 최종 확인

```
slot_schema.py
  └─ recipients.service (classify_recipient_input)          ← 기존

features/recipients/service.py
  └─ (신규 외부 import 없음)

features/transfer/service.py
  └─ slot_schema (ACTION_LABELS, ACTIONS_WITH_YES_NO_CONFIRM, CONFIRM_YES_NO_SUFFIX)  ← 신규

subgraphs/transfer.py
  └─ slot_schema (missing_slots, normalize_scheduled_day, parse_korean_amount, ...)
  └─ transfer.service (format_confirm_message)
  └─ recipients.service (enrich_slots_from_resolved, ...)

graph.py
  └─ 변경 없음 (이번 PR 제외)
```

`transfer/service.py → slot_schema → recipients.service` 방향.  
`recipients.service`는 `transfer/service.py`를 import하지 않음 → 순환 없음 ✅

---

## 검증

```bash
cd backend

# 1. AST 문법 체크 (venv 없이도 가능)
python3.11 -c "
import ast, pathlib
errors = []
for p in pathlib.Path('app').rglob('*.py'):
    try:
        ast.parse(p.read_text())
    except SyntaxError as e:
        errors.append(f'{p}: {e}')
print('\n'.join(errors) or 'OK')
"

# 2. 단위 테스트 (이동된 함수 직접 검증)
pytest tests/test_confirm_yes_no_tts.py tests/test_transfer_missing_slots.py -v

# 3. 서브그래프 통합 테스트
pytest tests/test_transfer_subgraph.py tests/test_transfer_tools.py -v
```

체크리스트:
1. `subgraphs/transfer.py`에 로컬 `_missing_slots`, `_format_confirm_message` 등 정의 없음
2. `slot_schema.py`에 `missing_slots`, `parse_korean_amount`, `normalize_scheduled_day` 존재
3. `transfer/service.py`에 `format_confirm_message`, `amount_to_korean` 존재
4. `recipients/service.py`에 `enrich_slots_from_resolved` 존재
5. AST 체크 및 모든 pytest 통과
