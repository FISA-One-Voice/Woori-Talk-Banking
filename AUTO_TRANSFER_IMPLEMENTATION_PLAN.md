# Auto Transfer Implementation Plan — Issue #XX

## Context — 핵심 제약

- **URL**: `POST /api/auto-transfer` (RESTful, 동사 없음)
- **수취인**: 3가지 방법 (XOR — 정확히 하나만) — transfer와 동일 구조
  - `recipientId` — 등록 즐겨찾기 UUID (REGISTERED)
  - `recipientPhone` — 전화번호 (PHONE, 주계좌 자동 조회 + RegisteredRecipient 자동 생성)
  - `toAccountNumber` + `bankName` + `toName` (DIRECT, RegisteredRecipient 자동 생성)
  - PHONE/DIRECT는 `StandingOrder.recipient_id(nullable=False)` 충족을 위해 `create_recipient()` 자동 등록
- **인증**: ASV 없음 → `User.pin_hash` bcrypt 검증 + `StandingOrder.password_hash` 동의 기록
- **에러 코드**: 스타일가이드 §5.4 `AUTO_ORDER_*` 기준
- **보안 파이프라인**: 수취인 조회 → 계좌 소유권 → PIN 검증 → 약관 동의 → 실행일 계산 → 저장 (순서 변경 금지)
- **에이전트 툴만 구현**: 실제 스케줄러 실행은 범위 밖, CRUD + tool만 구현

---

## 데이터 흐름 3단계

```
[1단계 — 슬롯 추출]            [2단계 — 확인 화면]           [3단계 — 등록 완료]
 에이전트 툴                    프론트엔드 (Zustand)           백엔드 API 응답
 ──────────────                 ──────────────────            ─────────────────
parse_auto_transfer_slots  →    confirmScreen.tsx       →     POST /api/auto-transfer
"엄마한테 매월 15일 5만원"        수취인 정보 원본 노출             AutoTransferResult 반환
  ↓ match_by_name               "우리은행 홍어머니님께              next_execution_at:
  recipientId(UUID) 확정          매월 15일 오만 원 자동이체"        "2026-06-15"
  cycle='monthly'                PIN 입력 후 등록 클릭             account_masked:
  scheduledDay=15                       ↓                         "****RECV"
  amount=50000                  PIN은 폼 로컬 상태로만                   ↓
        ↓                       (Zustand 저장 안 함)           _mask_account() 적용
   Zustand store
   (클라이언트 메모리)
```

### 레이어별 책임 원칙

| 단계 | 주체 | 계좌번호 상태 | 인증 |
|------|------|-------------|------|
| 슬롯 추출 | `parse_auto_transfer_slots` tool | recipientId만 — 계좌번호 미접촉 | 없음 |
| 확인 화면 | 프론트엔드 Zustand | `resolve_by_id` 결과 원본 노출 | 없음 |
| 등록 API | `service.py` | AES-256 암호화 저장 | PIN bcrypt 검증 |
| 완료 응답 | `AutoTransferResult` | 마스킹 처리 | 완료 |

---

## 에이전트 ↔ 툴 실제 동작 흐름

### 전체 요청 흐름

```
프론트 Zustand
  transcript: "엄마한테 매월 15일 오만원 자동이체"
  current_slots: '{"cycle": "monthly"}'   ← 이전 턴에서 쌓인 슬롯
        ↓
POST /api/agent/chat
        ↓
shared/agent/router.py
  message = "[사용자ID:abc-123]\n엄마한테...\n[슬롯:{...}]"
  ↓ LangGraph ainvoke
  LLM → parse_auto_transfer_slots 선택
  파라미터 추출:
    user_id="abc-123"                      ← [사용자ID:...] 태그에서
    current_slots='{"cycle":"monthly"}'    ← [슬롯:...] 태그에서
    recipient_name="엄마"                  ← 발화에서
    amount=50000                           ← 발화에서
    scheduled_day=15                       ← 발화에서
```

### 툴 내부: 슬롯 병합 → if-else 분기

```python
# ① 기존 슬롯 복원
slots = json.loads(current_slots)  # {"cycle": "monthly"}

# ② LLM 추출 값 병합 (None이면 기존 값 유지)
if recipient_name: slots["recipientName"] = "엄마"
if amount:         slots["amount"] = 50000
if scheduled_day:  slots["scheduledDay"] = 15
# cycle은 이미 있으므로 건드리지 않음

# ③ 이름 → recipientId 변환
candidates = match_by_name(db, user_uuid, "엄마")
# 1건이면:
slots["recipientId"] = "uuid-엄마"
slots["toName"] = "홍어머니"
slots["bankName"] = "우리은행"

# ④ if-else 슬롯 완성 검사
# recipientId ✅  amount ✅  cycle ✅  scheduledDay ✅
→ _confirm("홍어머니님께 매월 15일에 오만 원을 자동이체할까요?", slots)
```

### 반환 포맷 (두 가지)

```python
# 슬롯 부족 → 재질문
{"action": "tts_reply", "tts_text": "매월 며칠에 이체할까요?", "slots": {...}}

# 슬롯 완성 → 확인 화면 이동
{"action": "navigate_confirm", "tts_text": "홍어머니님께...", "slots": {...}}
```

### 3턴 대화 예시

```
1턴: "엄마한테 자동이체 설정해줘"
     current_slots: {}
     병합 후: {recipientId: "uuid-엄마", toName: "홍어머니", bankName: "우리은행"}
     → amount 없음 → tts_reply("매번 얼마씩 이체할까요?")

2턴: "오만원"
     current_slots: {"recipientId": "uuid-엄마", ...}
     병합 후: {..., amount: 50000}
     → cycle 없음 → tts_reply("매월 특정 날짜에 보낼까요, 아니면 매주 특정 요일에 보낼까요?")

3턴: "매월 15일"
     current_slots: {"recipientId": "uuid-엄마", "amount": 50000}
     병합 후: {..., cycle: "monthly", scheduledDay: 15}
     → 모두 채워짐 → navigate_confirm("홍어머니님께 매월 15일 오만 원을 자동이체할까요?")

프론트: navigate_confirm → Zustand에 slots 저장 → 확인 화면 이동
확인 후: POST /api/auto-transfer (PIN + slots)
```

---

## Reuse Map

| 기존 파일 | 함수/클래스 | 사용 위치 |
|-----------|------------|----------|
| `features/recipients/service.py` | `resolve_by_id()` | service.py REGISTERED 모드 |
| `features/recipients/service.py` | `resolve_by_phone()` | service.py PHONE 모드 |
| `features/recipients/service.py` | `create_recipient()` | service.py PHONE/DIRECT 자동 등록 |
| `features/recipients/service.py` | `match_by_name()` | tools/auto_transfer.py 이름→ID 변환 |
| `features/recipients/schema.py` | `ResolvedRecipient` | service.py 내부 전달 타입 |
| `shared/crypto.py` | `decrypt()` | 마스킹용 복호화 |
| `core/jwt_utils.py` | `get_current_user_id` | router.py Depends |
| `shared/agent/tools/transfer.py` | `_ask()`, `_confirm()`, `_num_to_korean()` 패턴 | auto_transfer tool 동일 패턴 |
| `models/user.py` | `User.pin_hash` | PIN bcrypt 검증 |
| `models/standing_order.py` | `StandingOrder` | service.py 저장 대상 |
| `tests/conftest.py` | `db`, `client` fixture | test_auto_transfer.py 재사용 |
| `tests/test_transfer.py` | `_login`, `_auth`, `_cleanup` 패턴 | 동일 구조 |

---

## Files to Create / Modify

```
[수정] backend/app/core/exception.py
[신규] backend/app/features/auto_transfer/__init__.py
[신규] backend/app/features/auto_transfer/schema.py
[신규] backend/app/features/auto_transfer/service.py
[신규] backend/app/features/auto_transfer/router.py
[신규] backend/app/shared/agent/tools/auto_transfer.py
[수정] backend/app/shared/agent/tools/__init__.py
[수정] backend/app/main.py
[신규] backend/tests/test_auto_transfer.py
```

---

## Step-by-Step Implementation

---

### Step 1 — `core/exception.py` 수정

파일 끝 `TransferError` 다음에 추가:

```python
class AutoTransferError(AppError):
    """자동이체 처리 중 발생하는 도메인 예외.

    스타일가이드 §5.4 Standing Order 에러 코드 기준.

    code 목록:
        AUTO_ORDER_ACCOUNT_NOT_FOUND          - from_account 없음/타인 소유 (404)
        AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID - PIN 불일치 (403)
        AUTO_ORDER_TERMS_NOT_AGREED           - 약관 미동의 (400)
        AUTO_ORDER_NOT_FOUND                  - 자동이체 건 없음/타인 소유 (404)
        AUTO_ORDER_STATUS_INVALID             - 허용되지 않는 상태 전환 (400)
        INTERNAL_ERROR                        - DB 저장 실패 (500)
    """
    pass
```

---

### Step 2 — `features/auto_transfer/schema.py` (신규)

transfer/schema.py와 동일한 XOR 3-way 구조. PHONE/DIRECT는 service에서 `create_recipient()` 자동 등록.

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AutoTransferRequest(BaseModel):
    """POST /api/auto-transfer 요청 바디.

    수취인 지정 3가지 방법 (XOR — 정확히 하나만 허용):
        1. recipientId     — 등록 즐겨찾기 UUID
        2. recipientPhone  — 전화번호 (가입 사용자 주계좌로 자동 조회)
        3. toAccountNumber — 계좌번호 직접 입력 (bankName, toName 필수)

    PHONE / DIRECT 모드는 내부적으로 RegisteredRecipient를 자동 생성하여
    StandingOrder.recipient_id(nullable=False) 제약을 충족합니다.

    cycle 검증 규칙:
        cycle='monthly' → scheduledDay(1~31) 필수
        cycle='weekly'  → scheduledDow(0~6)  필수  (0=월, 6=일)
    """

    model_config = ConfigDict(populate_by_name=True)

    from_account_id: str = Field(alias="fromAccountId")
    amount: int = Field(gt=0)
    cycle: str
    scheduled_day: int | None = Field(default=None, ge=1, le=31, alias="scheduledDay")
    scheduled_dow: int | None = Field(default=None, ge=0, le=6, alias="scheduledDow")
    password: str
    terms_agreed: bool = Field(alias="termsAgreed")
    label: str | None = Field(default=None, max_length=100)

    # 수취인 지정 3가지 방법 (XOR — 정확히 하나만 허용)
    recipient_id: str | None = Field(default=None, alias="recipientId")
    recipient_phone: str | None = Field(default=None, alias="recipientPhone")
    to_account_number: str | None = Field(default=None, alias="toAccountNumber")

    # DIRECT(toAccountNumber) 모드 추가 필드
    bank_name: str | None = Field(default=None, alias="bankName")
    to_name: str | None = Field(default=None, alias="toName")

    @model_validator(mode="after")
    def validate_recipient_and_cycle(self) -> "AutoTransferRequest":
        """수취인 지정 방법(XOR)과 cycle 스케줄 필드를 검증합니다."""
        provided = [
            v for v in [self.recipient_id, self.recipient_phone, self.to_account_number]
            if v is not None
        ]
        if len(provided) != 1:
            raise ValueError(
                "recipientId, recipientPhone, toAccountNumber 중 정확히 하나만 제공해야 합니다."
            )
        if self.to_account_number is not None:
            if not self.bank_name or not self.to_name:
                raise ValueError("toAccountNumber 사용 시 bankName과 toName은 필수입니다.")

        if self.cycle == "monthly":
            if self.scheduled_day is None:
                raise ValueError("monthly 주기에는 scheduledDay(1~31)가 필요합니다.")
        elif self.cycle == "weekly":
            if self.scheduled_dow is None:
                raise ValueError("weekly 주기에는 scheduledDow(0~6)가 필요합니다.")
        else:
            raise ValueError("cycle은 'monthly' 또는 'weekly'여야 합니다.")
        return self


class AutoTransferResult(BaseModel):
    """POST /api/auto-transfer 성공 응답 data 필드."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    to_name: str | None = Field(alias="toName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")
    amount: int
    cycle: str
    scheduled_day: int | None = Field(default=None, alias="scheduledDay")
    scheduled_dow: int | None = Field(default=None, alias="scheduledDow")
    next_execution_at: str = Field(alias="nextExecutionAt")
    status: str
    label: str | None = Field(default=None)


class AutoTransferListItem(BaseModel):
    """GET /api/auto-transfer 목록 응답 항목 1건."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    to_name: str | None = Field(alias="toName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")
    amount: int
    cycle: str
    scheduled_day: int | None = Field(default=None, alias="scheduledDay")
    scheduled_dow: int | None = Field(default=None, alias="scheduledDow")
    next_execution_at: str | None = Field(default=None, alias="nextExecutionAt")
    status: str
    label: str | None = Field(default=None)
    created_at: str = Field(alias="createdAt")


class StatusUpdateRequest(BaseModel):
    """PATCH /api/auto-transfer/{orderId}/status 요청 바디.

    허용 전환: active→paused/cancelled, paused→active/cancelled, cancelled→불가
    """

    model_config = ConfigDict(populate_by_name=True)
    status: str


class StatusUpdateResult(BaseModel):
    """PATCH /api/auto-transfer/{orderId}/status 성공 응답 data 필드."""

    model_config = ConfigDict(populate_by_name=True)
    order_id: str = Field(alias="orderId")
    status: str
```

---

### Step 3 — `features/auto_transfer/service.py` (신규)

실제 파일 기준 — transfer/service.py 주석 스타일 적용, 스타일가이드 §2 80줄 제한으로 검증 헬퍼 분리.

```python
# 실제 파일 참조: backend/app/features/auto_transfer/service.py
#
# 핵심 설계 포인트:
#
# [수취인 경로 — _resolve_recipient()]
#   REGISTERED : resolve_by_id() → recipient_id 직접 사용
#   PHONE      : resolve_by_phone() → create_recipient() 자동 등록
#   DIRECT     : create_recipient() 자동 등록
#   (StandingOrder.recipient_id nullable=False 이므로 자동 등록 필수)
#
# [헬퍼 함수 분리 — 80줄 제한]
#   _resolve_recipient(db, user_uuid, data) → ResolvedRecipient
#   _verify_account(db, user_uuid, from_account_id) → Account
#   _verify_pin(user, raw_password) → None
#
# [에러 코드 — 스타일가이드 §5.4]
#   AUTO_ORDER_ACCOUNT_NOT_FOUND          (404)
#   AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID (403)
#   AUTO_ORDER_TERMS_NOT_AGREED           (400)
#   AUTO_ORDER_NOT_FOUND                  (404)
#   AUTO_ORDER_STATUS_INVALID             (400)
#   INTERNAL_ERROR                        (500)
#
# [5관문 파이프라인 — register_auto_transfer()]
#   1관문: _resolve_recipient()  — REGISTERED/PHONE/DIRECT 스위치
#   2관문: _verify_account()     — 출금 계좌 소유권
#   3관문: _verify_pin()         — PIN bcrypt
#   4관문: terms_agreed 확인
#   5관문: _calc_next_execution() + StandingOrder 저장
```

---

### Step 4 — `features/auto_transfer/router.py` (신규)

```python
from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.auto_transfer import service
from app.features.auto_transfer.schema import AutoTransferRequest, StatusUpdateRequest

router = APIRouter(prefix="/api/auto-transfer", tags=["자동이체"])


@router.post("", response_model=dict)
def register(
    data: AutoTransferRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체를 등록합니다. PIN 검증 통과 후 StandingOrder 생성."""
    result = service.register_auto_transfer(db, user_id, data)
    return {"success": True, "data": result.model_dump(by_alias=True), "message": "자동이체가 등록되었습니다."}


@router.get("", response_model=dict)
def list_orders(
    status: str | None = Query(default=None, description="'active' | 'paused' | 'cancelled'"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체 목록 조회. status 파라미터로 필터링 가능."""
    items = service.list_auto_transfers(db, user_id, status)
    return {"success": True, "data": [i.model_dump(by_alias=True) for i in items], "message": "자동이체 목록을 조회했습니다."}


@router.patch("/{order_id}/status", response_model=dict)
def update_status(
    order_id: str = Path(...),
    body: StatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체 상태 변경 (일시정지 / 재개 / 해지). cancelled는 복구 불가."""
    result = service.update_status(db, user_id, order_id, body)
    return {"success": True, "data": result.model_dump(by_alias=True), "message": "자동이체 상태가 변경되었습니다."}
```

---

### Step 5 — `shared/agent/tools/auto_transfer.py` (신규)

```python
"""자동이체 슬롯 파싱 agent tool.

[슬롯 완성 조건]
recipientId(match_by_name 확정) + amount + cycle
  + scheduledDay(monthly) or scheduledDow(weekly)
→ navigate_confirm

[에이전트 역할]
모호한 발화를 확정된 슬롯으로 변환하는 UX 레이어.
실제 StandingOrder 생성은 사용자 PIN 입력 후 POST /api/auto-transfer가 담당.
"""

import json
import uuid

from langchain_core.tools import tool

from app.core.database import SessionLocal
from app.features.recipients.service import match_by_name


@tool
def parse_auto_transfer_slots(
    user_id: str,
    current_slots: str = "{}",
    recipient_name: str | None = None,
    amount: int | None = None,
    cycle: str | None = None,
    scheduled_day: int | None = None,
    scheduled_dow: int | None = None,
) -> str:
    """자동이체 관련 발화에서 수취인·금액·주기·날짜 슬롯을 파싱합니다.

    다음 유형의 발화 시 호출합니다:
    - '엄마한테 매월 15일에 오만원 자동이체 등록해줘'
    - '아들한테 매주 월요일 삼만원씩 자동이체'
    - '자동이체 설정해줘'

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        current_slots: 프론트 Zustand가 전달한 현재 슬롯 JSON 문자열.
        recipient_name: 발화에서 추출한 수취인 이름/별명 (즐겨찾기 검색용).
        amount: 발화에서 추출한 금액 (원 단위 정수).
        cycle: 'monthly' 또는 'weekly'.
        scheduled_day: 월 기준 날짜 (1~31, monthly 전용).
        scheduled_dow: 요일 (0=월~6=일, weekly 전용).

    Returns:
        JSON string:
          {"action": "tts_reply",        "tts_text": "...", "slots": {...}}
          {"action": "navigate_confirm", "tts_text": "...", "slots": {...}}
    """
    # ── 기존 슬롯 복원 + 신규 값 병합 ────────────────────────────────────────
    try:
        slots: dict = json.loads(current_slots) if current_slots else {}
    except (json.JSONDecodeError, TypeError):
        slots = {}

    if recipient_name is not None:
        slots["recipientName"] = recipient_name
    if amount is not None:
        slots["amount"] = amount
    if cycle is not None:
        slots["cycle"] = cycle
    if scheduled_day is not None:
        slots["scheduledDay"] = scheduled_day
    if scheduled_dow is not None:
        slots["scheduledDow"] = scheduled_dow

    # ── 이름 → recipientId 변환 (transfer tool과 동일 패턴) ──────────────────
    if slots.get("recipientName") and not slots.get("recipientId"):
        name = slots["recipientName"]
        db = SessionLocal()
        try:
            candidates = match_by_name(db, uuid.UUID(user_id), name)
        finally:
            db.close()

        if len(candidates) == 0:
            slots.pop("recipientName", None)
            return _ask(
                f"등록된 즐겨찾기에서 {name}님을 찾을 수 없습니다. "
                "자동이체는 즐겨찾기에 등록된 분만 가능합니다. 다른 이름을 말씀해 주세요.",
                slots,
            )
        if len(candidates) == 1:
            c = candidates[0]
            slots["recipientId"] = str(c.recipient_id)
            slots["toName"] = c.recipient_name
            slots["bankName"] = c.bank_name
            slots.pop("recipientName", None)
        else:
            candidate_list = ", ".join(f"{c.alias}({c.bank_name})" for c in candidates)
            return _ask(
                f"{name}님이 여러 명 등록되어 있습니다. "
                f"{candidate_list} 중 누구에게 설정할까요?",
                slots,
            )

    return _check_slots_and_respond(slots)


def _check_slots_and_respond(slots: dict) -> str:
    """슬롯 완성 여부를 검사해 navigate_confirm 또는 tts_reply를 결정합니다."""
    if not slots.get("recipientId"):
        return _ask("누구에게 자동이체를 설정할까요? 등록된 즐겨찾기 이름을 말씀해 주세요.", slots)

    if not slots.get("amount"):
        return _ask("매번 얼마씩 이체할까요?", slots)

    cycle = slots.get("cycle")
    if not cycle:
        return _ask("매월 특정 날짜에 보낼까요, 아니면 매주 특정 요일에 보낼까요?", slots)

    if cycle == "monthly":
        if not slots.get("scheduledDay"):
            return _ask("매월 며칠에 이체할까요? 1일부터 31일 중 말씀해 주세요.", slots)
        to_name = slots.get("toName", "등록된 수취인")
        day = slots["scheduledDay"]
        return _confirm(
            f"{to_name}님께 매월 {day}일에 {_num_to_korean(slots['amount'])}을 자동이체할까요?",
            slots,
        )

    if cycle == "weekly":
        if slots.get("scheduledDow") is None:
            return _ask("매주 무슨 요일에 이체할까요?", slots)
        dow_label = ["월", "화", "수", "목", "금", "토", "일"][slots["scheduledDow"]]
        to_name = slots.get("toName", "등록된 수취인")
        return _confirm(
            f"{to_name}님께 매주 {dow_label}요일에 {_num_to_korean(slots['amount'])}을 자동이체할까요?",
            slots,
        )

    return _ask("주기를 다시 말씀해 주세요. 매월 또는 매주로 말씀해 주세요.", slots)


def _ask(tts_text: str, slots: dict) -> str:
    return json.dumps({"action": "tts_reply", "tts_text": tts_text, "slots": slots}, ensure_ascii=False)


def _confirm(tts_text: str, slots: dict) -> str:
    return json.dumps({"action": "navigate_confirm", "tts_text": tts_text, "slots": slots}, ensure_ascii=False)


def _num_to_korean(amount: int) -> str:
    units = [("조", 10**12), ("억", 10**8), ("만", 10**4), ("천", 10**3), ("백", 10**2), ("십", 10)]
    digits = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
    result, remaining = "", amount
    for unit_name, unit_val in units:
        if remaining >= unit_val:
            q = remaining // unit_val
            prefix = digits[q] if q != 1 or unit_val >= 10**4 else ""
            result += f"{prefix}{unit_name}"
            remaining %= unit_val
    return f"{result} 원" if result else f"{amount} 원"
```

---

### Step 6 — `shared/agent/tools/__init__.py` 수정

```python
from app.shared.agent.tools.auto_transfer import parse_auto_transfer_slots
from app.shared.agent.tools.transfer import parse_transfer_slots

ALL_TOOLS: list = [parse_transfer_slots, parse_auto_transfer_slots]
```

---

### Step 7 — `main.py` 수정

`transfer_router` 등록 다음 줄에 추가:

```python
from app.features.auto_transfer.router import router as auto_transfer_router

app.include_router(auto_transfer_router)
```

---

### Step 8 — `tests/test_auto_transfer.py` (신규)

```python
"""자동이체 기능 통합 테스트.

실행:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_auto_transfer.py -v

전제 조건:
    - .env POSTGRES_* 설정 (Aiven)
    - CRYPTO_NOOP=true: encrypt/decrypt 평문 패스스루
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.standing_order import StandingOrder
from app.models.transaction import Transaction
from app.models.user import User
from app.shared.crypto import encrypt

_TEST_PIN = "000001"
_TEST_PIN_HASH = bcrypt.hashpw(_TEST_PIN.encode(), bcrypt.gensalt()).decode()


def _random_phone() -> str:
    return f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, phone: str) -> str:
    res = client.post("/api/users/login", json={"phone": phone, "pin": _TEST_PIN})
    assert res.status_code == 200, f"로그인 실패: {res.json()}"
    return res.json()["data"]["accessToken"]


def _cleanup(user_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        db.query(StandingOrder).filter(
            StandingOrder.user_id == user_id
        ).delete(synchronize_session=False)
        db.query(Transaction).filter(
            Transaction.user_id == user_id
        ).delete(synchronize_session=False)
        db.query(RegisteredRecipient).filter(
            RegisteredRecipient.user_id == user_id
        ).delete(synchronize_session=False)
        db.query(Account).filter(
            Account.user_id == user_id
        ).delete(synchronize_session=False)
        db.query(User).filter(
            User.user_id == user_id
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _base_payload(from_account_id: str, recipient_id: str, **kwargs) -> dict:
    return {
        "fromAccountId": str(from_account_id),
        "recipientId": str(recipient_id),
        "amount": 50_000,
        "cycle": "monthly",
        "scheduledDay": 15,
        "password": _TEST_PIN,
        "termsAgreed": True,
        **kwargs,
    }


@pytest.fixture(scope="module")
def user_with_account(db: Session):
    user = User(
        name="자동이체 테스터", phone=_random_phone(),
        pin_hash=_TEST_PIN_HASH, embedding_vector=None,
    )
    db.add(user)
    db.flush()
    account = Account(
        user_id=user.user_id, bank_name="우리은행",
        account_number=encrypt("1002-AUTO-0001"),
        account_type="입출금", balance=1_000_000, is_primary=True,
    )
    db.add(account)
    db.commit()
    db.refresh(user)
    db.refresh(account)
    yield user, account
    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def registered_recipient(db: Session, user_with_account):
    user, _ = user_with_account
    r = RegisteredRecipient(
        user_id=user.user_id, alias="엄마",
        bank_name="신한은행", account_number=encrypt("110-AUTO-RECV"),
        recipient_name="김어머니",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    yield r


@pytest.fixture(scope="module")
def token(client: TestClient, user_with_account):
    user, _ = user_with_account
    return _login(client, user.phone)


class TestRegister:
    def test_monthly_success(self, client, token, user_with_account, registered_recipient, db):
        """monthly 등록 성공 + DB StandingOrder 생성 확인."""
        _, account = user_with_account
        payload = _base_payload(account.account_id, registered_recipient.recipient_id)
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        data = res.json()["data"]
        order = db.query(StandingOrder).filter(
            StandingOrder.order_id == data["orderId"]
        ).first()
        assert order is not None
        assert order.status == "active"
        assert order.cycle == "monthly"
        assert order.scheduled_day == 15

    def test_weekly_success(self, client, token, user_with_account, registered_recipient):
        """weekly 등록 성공."""
        _, account = user_with_account
        payload = _base_payload(
            account.account_id, registered_recipient.recipient_id,
            cycle="weekly", scheduledDow=0,
        )
        del payload["scheduledDay"]
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["cycle"] == "weekly"
        assert data["scheduledDow"] == 0

    def test_response_fields(self, client, token, user_with_account, registered_recipient):
        """응답 필드 구조 + accountMasked 마스킹 검증."""
        _, account = user_with_account
        payload = _base_payload(account.account_id, registered_recipient.recipient_id)
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 200
        data = res.json()["data"]
        for field in ("orderId", "toName", "bankName", "accountMasked", "amount", "cycle", "nextExecutionAt", "status"):
            assert field in data, f"{field} 필드 누락"
        assert "*" in data["accountMasked"]
        assert data["status"] == "active"

    def test_wrong_pin_returns_403(self, client, token, user_with_account, registered_recipient):
        """PIN 불일치 → INVALID_PIN 403."""
        _, account = user_with_account
        payload = _base_payload(account.account_id, registered_recipient.recipient_id, password="999999")
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 403
        assert res.json()["code"] == "INVALID_PIN"

    def test_terms_not_agreed_returns_400(self, client, token, user_with_account, registered_recipient):
        """약관 미동의 → TERMS_NOT_AGREED 400."""
        _, account = user_with_account
        payload = _base_payload(account.account_id, registered_recipient.recipient_id, termsAgreed=False)
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 400
        assert res.json()["code"] == "TERMS_NOT_AGREED"

    def test_monthly_missing_scheduled_day_returns_422(self, client, token, user_with_account, registered_recipient):
        """monthly + scheduledDay 누락 → 422."""
        _, account = user_with_account
        payload = _base_payload(account.account_id, registered_recipient.recipient_id)
        del payload["scheduledDay"]
        res = client.post("/api/auto-transfer", json=payload, headers=_auth(token))
        assert res.status_code == 422


class TestList:
    def test_list_returns_items(self, client, token):
        """목록 조회 성공."""
        res = client.get("/api/auto-transfer", headers=_auth(token))
        assert res.status_code == 200
        assert isinstance(res.json()["data"], list)

    def test_filter_by_status(self, client, token):
        """status=active 필터 정상 동작."""
        res = client.get("/api/auto-transfer", params={"status": "active"}, headers=_auth(token))
        assert res.status_code == 200
        for item in res.json()["data"]:
            assert item["status"] == "active"


class TestStatusUpdate:
    def test_pause_and_resume(self, client, token, user_with_account, registered_recipient):
        """active → paused → active 전환 성공."""
        _, account = user_with_account
        reg = client.post(
            "/api/auto-transfer",
            json=_base_payload(account.account_id, registered_recipient.recipient_id),
            headers=_auth(token),
        )
        order_id = reg.json()["data"]["orderId"]

        res = client.patch(f"/api/auto-transfer/{order_id}/status", json={"status": "paused"}, headers=_auth(token))
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "paused"

        res = client.patch(f"/api/auto-transfer/{order_id}/status", json={"status": "active"}, headers=_auth(token))
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "active"

    def test_cancel_is_irreversible(self, client, token, user_with_account, registered_recipient):
        """cancelled → active 시도 → INVALID_STATUS_TRANSITION 400."""
        _, account = user_with_account
        reg = client.post(
            "/api/auto-transfer",
            json=_base_payload(account.account_id, registered_recipient.recipient_id),
            headers=_auth(token),
        )
        order_id = reg.json()["data"]["orderId"]
        client.patch(f"/api/auto-transfer/{order_id}/status", json={"status": "cancelled"}, headers=_auth(token))
        res = client.patch(f"/api/auto-transfer/{order_id}/status", json={"status": "active"}, headers=_auth(token))
        assert res.status_code == 400
        assert res.json()["code"] == "INVALID_STATUS_TRANSITION"

    def test_not_found_returns_404(self, client, token):
        """없는 orderId → AUTO_TRANSFER_NOT_FOUND 404."""
        res = client.patch(
            f"/api/auto-transfer/{uuid.uuid4()}/status",
            json={"status": "paused"},
            headers=_auth(token),
        )
        assert res.status_code == 404
        assert res.json()["code"] == "AUTO_TRANSFER_NOT_FOUND"

    def test_no_token_returns_401(self, client):
        """Authorization 없음 → 401."""
        res = client.patch(f"/api/auto-transfer/{uuid.uuid4()}/status", json={"status": "paused"})
        assert res.status_code == 401
```

---

## Verification

```bash
cd backend
CRYPTO_NOOP=true pytest tests/test_auto_transfer.py -v

# 전체 회귀
CRYPTO_NOOP=true pytest tests/ -v

# Swagger 확인
uvicorn app.main:app --reload
# http://localhost:8000/docs → POST /api/auto-transfer
```

**이슈 완료 조건 체크리스트**

| 조건 | 대응 코드 |
|------|----------|
| monthly/weekly 등록 성공 | `TestRegister::test_monthly/weekly_success` |
| PIN 불일치 차단 | `TestRegister::test_wrong_pin_returns_403` |
| 약관 미동의 차단 | `TestRegister::test_terms_not_agreed_returns_400` |
| accountMasked 마스킹 검증 | `TestRegister::test_response_fields` |
| 목록 조회 + status 필터 | `TestList` |
| pause/resume/cancel 전환 | `TestStatusUpdate::test_pause_and_resume` |
| cancelled 복구 불가 | `TestStatusUpdate::test_cancel_is_irreversible` |
| 에이전트 슬롯 분기 (tool) | `parse_auto_transfer_slots` if-else 분기 |
| Agent tool 등록 | `tools/__init__.py` ALL_TOOLS |
| main.py router 등록 | Step 7 |
