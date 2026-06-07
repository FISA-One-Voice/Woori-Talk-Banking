"""이체 비즈니스 로직."""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exception import AppError, TransferError
from app.features.recipients.service import (
    lookup_recipient_for_transfer,
    resolve_by_id,
    resolve_direct_account,
)
from app.models.account import Account
from app.models.transaction import Transaction
from app.shared.crypto import decrypt, encrypt

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))

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


# ── 에이전트 tool용 TTS 래퍼 ─────────────────────────────────────────────────
# tools/transfer.py는 아래 함수를 호출하는 thin wrapper만 둔다.

def execute_transfer_tts(
    db: Session,
    user_id: str,
    recipient: str,
    amount: int,
    collected_slots: dict | None = None,
) -> tuple[str, str | None]:
    """이체를 실행하고 (TTS 메시지, tx_id)를 반환한다."""
    slots = collected_slots or {}
    try:
        user_uuid = uuid.UUID(user_id)
        recipient_id = slots.get("recipient_id")
        if recipient_id:
            resolved = resolve_by_id(db, user_uuid, str(recipient_id))
        elif slots.get("account_number") and slots.get("bank_name"):
            resolved = resolve_direct_account(
                str(slots["account_number"]),
                str(slots["bank_name"]),
                recipient_name=str(slots.get("recipient") or recipient or "수취인"),
            )
        else:
            resolved = lookup_recipient_for_transfer(
                db,
                user_uuid,
                recipient,
                bank_name=str(slots["bank_name"]) if slots.get("bank_name") else None,
            )

        if resolved is None:
            return f"{recipient}님을 찾을 수 없습니다. 다시 확인해 주세요.", None

        display_name = str(slots.get("recipient") or recipient or resolved.recipient_name)
        receipt = execute_transfer(
            db=db,
            user_id=user_id,
            recipient=resolved.account_number,
            bank_name=resolved.bank_name,
            amount=amount,
            idempotency_key=str(uuid.uuid4()),
            recipient_name=resolved.recipient_name,
            recipient_id=str(resolved.recipient_id) if resolved.recipient_id else None,
        )
        return f"{display_name}님께 {amount:,}원 이체가 완료되었습니다.", receipt["txId"]
    except AppError as e:
        logger.warning("execute_transfer_tts AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message, None
    except Exception as e:
        logger.error("execute_transfer_tts 실패: user=%s error=%s", user_id, e)
        return "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", None


def add_note_tts(db: Session, user_id: str, memo: str, tx_id: str) -> str:
    """이체 거래에 메모를 추가하고 TTS 메시지를 반환한다."""
    try:
        update_memo(db=db, user_id=user_id, tx_id=tx_id, memo=memo)
        return f"'{memo}' 메모가 추가되었습니다."
    except AppError as e:
        logger.warning("add_note_tts AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    except Exception as e:
        logger.error("add_note_tts 실패: user=%s tx_id=%s error=%s", user_id, tx_id, e)
        return "메모 추가 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def get_transfer_history_tts(db: Session, user_id: str, days: int = 30) -> str:
    """최근 이체 내역을 TTS 문자열로 반환한다."""
    try:
        user_uuid = uuid.UUID(user_id)
        since = datetime.now(_KST).replace(tzinfo=None) - timedelta(days=days)
        txs = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_uuid,
                Transaction.status == "completed",
                Transaction.tx_type.in_(["transfer", "auto_transfer"]),
                Transaction.created_at >= since,
            )
            .order_by(Transaction.created_at.desc())
            .limit(10)
            .all()
        )
        if not txs:
            return f"최근 {days}일간 이체 내역이 없습니다."
        parts = []
        for tx in txs:
            type_label = "자동이체" if tx.tx_type == "auto_transfer" else "이체"
            name = tx.to_name or "수취인"
            text = f"{name}에게 {tx.amount:,}원 {type_label}"
            if tx.memo:
                text += f", 메모 '{tx.memo}'"
            parts.append(text)
        return f"이체 내역 알려드리겠습니다. 최근 {len(txs)}건입니다. " + ". ".join(parts) + "."
    except Exception as e:
        logger.error("get_transfer_history_tts 실패: user=%s error=%s", user_id, e)
        return "이체 내역 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
