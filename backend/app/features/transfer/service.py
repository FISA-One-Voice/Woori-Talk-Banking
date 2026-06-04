"""이체 비즈니스 로직."""

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
            user_message="출금 계좌를 찾을 수 없습니다.",
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
    memo: str | None = None,
) -> dict:
    """이체를 실행하고 영수증을 반환합니다.

    멱등성 보호:
        앱 레벨: idempotency_key SELECT — completed 재반환, failed → 409
        DB 레벨: pending INSERT UNIQUE 제약 — IntegrityError 시 409 반환
        잔액 락: SELECT FOR UPDATE로 출금 계좌 행 비관적 락 취득
    """
    user_uuid = uuid.UUID(user_id)

    # 계좌번호 형식 검증 (recipient_id 없는 직접 입력 경우만)
    if recipient_id is None:
        cleaned = recipient.replace("-", "").replace(" ", "")
        if not _ACCOUNT_RE.match(cleaned):
            raise TransferError(
                code="INVALID_ACCOUNT_FORMAT",
                message="계좌번호는 10~14자리 숫자여야 합니다.",
                status_code=400,
                user_message="계좌번호 형식이 올바르지 않습니다.",
            )
        recipient = cleaned

    # 멱등성 체크 (앱 레벨)
    existing_tx = (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing_tx is not None:
        if existing_tx.status == "completed":
            # 중복 요청: 기존 영수증 재반환 (출금 없음)
            return _build_receipt(existing_tx)
        # status == "failed": key 소진, 재사용 불가
        raise TransferError(
            code="IDEMPOTENCY_KEY_USED",
            message="이 idempotency_key는 실패한 이체에 사용되었습니다. 새 key를 발급하세요.",
            status_code=409,
            user_message="이미 처리된 이체 요청입니다.",
        )

    # 수취인 정보 해석
    resolved_recipient_id: str | None = None
    if recipient_id:
        # RecipientError(404) 발생 가능 — AppError 핸들러가 처리
        resolved = resolve_by_id(db, user_uuid, recipient_id)
        resolved_recipient_id = resolved.recipient_id
        to_account_number = resolved.account_number
        to_bank_name = resolved.bank_name
        to_name = resolved.recipient_name
    else:
        to_account_number = recipient
        to_bank_name = bank_name
        to_name = recipient_name

    # pending INSERT — UNIQUE 제약이 동시 요청의 최후 방어선
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
        memo=memo,
    )
    db.add(tx)
    try:
        db.flush()  # PK 생성 + UNIQUE 위반 즉시 감지
    except IntegrityError:
        db.rollback()
        raise TransferError(
            code="TRANSFER_PENDING",
            message="동일한 이체 요청이 처리 중입니다.",
            status_code=409,
            user_message="동일한 이체 요청이 처리 중입니다.",
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
            user_message="잔액이 부족합니다.",
        )

    locked_account.balance -= amount
    tx.status = "completed"
    db.commit()
    return _build_receipt(tx)


# ── API 2: 메모 업데이트 ────────────────────────────────────────────────────


def update_memo(db: Session, user_id: str, tx_id: str, memo: str) -> dict:
    """본인 소유 트랜잭션의 메모를 업데이트합니다."""
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
            user_message="해당 거래를 찾을 수 없습니다.",
        )
    tx.memo = memo
    db.commit()
    return {"txId": tx_id, "memo": memo}


# ── API 3: 최근 수취인 조회 ─────────────────────────────────────────────────


def get_recent_recipients(db: Session, user_id: str, limit: int = 5) -> list[dict]:
    """최근 이체 완료 트랜잭션에서 recipient_id 기준 중복 제거 후 최신 수취인을 반환합니다.

    AES-256-GCM은 비결정적(동일 평문 → 매번 다른 암호문)이므로
    to_account_number로 DB GROUP BY 불가 → recipient_id 기준으로 그루핑.
    """
    user_uuid = uuid.UUID(user_id)

    # recipient_id별 최신 순서 번호 부여 (rn=1이 가장 최근)
    # created_at 동등 비교 방식은 동시 삽입 시 타임스탬프 충돌로 오동작하므로 사용하지 않는다.
    rn_subq = (
        db.query(
            Transaction.tx_id,
            func.row_number()
            .over(
                partition_by=Transaction.recipient_id,
                order_by=Transaction.created_at.desc(),
            )
            .label("rn"),
        )
        .filter(
            Transaction.user_id == user_uuid,
            Transaction.status == "completed",
            Transaction.tx_type == "transfer",
            Transaction.recipient_id.isnot(None),
        )
        .subquery()
    )

    # Subquery를 IN()에 직접 전달하면 SQLAlchemy가 경고와 함께 잘못된 SQL을 생성할 수 있으므로
    # tx_id를 Python 리스트로 먼저 조회한 뒤 IN()에 전달한다.
    top_tx_id_rows = db.query(rn_subq.c.tx_id).filter(rn_subq.c.rn == 1).all()
    tx_ids = [r[0] for r in top_tx_id_rows]
    if not tx_ids:
        return []

    rows = (
        db.query(Transaction)
        .filter(Transaction.tx_id.in_(tx_ids))
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for tx in rows:
        plain = decrypt(tx.to_account_number) if tx.to_account_number else ""
        result.append(
            {
                "recipientId": str(tx.recipient_id) if tx.recipient_id else None,
                "toBankName": tx.to_bank_name,
                "toName": tx.to_name,
                "accountMasked": _mask_account(plain),
                "lastTransferredAt": tx.created_at.isoformat(),
            }
        )
    return result
