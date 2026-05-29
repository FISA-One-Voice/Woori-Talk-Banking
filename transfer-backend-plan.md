# Transfer 기능 백엔드 구현 계획

## Context

음성 기반 뱅킹 앱(Woori-Talk-Banking)의 이체(Transfer) API 레이어를 구현한다.  
AI 에이전트(`execute_transfer` tool)와 프론트엔드가 신뢰할 수 있는 금융 API를 제공하는 것이 목표이며,  
잔액 이중 차감·중복 이체 등 금전적 사고를 애플리케이션/DB 두 계층에서 완전히 방어해야 한다.

---

## 디렉토리 결정

사용자 spec은 `app/api/`, `app/schemas/`, `app/services/`를 언급했으나,  
**기존 코드베이스 전체가 `app/features/<domain>/` 구조**를 사용하며  
`voice-pipeline-flow.md`도 `app/features/transfer/tools.py`를 명시하므로  
→ `app/features/transfer/` 에 구현한다.

---

## 수정/생성 파일 목록

| 파일 | 작업 |
|------|------|
| `app/models/transaction.py` | `idempotency_key` 컬럼 + UniqueConstraint 추가 |
| `app/core/exception.py` | `TransferError` 클래스 추가 |
| `app/features/transfer/__init__.py` | 신규 (빈 파일) |
| `app/features/transfer/schema.py` | 신규 (Pydantic 스키마) |
| `app/features/transfer/service.py` | 신규 (비즈니스 로직) |
| `app/features/transfer/router.py` | 신규 (엔드포인트) |
| `app/main.py` | `transfer_router` 등록 |

---

## 1. `app/models/transaction.py` — idempotency_key 추가

**현황**: DB DDL에는 `idempotency_key VARCHAR(36)`가 있으나 ORM 모델에 누락됨.

```python
# 기존 import에 UniqueConstraint 추가
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint

class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transaction_idempotency_key"),
    )

    # ... 기존 컬럼들 유지 ...

    # 새로 추가 — NULL 허용(자동이체 등 idempotency_key 불필요한 케이스 존재)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
```

> ⚠️ **DB 마이그레이션 필요**: 모델 변경 후 PostgreSQL에 반영해야 함
> ```sql
> ALTER TABLE transactions ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100);
> CREATE UNIQUE INDEX IF NOT EXISTS uq_transaction_idempotency_key
>   ON transactions (idempotency_key) WHERE idempotency_key IS NOT NULL;
> ```
> UniqueConstraint는 NULL을 제외해야 중복 NULL 저장이 가능. PostgreSQL은 `WHERE IS NOT NULL` partial index로 처리.

---

## 2. `app/core/exception.py` — TransferError 추가

파일 맨 끝에 추가:

```python
class TransferError(AppError):
    """이체 처리 중 발생하는 에러.

    코드 목록:
        INVALID_ACCOUNT_FORMAT     계좌번호 형식 오류 (400)
        TRANSFER_ACCOUNT_NOT_FOUND 출금 계좌 없음 (404)
        TRANSFER_PENDING           동일 key 이체 진행 중 (409)
        IDEMPOTENCY_KEY_USED       동일 key가 이미 실패 처리됨 (409)
        INSUFFICIENT_BALANCE       잔액 부족 (400)
        TRANSACTION_NOT_FOUND      트랜잭션 없음 (404)
    """
    pass
```

`main.py`의 `AppError` 핸들러가 서브클래스를 자동 처리하므로 핸들러 추가 불필요.

---

## 3. `app/features/transfer/schema.py`

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TransferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient: str = Field(..., alias="recipient", description="계좌번호 (10~14자리 숫자)")
    bank_name: str = Field(..., alias="bankName")
    amount: int = Field(..., alias="amount", gt=0)
    idempotency_key: str = Field(..., alias="idempotencyKey", min_length=1, max_length=100)
    recipient_name: Optional[str] = Field(None, alias="recipientName")
    recipient_id: Optional[str] = Field(None, alias="recipientId")


class MemoUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    memo: str = Field(..., alias="memo", max_length=255)
```

---

## 4. `app/features/transfer/service.py`

재사용 함수:
- `app.features.recipients.service.resolve_by_id` — recipient_id → ResolvedRecipient
- `app.shared.crypto.encrypt / decrypt` — AES-256-GCM
- `app.core.exception.TransferError` / `RecipientError`

```python
import re
import uuid
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exception import TransferError
from app.features.recipients.service import resolve_by_id
from app.models.account import Account
from app.models.transaction import Transaction
from app.shared.crypto import decrypt, encrypt

_ACCOUNT_RE = re.compile(r"^\d{10,14}$")


def _get_primary_account(db: Session, user_uuid: uuid.UUID) -> Account:
    account = (
        db.query(Account)
        .filter(Account.user_id == user_uuid, Account.is_primary.is_(True))
        .first()
    )
    if account is None:
        raise TransferError(
            code="TRANSFER_ACCOUNT_NOT_FOUND",
            message="출금 계좌를 찾을 수 없습니다.",
            status_code=404,
        )
    return account


def _mask_account(plain: str) -> str:
    if len(plain) <= 10:
        return plain
    return plain[:6] + "***" + plain[-4:]


def _build_receipt(tx: Transaction) -> dict:
    return {
        "txId": tx.tx_id,
        "fromAccountId": tx.from_account_id,
        "toBankName": tx.to_bank_name,
        "toName": tx.to_name,
        "amount": tx.amount,
        "status": tx.status,
        "createdAt": tx.created_at.isoformat(),
    }


# ── API 1: 이체 실행 ────────────────────────────────────────────────────────

def execute_transfer(
    db: Session,
    user_id: str,
    recipient: str,
    bank_name: str,
    amount: int,
    idempotency_key: str,
    recipient_name: str | None,
    recipient_id: str | None,
) -> dict:
    user_uuid = uuid.UUID(user_id)

    # 계좌번호 형식 검증 (recipient_id 없는 직접 입력 경우만)
    if recipient_id is None:
        cleaned = recipient.replace("-", "").replace(" ", "")
        if not _ACCOUNT_RE.match(cleaned):
            raise TransferError(
                code="INVALID_ACCOUNT_FORMAT",
                message="계좌번호는 10~14자리 숫자여야 합니다.",
                status_code=400,
            )
        recipient = cleaned

    # 멱등성 체크 (앱 레벨 — 일반적인 중복 요청 빠른 처리)
    existing_tx = (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing_tx is not None:
        if existing_tx.status == "pending":
            raise TransferError(
                code="TRANSFER_PENDING",
                message="동일한 이체 요청이 처리 중입니다.",
                status_code=409,
            )
        if existing_tx.status == "completed":
            return _build_receipt(existing_tx)
        # status == "failed": key 소진, 재사용 불가
        raise TransferError(
            code="IDEMPOTENCY_KEY_USED",
            message="이 idempotency_key는 실패한 이체에 사용되었습니다. 새 key를 발급하세요.",
            status_code=409,
        )

    # 수취인 정보 해석
    resolved_recipient_id: str | None = None
    if recipient_id:
        resolved = resolve_by_id(db, user_uuid, recipient_id)  # RecipientError(404) 가능
        resolved_recipient_id = resolved.recipient_id
        to_account_number = resolved.account_number
        to_bank_name = resolved.bank_name
        to_name = resolved.recipient_name
    else:
        to_account_number = recipient
        to_bank_name = bank_name
        to_name = recipient_name

    # pending INSERT — idempotency_key UNIQUE 제약이 동시 요청의 최후 방어선
    from_account = _get_primary_account(db, user_uuid)
    tx = Transaction(
        user_id=user_uuid,
        from_account_id=from_account.account_id,
        recipient_id=resolved_recipient_id,
        to_bank_name=to_bank_name,
        to_account_number=encrypt(to_account_number),
        to_name=to_name,
        amount=amount,
        tx_type="transfer",
        status="pending",
        idempotency_key=idempotency_key,
    )
    db.add(tx)
    try:
        db.flush()  # PK 생성 + UNIQUE 위반 즉시 감지
    except IntegrityError:
        db.rollback()
        # 동시 요청 경쟁에서 진 건 → 409
        raise TransferError(
            code="TRANSFER_PENDING",
            message="동일한 이체 요청이 처리 중입니다.",
            status_code=409,
        )

    # SELECT FOR UPDATE — 출금 계좌 비관적 락 (잔액 이중 차감 방지)
    locked_account = (
        db.query(Account)
        .filter(Account.account_id == from_account.account_id)
        .with_for_update()
        .first()
    )

    if locked_account.balance < amount:
        tx.status = "failed"
        db.commit()  # failed 상태로 커밋 (idempotency_key 소진)
        raise TransferError(
            code="INSUFFICIENT_BALANCE",
            message="잔액이 부족합니다.",
            status_code=400,
        )

    locked_account.balance -= amount
    tx.status = "completed"
    db.commit()
    return _build_receipt(tx)


# ── API 2: 메모 업데이트 ────────────────────────────────────────────────────

def update_memo(db: Session, user_id: str, tx_id: str, memo: str) -> dict:
    user_uuid = uuid.UUID(user_id)
    tx = (
        db.query(Transaction)
        .filter(Transaction.tx_id == tx_id, Transaction.user_id == user_uuid)
        .first()
    )
    if tx is None:
        raise TransferError(
            code="TRANSACTION_NOT_FOUND",
            message="트랜잭션을 찾을 수 없습니다.",
            status_code=404,
        )
    tx.memo = memo
    db.commit()
    return {"txId": tx_id, "memo": memo}


# ── API 3: 최근 수취인 조회 ─────────────────────────────────────────────────

def get_recent_recipients(db: Session, user_id: str, limit: int = 5) -> list[dict]:
    """recipient_id 기준 GROUP BY.

    AES-256-GCM은 비결정적(동일 평문 → 매번 다른 암호문)이므로
    to_account_number로 DB GROUP BY 불가 → recipient_id 기준으로 그루핑.
    """
    user_uuid = uuid.UUID(user_id)

    subq = (
        db.query(
            Transaction.recipient_id,
            func.max(Transaction.created_at).label("last_at"),
        )
        .filter(
            Transaction.user_id == user_uuid,
            Transaction.status == "completed",
            Transaction.tx_type == "transfer",
            Transaction.recipient_id.isnot(None),
        )
        .group_by(Transaction.recipient_id)
        .order_by(func.max(Transaction.created_at).desc())
        .limit(limit)
        .subquery()
    )

    rows = (
        db.query(Transaction)
        .join(
            subq,
            (Transaction.recipient_id == subq.c.recipient_id)
            & (Transaction.created_at == subq.c.last_at),
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )

    result = []
    for tx in rows:
        plain = decrypt(tx.to_account_number) if tx.to_account_number else ""
        result.append({
            "recipientId": tx.recipient_id,
            "toBankName": tx.to_bank_name,
            "toName": tx.to_name,
            "accountMasked": _mask_account(plain),
            "lastTransferredAt": tx.created_at.isoformat(),
        })
    return result
```

---

## 5. `app/features/transfer/router.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.transfer import service
from app.features.transfer.schema import MemoUpdateRequest, TransferRequest

router = APIRouter(prefix="/api/transfer", tags=["Transfer"])


# ⚠️ GET /recent를 /{tx_id}/memo 보다 먼저 등록 — FastAPI는 선언 순서로 경로 매칭
@router.get("/recent", response_model=dict)
def get_recent_recipients(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    data = service.get_recent_recipients(db=db, user_id=user_id)
    return {
        "success": True,
        "data": {"recipients": data},
        "message": f"{len(data)}건의 최근 수취인을 조회했습니다.",
    }


@router.post("/", response_model=dict)
def create_transfer(
    req: TransferRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    data = service.execute_transfer(
        db=db,
        user_id=user_id,
        recipient=req.recipient,
        bank_name=req.bank_name,
        amount=req.amount,
        idempotency_key=req.idempotency_key,
        recipient_name=req.recipient_name,
        recipient_id=req.recipient_id,
    )
    return {"success": True, "data": data, "message": "이체가 완료되었습니다."}


@router.post("/{tx_id}/memo", response_model=dict)
def update_memo(
    tx_id: str,
    req: MemoUpdateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    data = service.update_memo(db=db, user_id=user_id, tx_id=tx_id, memo=req.memo)
    return {"success": True, "data": data, "message": "메모가 업데이트되었습니다."}
```

---

## 6. `app/main.py` — 라우터 등록

```python
# 기존 import 블록에 추가
from app.features.transfer.router import router as transfer_router

# 기존 include_router 블록에 추가 (recipients_router 아래)
app.include_router(transfer_router)
```

---

## 핵심 보안/동시성 설계 요약

### 레이스 컨디션 이중 방어

```
[동일 idempotency_key 동시 요청 2건]

Request-1                          Request-2
  ↓ SELECT → 없음                    ↓ SELECT → 없음
  ↓ INSERT pending                   ↓ INSERT pending
  ↓ flush → 성공                     ↓ flush → IntegrityError (UNIQUE 위반)
  ↓ SELECT FOR UPDATE (락 취득)      ↓ rollback → 409
  ↓ 잔액 차감 + completed
  ↓ commit
```

- **1차 방어**: 앱 레벨 SELECT로 기존 레코드 확인 (일반적인 중복 빠른 처리)
- **2차 방어**: DB UNIQUE 제약 + IntegrityError 핸들링 (진짜 경쟁 상황)

### 잔액 이중 차감 방지

```
[동일 계좌에서 두 건 동시 출금]
Request-1 → SELECT FOR UPDATE (락 취득) → 차감 → commit → 락 해제
Request-2 → SELECT FOR UPDATE (대기) ──────────────────────→ 잔액 재확인
```

### 데드락 방지 (v1)

단일 계좌 락만 사용하므로 데드락 발생 불가.  
향후 수취 계좌 락 추가 시: `sorted([from_id, to_id])` 오름차순으로 락 취득 순서 고정 필요.

### idempotency_key 상태별 처리

| 기존 상태 | 응답 |
|-----------|------|
| 없음 | 신규 이체 진행 |
| `pending` | 409 TRANSFER_PENDING |
| `completed` | 200 (기존 영수증 재반환, 출금 없음) |
| `failed` | 409 IDEMPOTENCY_KEY_USED (새 key 발급 요구) |

### AES-256-GCM 제약 — 최근 수취인 조회

AES-256-GCM은 비결정적(nonce 랜덤 → 동일 평문도 매번 다른 암호문).  
→ `to_account_number`로 DB GROUP BY 불가.  
→ `recipient_id` 기준으로 GROUP BY (등록 수취인 경로에서만 중복 제거).

---

## 검증 방법

### 1. 서버 기동 확인
```bash
cd backend && uvicorn app.main:app --reload
# GET http://localhost:8000/docs → Transfer 섹션 확인
```

### 2. 정상 이체 흐름
```bash
# 로그인 → access_token 취득
POST /api/users/login  {"phone": "...", "pin": "..."}

# 이체 실행
POST /api/transfer/
{
  "recipient": "1234567890",
  "bankName": "우리은행",
  "amount": 10000,
  "idempotencyKey": "<uuid-v4>",
  "recipientId": "<recipient_id>"
}
# 기대: 200, status="completed", 잔액 차감 확인
```

### 3. 멱등성 검증
```bash
# 동일 idempotencyKey 2회 요청
# 첫 번째: 200 completed
# 두 번째: 200 (기존 영수증 재반환, 잔액 변화 없음)
```

### 4. 잔액 부족
```bash
# amount > balance 로 요청 → 400 INSUFFICIENT_BALANCE
# DB에서 해당 tx의 status='failed' 확인
# 동일 idempotencyKey 재요청 → 409 IDEMPOTENCY_KEY_USED
```

### 5. 최근 수취인 조회
```bash
GET /api/transfer/recent
# 기대: 최대 5건, recipient_id 기준 중복 제거, 최신순 정렬
```

### 6. DB 마이그레이션 확인
```sql
-- idempotency_key 컬럼 및 partial unique index 존재 여부 확인
\d transactions
SELECT indexname FROM pg_indexes WHERE tablename='transactions';
```
