# Transfer Feature Implementation Plan — Issue #22

## Context

Issue #22는 `features/transfer/` 전체와 `shared/agent/tools/transfer.py`를 새로 구현하는 작업이다.

핵심 제약:
- **URL**: `POST /api/transfer` (`@router.post("")`, 동사 없음 RESTful)
- **Schema XOR 검증**: `@model_validator(mode="after")` — recipientId/recipientPhone/toAccountNumber 중 정확히 하나만 허용
- **One-Step 보안**: ASV 검증 → 멱등성 → 잔액 → DB (순서 변경 금지)
- **Loose Coupling**: ASV는 httpx 인터페이스만, 테스트는 mock으로 완전 분리

---

## 계좌번호 마스킹 아키텍처 (UX ↔ 보안 역할 분담)

> 고령층 사용자 인지 편의성(토스 스타일 UX) + 금융보안원·개인정보보호 규정을 동시에 만족하기 위한 레이어별 마스킹 정책.

### 데이터 흐름 3단계

```
[1단계 — 슬롯 추출]          [2단계 — 확인 화면]          [3단계 — 완료 영수증]
 에이전트 툴                  프론트엔드 (Zustand)          백엔드 API 응답
 ──────────────               ──────────────────            ─────────────────
 parse_transfer_slots()  →    confirmScreen.tsx        →    POST /api/transfer
 원본 그대로 파싱              원본 계좌번호 그대로 노출        TransferResult 반환
 recipientPhone: "010-…"      "우리은행 1002-123-456789     account_masked:
 toAccountNumber: "1002-…"     박지훈님께 5만원 이체"         "****456789"
        ↓                             ↓                            ↓
   Zustand store               사용자가 100% 확인 후         _mask_account() 적용
   (클라이언트 메모리)           음성 인증 버튼 클릭            (뒷 4자리만 노출)
```

### 레이어별 책임 원칙

| 단계 | 주체 | 계좌번호 상태 | 근거 |
|------|------|--------------|------|
| 슬롯 추출 | `parse_transfer_slots` tool | **원본 평문** | LLM 파싱 정확도 보장 |
| 확인 화면 렌더링 | 프론트엔드 Zustand | **원본 평문** | 송금 대상 오인 방지 (고령층 UX) |
| DB 저장 | `service.py` 내부 | **AES-256 암호화** | 저장 보안 |
| 완료 영수증 반환 | `TransferResult` | **마스킹 처리** | 금융보안원 규정 |

### service.py 준수 규칙

- `execute_transfer` 내부 처리 흐름 전체에서 `resolved.account_number`는 **평문 그대로** 사용
- DB 기록 시에만 `encrypt(resolved.account_number)` 적용
- `_mask_account()` 호출은 **`TransferResult` 반환 시점 단 두 곳**에서만 허용
  1. 멱등성 조기 반환 — `_mask_account(decrypt(existing_tx.to_account_number))`
  2. 정상 완료 반환 — `_mask_account(resolved.account_number)`
- 이 두 곳 외에 `_mask_account` 추가 절대 금지

---

## Reuse Map (기존 코드 재사용)

| 기존 파일 | 함수/클래스 | 사용 위치 |
|-----------|------------|----------|
| `features/recipients/service.py` | `resolve_by_id()` | transfer/service.py REGISTERED 모드 |
| `features/recipients/service.py` | `resolve_by_phone()` | transfer/service.py PHONE 모드 |
| `features/recipients/schema.py` | `ResolvedRecipient` | transfer/service.py 내부 전달 타입 |
| `shared/crypto.py` | `encrypt()` / `decrypt()` | to_account_number AES 저장/복호화 |
| `core/jwt_utils.py` | `get_current_user_id` | transfer/router.py Depends |
| `features/voice/service.py` | httpx AsyncClient 패턴 | ASV /verify 호출 구조 |
| `tests/conftest.py` | `db`, `client` fixture | test_transfer.py 그대로 재사용 |
| `tests/test_recipients_api.py` | `_login`, `_auth`, `_cleanup` 패턴 | test_transfer.py 동일 구조 |

---

## Files to Create / Modify

```
[수정] backend/app/models/transaction.py       — idempotency_key 컬럼 추가
[수정] backend/app/core/exception.py           — TransferError 클래스 추가
[신규] backend/app/features/transfer/__init__.py
[신규] backend/app/features/transfer/schema.py
[신규] backend/app/features/transfer/service.py
[신규] backend/app/features/transfer/router.py
[신규] backend/app/shared/agent/tools/transfer.py
[수정] backend/app/shared/agent/tools/__init__.py — ALL_TOOLS에 등록
[신규] backend/app/shared/agent/router.py       — Issue #7 구현
[수정] backend/app/main.py                      — 라우터 2개 등록
[신규] backend/tests/test_transfer.py
```

---

## Step-by-Step Implementation

---

### Step 1 — `models/transaction.py` 수정 + Aiven DDL

`status` 컬럼 다음 줄에 추가:

```python
idempotency_key: Mapped[str | None] = mapped_column(
    String(36),
    unique=True,
    nullable=True,
    index=True,
    comment="멱등성 보장. 동일 key 중복 요청 차단 (UUID v4)",
)
```

**Aiven pgAdmin에서 실행할 DDL:**
```sql
ALTER TABLE transactions
  ADD COLUMN idempotency_key VARCHAR(36) DEFAULT NULL;

ALTER TABLE transactions
  ADD CONSTRAINT uq_transactions_idempotency_key UNIQUE (idempotency_key);

CREATE INDEX idx_transactions_idempotency_key
  ON transactions (idempotency_key);
```

`DbTableScheme` 파일도 transactions DDL에 컬럼 추가.

---

### Step 2 — `core/exception.py` 수정

파일 끝에 추가:

```python
class TransferError(AppError):
    """이체 처리 중 발생하는 도메인 예외.

    code 목록:
        VOICE_NOT_REGISTERED       - 음성 프로필 미등록 (403)
        VOICE_VERIFICATION_FAILED  - ASV 검증 실패 (403)
        ASV_UNAVAILABLE            - ASV 서버 통신 오류 (503)
        TRANSFER_ACCOUNT_NOT_FOUND - from_account 없음/타인 소유 (404)
        INSUFFICIENT_BALANCE       - 잔액 부족 (400)
        TRANSFER_FAILED            - DB 처리 실패 (500)
    """
    pass
```

---

### Step 3 — `features/transfer/schema.py` (신규)

```python
"""이체 기능 요청/응답 Pydantic 스키마."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransferRequest(BaseModel):
    """POST /api/transfer 요청 바디.

    recipientId / recipientPhone / toAccountNumber 중 정확히 하나만 허용.
    """
    model_config = ConfigDict(populate_by_name=True)

    from_account_id: str = Field(alias="fromAccountId")
    amount: int = Field(gt=0)
    idempotency_key: str = Field(alias="idempotencyKey")

    # 수취인 지정 3가지 방법 (XOR — 정확히 하나만 허용)
    recipient_id: str | None = Field(default=None, alias="recipientId")
    recipient_phone: str | None = Field(default=None, alias="recipientPhone")
    to_account_number: str | None = Field(default=None, alias="toAccountNumber")

    # DIRECT(toAccountNumber) 모드 추가 필드
    bank_name: str | None = Field(default=None, alias="bankName")
    to_name: str | None = Field(default=None, alias="toName")

    @model_validator(mode="after")
    def validate_recipient_xor(self) -> "TransferRequest":
        """수취인 지정 방법이 정확히 하나인지 검증합니다."""
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
                raise ValueError(
                    "toAccountNumber 사용 시 bankName과 toName은 필수입니다."
                )
        return self


class TransferResult(BaseModel):
    """POST /api/transfer 성공 응답 data 필드."""
    model_config = ConfigDict(populate_by_name=True)

    tx_id: str = Field(alias="txId")
    to_name: str | None = Field(alias="toName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")
    amount: int


class PhoneLookupResult(BaseModel):
    """GET /api/transfer/lookup/phone 응답 data 필드."""
    model_config = ConfigDict(populate_by_name=True)

    recipient_name: str | None = Field(alias="recipientName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")
```

---

### Step 4 — `features/transfer/service.py` (신규)

```python
"""이체 비즈니스 로직.

외부 의존: ASV 서버(settings.ASV_SERVER_URL) — httpx 인터페이스만 정의.
실제 서버 미완성 시에도 mock으로 100% 테스트 가능.
"""

import json
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exception import TransferError
from app.features.recipients.schema import ResolvedRecipient
from app.features.recipients.service import resolve_by_id, resolve_by_phone
from app.features.transfer.schema import PhoneLookupResult, TransferRequest, TransferResult
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.shared.crypto import decrypt, encrypt


def _mask_account(account_number: str | None) -> str:
    if not account_number:
        return "****"
    if len(account_number) <= 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]


# ── GET /api/transfer/lookup/phone ────────────────────────────────────────────

def lookup_by_phone(db: Session, phone: str) -> PhoneLookupResult:
    """전화번호로 수취인 주계좌를 조회합니다.

    미가입 번호이면 RecipientError(TRANSFER_RECIPIENT_NOT_FOUND, 404)가 그대로 전파됩니다.
    프론트엔드는 404 수신 시 '직접 입력' 화면으로 전환합니다.
    """
    resolved = resolve_by_phone(db, phone)
    return PhoneLookupResult(
        recipient_name=resolved.recipient_name,
        bank_name=resolved.bank_name,
        account_masked=_mask_account(resolved.account_number),
    )


# ── POST /api/transfer ────────────────────────────────────────────────────────

async def execute_transfer(
    db: Session,
    user_id: str,
    data: TransferRequest,
    audio_bytes: bytes,
    content_type: str,
) -> TransferResult:
    """One-Step 이체 처리: ASV 검증 → 멱등성 → 수취인 조회 → 잔액 차감 → DB 기록.

    순서 변경 금지 — 보안 설계의 핵심입니다.
    """
    user_uuid = uuid.UUID(user_id)

    # ── 1. 음성 프로필 확인 ──────────────────────────────────────────────────
    user = db.query(User).filter(User.user_id == user_uuid).first()
    if user is None or user.embedding_vector is None:
        raise TransferError(
            code="VOICE_NOT_REGISTERED",
            message="음성 인증을 먼저 등록해 주세요.",
            status_code=403,
        )

    # ── 2. ASV 화자 검증 (interface-only, loose coupling) ────────────────────
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.ASV_SERVER_URL}/verify",
                files={"file": ("audio.wav", audio_bytes, content_type)},
                data={"reference_embedding": json.dumps(user.embedding_vector)},
                timeout=10.0,
            )
            resp.raise_for_status()
            verify_result = resp.json()
    except httpx.HTTPError as e:
        raise TransferError(
            code="ASV_UNAVAILABLE",
            message="음성 인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            status_code=503,
        ) from e

    if not verify_result.get("is_same_speaker", False):
        raise TransferError(
            code="VOICE_VERIFICATION_FAILED",
            message="음성 인증에 실패했습니다. 다시 시도해 주세요.",
            status_code=403,
        )

    # ── 3. 멱등성 확인 ───────────────────────────────────────────────────────
    existing_tx = (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == data.idempotency_key)
        .first()
    )
    if existing_tx is not None:
        return TransferResult(
            tx_id=existing_tx.tx_id,
            to_name=existing_tx.to_name,
            bank_name=existing_tx.to_bank_name,
            account_masked=_mask_account(decrypt(existing_tx.to_account_number)),
            amount=existing_tx.amount,
        )

    # ── 4. 수취인 조회 (XOR 분기) ────────────────────────────────────────────
    if data.recipient_id is not None:
        resolved = resolve_by_id(db, user_uuid, data.recipient_id)
    elif data.recipient_phone is not None:
        resolved = resolve_by_phone(db, data.recipient_phone)
    else:
        resolved = ResolvedRecipient(
            recipient_id=None,
            bank_name=data.bank_name,
            account_number=data.to_account_number,
            recipient_name=data.to_name,
        )

    # ── 5. 출금 계좌 확인 + 잔액 검증 ───────────────────────────────────────
    from_account = (
        db.query(Account)
        .filter(
            Account.account_id == data.from_account_id,
            Account.user_id == user_uuid,
        )
        .first()
    )
    if from_account is None:
        raise TransferError(
            code="TRANSFER_ACCOUNT_NOT_FOUND",
            message="출금 계좌를 찾을 수 없습니다.",
            status_code=404,
        )
    if from_account.balance < data.amount:
        raise TransferError(
            code="INSUFFICIENT_BALANCE",
            message="잔액이 부족합니다.",
            status_code=400,
        )

    # ── 6. 잔액 차감 + 거래 기록 생성 ───────────────────────────────────────
    from_account.balance -= data.amount

    tx = Transaction(
        user_id=user_uuid,
        from_account_id=data.from_account_id,
        recipient_id=resolved.recipient_id,
        to_bank_name=resolved.bank_name,
        to_account_number=encrypt(resolved.account_number),
        to_name=resolved.recipient_name,
        amount=data.amount,
        tx_type="transfer",
        status="completed",
        idempotency_key=data.idempotency_key,
    )
    db.add(tx)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise TransferError(
            code="TRANSFER_FAILED",
            message="이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            status_code=500,
        ) from e

    return TransferResult(
        tx_id=tx.tx_id,
        to_name=tx.to_name,
        bank_name=tx.to_bank_name,
        account_masked=_mask_account(resolved.account_number),
        amount=tx.amount,
    )
```

---

### Step 5 — `features/transfer/router.py` (신규)

```python
"""이체 API 라우터.

POST /api/transfer            — 이체 실행 (RESTful, 동사 없음)
GET  /api/transfer/lookup/phone — 전화번호 수취인 조회
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.transfer import service
from app.features.transfer.schema import TransferRequest

router = APIRouter(prefix="/api/transfer", tags=["이체"])


@router.get("/lookup/phone", response_model=dict)
def lookup_phone(
    phone: str = Query(..., description="수취인 전화번호"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """전화번호로 수취인 주계좌를 조회합니다.

    404(TRANSFER_RECIPIENT_NOT_FOUND) 수신 시 프론트엔드가 '직접 입력' 화면으로 전환합니다.
    """
    data = service.lookup_by_phone(db, phone)
    return {
        "success": True,
        "data": data.model_dump(by_alias=True),
        "message": "수취인 정보를 조회했습니다.",
    }


@router.post("", response_model=dict)
async def transfer(
    audio: UploadFile = File(..., description="ASV 검증용 음성 파일 (WAV)"),
    transfer_data: str = Form(..., description="TransferRequest JSON 문자열"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """ASV 음성 인증 후 이체를 실행합니다. (POST /api/transfer)

    multipart/form-data:
      - audio: WAV 음성 파일
      - transfer_data: TransferRequest JSON 문자열

    One-Step 처리: ASV 검증 → 멱등성 → 수취인 → 잔액 차감 → DB 기록
    """
    data = TransferRequest.model_validate_json(transfer_data)
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/wav"

    result = await service.execute_transfer(db, user_id, data, audio_bytes, content_type)
    return {
        "success": True,
        "data": result.model_dump(by_alias=True),
        "message": "이체가 완료되었습니다.",
    }
```

---

### Step 5-A — `features/transfer/schema.py` 추가 (메모·최근이체 스키마)

`schema.py` 파일 하단에 추가할 3개 클래스:

| 클래스 | 용도 |
|--------|------|
| `MemoRequest` | `POST /{txId}/memo` 요청 바디 (memo 100자 제한, category 선택) |
| `MemoResult` | 메모 저장 성공 응답 data 필드 |
| `RecentTransferItem` | `GET /recent` 응답 항목 1건 (Zustand 세팅용 원본 + 화면표시용 마스킹 동시 포함) |

**RecentTransferItem 설계 의도:**
- `toAccountNumber`: 평문 원본 — Zustand `transferStore`에 세팅해 즉시 재송금 가능하게 함
- `accountMasked`: 마스킹 버전 — 목록 화면 표시 전용
- `recipientId`: 등록 수취인이면 UUID 반환 — 재송금 시 REGISTERED 모드 우선 사용 가능

---

### Step 5-B — `features/transfer/service.py` 추가 함수

#### `save_transfer_memo(db, user_id, tx_id, memo, category)`
- `tx_id` + `user_id`로 소유권 검증 (타인 거래 접근 차단)
- `memo`, `category` 업데이트 후 커밋
- 존재하지 않는 txId → `TransferError(TRANSFER_NOT_FOUND, 404)`

#### `get_recent_transfers(db, user_id, limit=5)`
- 조건: `tx_type='transfer'`, `status='completed'`, `user_id=현재유저`
- 중복 제거 전략: `GROUP BY to_account_number` + `MAX(created_at)` 서브쿼리
  → 동일 수취 계좌 중 가장 최근 이체 1건씩만 추출
- 결과: `created_at DESC` 정렬, `limit`개 반환
- `to_account_number` → `decrypt()` → `_mask_account()` 적용 후 두 필드 동시 포함

---

### Step 5-C — `features/transfer/router.py` 추가 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/transfer/{tx_id}/memo` | 완료된 거래에 메모·카테고리 사후 저장 |
| `GET` | `/api/transfer/recent` | 최근 이체 목록 조회 (터치 송금 UX) |

**라우트 등록 순서 주의:**
`GET /recent`는 반드시 `GET /{tx_id}` 계열 경로보다 먼저 등록해야 FastAPI가 `"recent"` 문자열을 path param으로 오인하지 않음.
현재 router.py에는 GET `/{tx_id}` 계열이 없으므로 순서 충돌 없음. 향후 거래 상세 조회 추가 시 `/recent`를 반드시 위에 위치.

---

### Step 6-A — `shared/agent/tools/transfer.py` 설계 변경 이력 (3-way 슬롯 통합)

> **변경 사유**: 개발 중 발견된 UX 결함 — v1 코드는 `recipient_phone` + `amount` 2-슬롯만 처리해,
> "강호동한테 보내줘" 같은 이름 발화 시 전화번호만 계속 요구하는 문제가 있었음.

#### v1 (초기) vs v2 (현재) 비교

| 항목 | v1 (결함) | v2 (현재) |
|------|----------|----------|
| 처리 경로 수 | 1가지 (전화번호만) | 3가지 (등록/전화번호/직접입력) |
| 이름 발화 대응 | ❌ "전화번호를 말씀해 주세요" 반복 | ✅ `match_by_name` 호출 후 분기 |
| DB 세션 | ❌ 없음 | ✅ `SessionLocal()` 직접 생성 |
| 동명이인 처리 | ❌ 없음 | ✅ 후보 목록 TTS 안내 |

#### 3-way 경로 슬롯 완성 조건

```
경로 ① REGISTERED : recipientId(UUID 확정) + amount → navigate_confirm
경로 ② PHONE      : recipientPhone + amount → navigate_confirm
경로 ③ DIRECT     : toAccountNumber + bankName + toName + amount → navigate_confirm
```

#### match_by_name 0 / 1 / N건 분기 처리

| 결과 | 동작 |
|------|------|
| 0건 | `tts_reply` — 즐겨찾기 미등록 안내 + 전화번호·계좌 입력 유도 |
| 1건 | `recipientId` 슬롯에 저장, `toName`·`bankName` 보조 저장 후 계속 진행 |
| 2건 이상 | `tts_reply` — 후보 목록(`alias(bank_name)`) TTS 안내 후 재질문 |

#### transfer/ 패키지 수정 여부

`features/transfer/schema.py`, `service.py`, `router.py`는 **수정 없음**.
4관문 스위치 타워가 처음부터 3가지 확정 식별자(`recipientId` / `recipientPhone` / `toAccountNumber`)만 받도록 설계되어 있어, 어느 경로로 슬롯이 완성되든 기어가 그대로 맞물림.

---

### Step 6 — `shared/agent/tools/transfer.py` (신규)

```python
"""이체 슬롯 파싱 agent tool."""

import json

from langchain_core.tools import tool


@tool
def parse_transfer_slots(
    user_id: str,
    current_slots: str = "{}",
    recipient_phone: str | None = None,
    amount: int | None = None,
) -> str:
    """이체 관련 발화에서 수취인 전화번호와 금액 슬롯을 파싱합니다.

    '엄마한테 오만원 보내줘', '010-1234-5678로 이체해줘', '십만원 보내' 등
    이체 의도 발화 시 호출합니다.

    프론트엔드가 current_slots를 JSON 문자열로 전달합니다.
    여기서 새로 추출한 값을 기존 슬롯과 병합한 뒤 완성 여부를 판단합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID (모든 tool 공통 인증용).
        current_slots: 프론트 Zustand가 전달한 현재 슬롯 JSON 문자열.
        recipient_phone: 발화에서 LLM이 추출한 수취인 전화번호. 없으면 None.
        amount: 발화에서 LLM이 추출한 금액 (원 단위). 없으면 None.

    Returns:
        JSON string:
          {"action": "tts_reply",       "tts_text": "...", "slots": {...}}
          {"action": "navigate_confirm", "tts_text": "...", "slots": {...}}
    """
    try:
        slots: dict = json.loads(current_slots) if current_slots else {}
    except (json.JSONDecodeError, TypeError):
        slots = {}

    if recipient_phone is not None:
        slots["recipientPhone"] = recipient_phone
    if amount is not None:
        slots["amount"] = amount

    missing = []
    if not slots.get("recipientPhone"):
        missing.append("전화번호")
    if not slots.get("amount"):
        missing.append("금액")

    if missing:
        question_map = {
            "전화번호": "누구에게 보내드릴까요? 전화번호를 말씀해 주세요.",
            "금액": "얼마를 보내드릴까요?",
        }
        return json.dumps(
            {"action": "tts_reply", "tts_text": question_map[missing[0]], "slots": slots},
            ensure_ascii=False,
        )

    phone = slots["recipientPhone"]
    amount_kor = _num_to_korean(slots["amount"])
    return json.dumps(
        {
            "action": "navigate_confirm",
            "tts_text": f"{phone} 번호로 {amount_kor}을 이체할까요?",
            "slots": slots,
        },
        ensure_ascii=False,
    )


def _num_to_korean(amount: int) -> str:
    units = [("조", 10**12), ("억", 10**8), ("만", 10**4), ("천", 10**3),
             ("백", 10**2), ("십", 10)]
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

### Step 7 — `shared/agent/tools/__init__.py` 수정

```python
from app.shared.agent.tools.transfer import parse_transfer_slots

ALL_TOOLS: list = [parse_transfer_slots]
```

---

### Step 8-A — `shared/agent/router.py` 결함 발견 및 수정 이력

> **발견 시점**: router.py 초안 작성 직후 코드 교차 검증에서 발견
> **영향 범위**: `parse_transfer_slots` tool의 `user_id` 의존 경로(경로 ① REGISTERED) 전체

#### 결함 1 — `user_id` 소실로 인한 tool 오작동

| 항목 | 내용 |
|------|------|
| 원인 | `thread_id`는 LangGraph 메모리 체크포인팅 키 전용 — tool 파라미터로 자동 주입되지 않음 |
| 증상 | LLM이 `user_id` 값을 모르므로 `uuid.UUID(user_id)` 호출 시 `ValueError` crash |
| 피해 | 경로 ① (이름/별명 → `match_by_name`) **100% 오작동** |
| 수정 | HumanMessage 본문에 `[사용자ID:{user_id}]` 태그 포함 → LLM이 tool 호출 시 추출·전달 |

#### 결함 2 — 응답 raw string으로 인한 프론트 파싱 실패

| 항목 | 내용 |
|------|------|
| 원인 | tool이 반환한 JSON 문자열을 `json.loads()` 없이 `"data": last`로 그대로 반환 |
| 증상 | 프론트엔드 `response.data.action` → `undefined` (data가 string이므로) |
| 피해 | Zustand 슬롯 저장 불가, 화면 전환 신호 수신 불가 |
| 수정 | `json.loads(last)` 후 반환, `JSONDecodeError` 시 `tts_reply`로 안전하게 래핑 |

#### v1 → v2 메시지 포맷 변경

```python
# v1 (결함)
message = f"{body.transcript}\n[슬롯:{body.current_slots}]"

# v2 (수정)
message = (
    f"[사용자ID:{user_id}]\n"
    f"{body.transcript}\n"
    f"[슬롯:{body.current_slots}]"
)
```

#### v1 → v2 응답 파싱 변경

```python
# v1 (결함) — raw string 반환
last = result["messages"][-1].content
return {"success": True, "data": last, "message": ""}

# v2 (수정) — json.loads + fallback
try:
    data = json.loads(last)
except (json.JSONDecodeError, TypeError):
    data = {"action": "tts_reply", "tts_text": last, "slots": {}}
return {"success": True, "data": data, "message": ""}
```

---

### Step 8 — `shared/agent/router.py` 신규 생성 (Issue #7)

```python
"""에이전트 채팅 라우터 — Issue #7 구현."""

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.jwt_utils import get_current_user_id
from app.shared.agent.graph import build_graph
from app.shared.agent.tools import ALL_TOOLS

router = APIRouter(prefix="/api/agent", tags=["agent"])

_graph = build_graph(ALL_TOOLS)


class AgentChatRequest(BaseModel):
    transcript: str
    current_slots: str = "{}"


@router.post("/chat", response_model=dict)
async def chat(
    body: AgentChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """STT 결과를 에이전트에 전달하고 action JSON을 반환합니다."""
    message = f"{body.transcript}\n[슬롯:{body.current_slots}]"
    result = await _graph.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": user_id}},
    )
    last = result["messages"][-1].content
    return {"success": True, "data": last, "message": ""}
```

---

### Step 9 — `main.py` 수정

기존 `app.include_router(recipients_router)` 다음에 추가:

```python
from app.features.transfer.router import router as transfer_router
from app.shared.agent.router import router as agent_router

app.include_router(transfer_router)
app.include_router(agent_router)
```

---

### Step 10 — `tests/test_transfer.py` (신규)

> **최종 구현 기준** — 아래 코드가 실제 `backend/tests/test_transfer.py`에 반영된 확정본입니다.
>
> 초안 대비 주요 변경 사항:
> 1. `_cleanup`: `filter_by()` → `filter(Model.col == id)` + `synchronize_session=False` + `try/except/rollback`
> 2. 픽스처 계좌번호: 평문 직접 저장 → `encrypt()` 래핑 (CRYPTO_NOOP=true 시 투명 패스스루)
> 3. `from app.shared.crypto import encrypt` 임포트 추가
> 4. `_base_payload`: `account_id` → `str(account_id)` 명시적 타입 변환
> 5. `test_response_fields`: 필드 존재 확인 + `"*" in data["accountMasked"]` 마스킹 검증 + `amount` 값 일치 검증 추가
> 6. `test_direct_entry_success`: `toName` 값 단언 제거 (status_code만 검증)

```python
"""이체 기능 통합 테스트.

실행:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_transfer.py -v

전제 조건:
    - .env POSTGRES_* 설정 (Aiven)
    - idempotency_key 컬럼 Aiven 마이그레이션 완료
    - CRYPTO_NOOP=true: encrypt/decrypt 평문 패스스루 (테스트 환경 전용)

UUID 타입 안전성:
    User/Transaction/RegisteredRecipient.user_id → PGUUID(as_uuid=True) → uuid.UUID 객체 직접 바인딩 가능
    Account.account_id / Transaction.tx_id / RegisteredRecipient.recipient_id → String(36) → str
"""

import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.transaction import Transaction
from app.models.user import User
from app.shared.crypto import encrypt  # CRYPTO_NOOP=true 시 평문 그대로 반환

_TEST_PIN = "000001"
_TEST_PIN_HASH = bcrypt.hashpw(_TEST_PIN.encode(), bcrypt.gensalt()).decode()
_FAKE_AUDIO = b"RIFF$\x00\x00\x00WAVEfmt "

# service.py가 `import httpx` 후 `httpx.AsyncClient()`를 사용하므로 이 경로가 정확함
# `from httpx import AsyncClient` 방식이면 "app.features.transfer.service.AsyncClient"로 변경
ASV_PATCH = "app.features.transfer.service.httpx.AsyncClient"


def _random_phone() -> str:
    return f"010-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, phone: str) -> str:
    res = client.post("/api/users/login", json={"phone": phone, "pin": _TEST_PIN})
    assert res.status_code == 200, f"로그인 실패: {res.json()}"
    return res.json()["data"]["accessToken"]


def _cleanup(user_id: uuid.UUID) -> None:
    """FK 의존 순서대로 삭제: Transaction → RegisteredRecipient → Account → User

    변경점(초안 대비):
    - filter_by() → filter(Model.col == id): PGUUID 컬럼에 uuid.UUID 직접 비교
    - synchronize_session=False: 세션 간 충돌 방지
    - try/except/rollback: 정리 중 오류 시 상태 보호
    """
    db = SessionLocal()
    try:
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


def _asv_mock(is_same_speaker: bool) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "is_same_speaker": is_same_speaker,
        "similarity_score": 0.95 if is_same_speaker else 0.3,
    }
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


def _post_transfer(client: TestClient, token: str, payload: dict, audio: bytes = _FAKE_AUDIO):
    with patch(ASV_PATCH, return_value=_asv_mock(True)):
        return client.post(
            "/api/transfer",
            files={"audio": ("t.wav", io.BytesIO(audio), "audio/wav")},
            data={"transfer_data": json.dumps(payload)},
            headers=_auth(token),
        )


def _base_payload(account_id: str, **kwargs) -> dict:
    return {
        "fromAccountId": str(account_id),  # str() 명시적 변환
        "amount": 50_000,
        "idempotencyKey": str(uuid.uuid4()),
        **kwargs,
    }


@pytest.fixture(scope="module")
def sender(db: Session):
    """잔액 1,000,000원 / 음성 임베딩 192차원 등록 완료.

    변경점: account_number에 encrypt() 적용 (CRYPTO_NOOP=true 시 평문 그대로).
    """
    user = User(
        name="이체 테스터", phone=_random_phone(),
        pin_hash=_TEST_PIN_HASH, embedding_vector=[0.1] * 192,
    )
    db.add(user)
    db.flush()
    account = Account(
        user_id=user.user_id, bank_name="우리은행",
        account_number=encrypt("1002-SEND-0001"),
        account_type="입출금",
        balance=1_000_000, is_primary=True,
    )
    db.add(account)
    db.commit()
    db.refresh(user)
    db.refresh(account)
    yield user, account
    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def receiver(db: Session):
    """신한은행 주계좌(is_primary=True) / 잔액 0원."""
    user = User(
        name="수신자 테스터", phone=_random_phone(),
        pin_hash=_TEST_PIN_HASH, embedding_vector=[0.2] * 192,
    )
    db.add(user)
    db.flush()
    db.add(Account(
        user_id=user.user_id, bank_name="신한은행",
        account_number=encrypt("110-RECV-0001"),
        account_type="입출금",
        balance=0, is_primary=True,
    ))
    db.commit()
    db.refresh(user)
    yield user
    _cleanup(user.user_id)


@pytest.fixture(scope="module")
def registered_recipient(db: Session, sender):
    """발신자의 즐겨찾기 등록 수취인.

    변경점: account_number에 encrypt() 적용.
    resolve_by_id()가 내부에서 decrypt()를 호출하므로 반드시 암호화 저장해야 함.
    """
    sender_user, _ = sender
    r = RegisteredRecipient(
        user_id=sender_user.user_id, alias="친구",
        bank_name="카카오뱅크", account_number=encrypt("3333-REG-0001"),
        recipient_name="김철수",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    yield r
    # sender _cleanup()에서 일괄 삭제


@pytest.fixture(scope="module")
def sender_token(client: TestClient, sender):
    sender_user, _ = sender
    return _login(client, sender_user.phone)


class TestRegisteredMode:
    def test_transfer_success(self, client, sender_token, sender, registered_recipient, db):
        """등록 수취인 ID로 이체 성공 + DB에 completed 거래 레코드 생성."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200
        assert res.json()["success"] is True
        tx = db.query(Transaction).filter(
            Transaction.idempotency_key == payload["idempotencyKey"]
        ).first()
        assert tx is not None
        assert tx.status == "completed"

    def test_response_fields(self, client, sender_token, sender, registered_recipient):
        """응답 필드 구조 + accountMasked 보안 마스킹 규칙 검증.

        변경점(초안 대비):
        - 필드 존재 확인 외에 "*" in data["accountMasked"] 마스킹 검증 추가
        - data["amount"] == payload["amount"] 값 일치 검증 추가
        - 응답 필드명: accountMasked (toAccountNumber 아님 — TransferResult alias 기준)
        """
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientId=str(registered_recipient.recipient_id),
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200
        data = res.json()["data"]

        for field in ("txId", "toName", "bankName", "accountMasked", "amount"):
            assert field in data, f"{field} 필드 누락 — TransferResult by_alias=True 기준"

        assert "*" in data["accountMasked"], (
            f"계좌번호 마스킹 미적용: '{data['accountMasked']}'"
        )
        assert data["amount"] == payload["amount"]
        assert len(data["txId"]) > 0


class TestPhoneMode:
    def test_transfer_via_primary_account(self, client, sender_token, sender, receiver):
        """전화번호 → is_primary 계좌로 이체 성공."""
        _, from_account = sender
        payload = _base_payload(from_account.account_id, recipientPhone=receiver.phone)
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200

    def test_unregistered_phone_lookup_returns_404(self, client, sender_token):
        """미가입 번호 조회 → 404 TRANSFER_RECIPIENT_NOT_FOUND."""
        res = client.get(
            "/api/transfer/lookup/phone",
            params={"phone": "010-0000-0000"},
            headers=_auth(sender_token),
        )
        assert res.status_code == 404
        assert res.json()["code"] == "TRANSFER_RECIPIENT_NOT_FOUND"


class TestDirectMode:
    def test_direct_entry_success(self, client, sender_token, sender):
        """계좌번호·은행명·수취인명 직접 입력 → 이체 성공."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="9999-DIRECT-001", bankName="하나은행", toName="이영희",
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 200

    def test_direct_missing_bank_name_returns_422(self, client, sender_token, sender):
        """toAccountNumber 입력 시 bankName 누락 → XOR 검증 오류 422."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="9999-DIRECT-002", toName="이영희",
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 422


class TestXORValidation:
    def test_two_methods_returns_422(self, client, sender_token, sender, receiver, registered_recipient):
        """recipientId + recipientPhone 동시 입력 → XOR 위반 422."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            recipientId=str(registered_recipient.recipient_id),
            recipientPhone=receiver.phone,
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 422

    def test_no_method_returns_422(self, client, sender_token, sender):
        """수취인 지정 방식 미입력 → XOR 위반 422."""
        _, from_account = sender
        payload = _base_payload(from_account.account_id)
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 422


class TestIdempotency:
    def test_same_key_twice_one_record(self, client, sender_token, sender, db):
        """동일 idempotencyKey 2회 요청 → DB 레코드 1건, txId 동일."""
        _, from_account = sender
        key = str(uuid.uuid4())
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="9999-IDEM-001", bankName="우리은행", toName="멱등성 테스터",
            idempotencyKey=key,
        )
        res1 = _post_transfer(client, sender_token, payload)
        res2 = _post_transfer(client, sender_token, payload)
        assert res1.json()["data"]["txId"] == res2.json()["data"]["txId"]
        count = (
            db.query(Transaction)
            .filter(Transaction.idempotency_key == key)
            .count()
        )
        assert count == 1, f"멱등성 위반: DB에 중복 레코드 {count}건"


class TestFailureCases:
    def test_asv_failed_returns_403(self, client, sender_token, sender):
        """ASV is_same_speaker=False → VOICE_VERIFICATION_FAILED 403."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="9999-FAIL-001", bankName="우리은행", toName="위조자",
        )
        with patch(ASV_PATCH, return_value=_asv_mock(False)):
            res = client.post(
                "/api/transfer",
                files={"audio": ("t.wav", io.BytesIO(_FAKE_AUDIO), "audio/wav")},
                data={"transfer_data": json.dumps(payload)},
                headers=_auth(sender_token),
            )
        assert res.status_code == 403
        assert res.json()["code"] == "VOICE_VERIFICATION_FAILED"

    def test_insufficient_balance_returns_400(self, client, sender_token, sender):
        """잔액 초과 금액 이체 → INSUFFICIENT_BALANCE 400."""
        _, from_account = sender
        payload = _base_payload(
            from_account.account_id,
            toAccountNumber="9999-INS-001", bankName="우리은행", toName="대금 테스터",
            amount=99_000_000,
        )
        res = _post_transfer(client, sender_token, payload)
        assert res.status_code == 400
        assert res.json()["code"] == "INSUFFICIENT_BALANCE"

    def test_no_token_returns_401(self, client, sender):
        """Authorization 헤더 없음 → JWT 인증 실패 401."""
        _, from_account = sender
        payload = _base_payload(from_account.account_id, toAccountNumber="x", bankName="x", toName="x")
        res = client.post(
            "/api/transfer",
            files={"audio": ("t.wav", io.BytesIO(_FAKE_AUDIO), "audio/wav")},
            data={"transfer_data": json.dumps(payload)},
        )
        assert res.status_code == 401
```

---

## Verification

```bash
cd backend
CRYPTO_NOOP=true pytest tests/test_transfer.py -v

# 전체 회귀
CRYPTO_NOOP=true pytest tests/ -v

# Swagger 확인
uvicorn app.main:app --reload
# http://localhost:8000/docs → POST /api/transfer
```

**이슈 완료 조건 체크리스트**

| 조건 | 대응 테스트 |
|------|------------|
| alias 등록 수취인 이체 성공 | `TestRegisteredMode::test_transfer_success` |
| 전화번호 → is_primary 이체 성공 | `TestPhoneMode::test_transfer_via_primary_account` |
| 미가입 번호 → 직접 입력 안내 | `TestPhoneMode::test_unregistered_phone_lookup_returns_404` |
| 3가지 request type 동작 | Registered + Phone + Direct 클래스 |
| transactions 레코드 생성 확인 | `test_transfer_success` DB 직접 조회 |
| Agent tool 등록 | `tools/__init__.py` ALL_TOOLS |
| main.py router 등록 | Step 9 |
| pytest 작성·실행 | `test_transfer.py` 전체 |
