"""이체 비즈니스 로직."""

import logging
import re
import time
import uuid

from app.core.metrics import transfer_total
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)

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

    transfer_start = time.monotonic()

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
        transfer_total.labels(status="failed").inc()
        raise TransferError(
            code="INSUFFICIENT_BALANCE",
            message="잔액이 부족합니다.",
            status_code=400,
            user_message="잔액이 부족합니다.",
        )

    locked_account.balance -= amount
    tx.status = "completed"
    db.commit()
    transfer_total.labels(status="success").inc()

    logger.info(
        "transfer_executed",
        extra={
            "event": "transfer_executed",
            "request_id": get_request_id(),
            "user_id": user_id,
            "tx_id": str(tx.tx_id),
            "amount": amount,
            "to_bank": to_bank_name,
            "to_account_masked": _mask_account(to_account_number),
            "status": "success",
            "duration_ms": int((time.monotonic() - transfer_start) * 1000),
        },
    )
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


# ── TTS 포맷 ────────────────────────────────────────────────────────────────────

from app.shared.agent.slot_schema import (  # noqa: E402
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
