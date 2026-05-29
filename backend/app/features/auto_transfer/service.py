"""
💳 자동이체 기능 핵심 비즈니스 로직 (Core Backend Service)

[레이어 역할 분담 및 데이터 흐름]
1. 레이어 1 (AI 에이전트 툴):
   - 유저가 "엄마한테 매월 15일 오만원 자동이체"라고 발화하면, match_by_name()으로
     수취인을 확정하고 cycle/amount/scheduledDay 슬롯을 수집합니다.
2. 레이어 2 (프론트엔드 Canvas):
   - 확인 화면에서 수취인 정보를 원본 그대로 보여주고 PIN 입력 폼을 제공합니다.
3. 레이어 3 (본 이체 서비스 API):
   - 사용자가 확인 후 최종 등록을 내리면 실행되는 최종 금고 사령탑입니다.
   - 금융 안전을 위해 5관문 보안 파이프라인을 순서대로 수행합니다.

[수취인 경로별 처리 전략]
REGISTERED : resolve_by_id() → recipient_id 직접 사용
DIRECT     : create_recipient() 자동 등록 → recipient_id 확보
(StandingOrder.recipient_id 가 nullable=False 이므로 DIRECT는 자동 등록 필수)
"""

import calendar
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.orm import Session

from app.core.exception import AutoTransferError
from app.features.auto_transfer.schema import (
    AutoTransferListItem,
    AutoTransferMemoRequest,
    AutoTransferMemoResult,
    AutoTransferRequest,
    AutoTransferResult,
    StatusUpdateRequest,
    StatusUpdateResult,
)
from app.features.recipients.schema import ResolvedRecipient
from app.features.recipients.service import create_recipient, resolve_by_id
from app.models.account import Account
from app.models.standing_order import StandingOrder
from app.models.transaction import Transaction
from app.models.user import User
from app.shared.crypto import encrypt

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "active": {"paused", "cancelled"},
    "paused": {"active", "cancelled"},
    "cancelled": set(),
}


def _mask_account(account_number: str | None) -> str:
    """[보안 헬퍼] 계좌번호의 뒷자리 4개만 남기고 앞부분은 모두 별표(*)로 가립니다.

    예시: '110-123-456789' ➔ '**********6789'
    """
    if not account_number:
        return "****"
    if len(account_number) <= 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]


def _now_kst() -> datetime:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).replace(tzinfo=None)


def _calc_next_execution(
    cycle: str,
    scheduled_day: int | None,
    scheduled_dow: int | None,
) -> datetime:
    """다음 실행일 자정(00:00:00)을 계산합니다.

    Args:
        cycle: 'monthly' 또는 'weekly'.
        scheduled_day: monthly 전용 (1~31). 해당 월에 없는 날짜는 말일로 처리.
        scheduled_dow: weekly 전용 (0=월~6=일). 오늘 포함 이미 지난 요일이면 다음 주.

    Returns:
        다음 실행일 자정 datetime.
    """
    now = _now_kst()
    today = now.date()

    if cycle == "monthly":
        last_day = calendar.monthrange(today.year, today.month)[1]
        actual_day = min(scheduled_day, last_day)
        candidate = today.replace(day=actual_day)
        if candidate <= today:
            # 이번 달 지정일이 이미 지났으면 다음 달로 이동
            year = today.year + (1 if today.month == 12 else 0)
            month = 1 if today.month == 12 else today.month + 1
            last_day = calendar.monthrange(year, month)[1]
            candidate = today.replace(year=year, month=month, day=min(scheduled_day, last_day))
        return datetime(candidate.year, candidate.month, candidate.day)

    # weekly — Python weekday(): 0=월, 6=일
    days_ahead = scheduled_dow - today.weekday()
    if days_ahead <= 0:
        # 오늘 포함 이미 지난 요일이면 다음 주로 이동
        days_ahead += 7
    candidate = today + timedelta(days=days_ahead)
    return datetime(candidate.year, candidate.month, candidate.day)


def _resolve_recipient(
    db: Session,
    user_uuid: uuid.UUID,
    data: AutoTransferRequest,
) -> ResolvedRecipient:
    """수취인 경로(REGISTERED / PHONE / DIRECT)에 따라 수취인 정보를 조회합니다.

    PHONE / DIRECT 경로는 StandingOrder.recipient_id(nullable=False) 충족을 위해
    RegisteredRecipient를 자동 생성합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID.
        data: 자동이체 등록 요청 바디.

    Returns:
        ResolvedRecipient (account_number는 평문, recipient_id 보장).

    """
    if data.recipient_id is not None:
        # REGISTERED 경로: 에이전트가 별명→ID 변환 후 전달한 UUID로 바로 조회
        return resolve_by_id(db, user_uuid, data.recipient_id)

    # DIRECT 경로: 계좌번호 직접 입력 → RegisteredRecipient 자동 등록
    return create_recipient(
        db,
        user_uuid,
        alias=data.to_name,
        bank_name=data.bank_name,
        account_number=data.to_account_number,
        recipient_name=data.to_name,
    )


def _verify_account(db: Session, user_uuid: uuid.UUID, from_account_id: str) -> Account:
    """출금 계좌 소유권을 확인합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID.
        from_account_id: 출금 계좌 ID.

    Returns:
        Account 인스턴스.

    Raises:
        AutoTransferError: 계좌 없음/타인 소유 (AUTO_ORDER_ACCOUNT_NOT_FOUND, 404).
    """
    account = (
        db.query(Account)
        .filter(Account.account_id == from_account_id, Account.user_id == user_uuid)
        .first()
    )
    if account is None:
        raise AutoTransferError(
            code="AUTO_ORDER_ACCOUNT_NOT_FOUND",
            message="출금 계좌를 찾을 수 없습니다.",
            status_code=404,
        )
    return account


def _verify_pin(user: User, raw_password: str) -> None:
    """사용자 PIN을 bcrypt로 검증합니다.

    Args:
        user: User 인스턴스.
        raw_password: 요청에서 전달된 평문 PIN.

    Raises:
        AutoTransferError: PIN 불일치 (AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID, 403).
    """
    if not bcrypt.checkpw(raw_password.encode(), user.pin_hash.encode()):
        raise AutoTransferError(
            code="AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID",
            message="PIN이 올바르지 않습니다.",
            status_code=403,
        )


# ── POST /api/auto-transfer ───────────────────────────────────────────────────

def register_auto_transfer(
    db: Session,
    user_id: str,
    data: AutoTransferRequest,
) -> AutoTransferResult:
    """[자동이체 등록 사령탑] 5관문 보안 파이프라인을 순서대로 수행합니다.

    사용자가 확인 화면에서 PIN을 입력하고 최종 등록을 누렀을 때 실행되며,
    금융 보안을 위해 [1관문]부터 [5관문]까지 절대로 순서를 변경하지 않습니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 사용자 ID.
        data: 자동이체 등록 요청 바디.

    Returns:
        AutoTransferResult.

    Raises:
        RecipientError: 수취인 조회 실패.
        AutoTransferError: 계좌/PIN/약관/저장 오류.
    """
    user_uuid = uuid.UUID(user_id)

    # ── 1관문: 수취인 조회/자동 등록 — REGISTERED / PHONE / DIRECT 스위치 ──
    # 프론트에서 확정한 식별자(recipient_id / phone / account)를 보고
    # 알맞은 조회 부품을 골라 실행합니다.
    resolved = _resolve_recipient(db, user_uuid, data)

    # ── 2관문: 출금 계좌 소유권 확인 ────────────────────────────────────────
    # 출금할 계좌가 진짜 내 계좌인지 먼저 확인합니다. 타인 계좌 접근을 원천 차단합니다.
    _verify_account(db, user_uuid, data.from_account_id)

    # ── 3관문: PIN bcrypt 검증 ───────────────────────────────────────────────
    # 음성 에이전트 흐름(password=None): ASV 통과가 PIN을 대체하므로 건너뜁니다.
    # 프론트 직접 호출 흐름(password 있음): 기존 PIN 검증을 수행합니다.
    user = db.query(User).filter(User.user_id == user_uuid).first()
    if data.password is not None:
        _verify_pin(user, data.password)

    # ── 4관문: 약관 동의 확인 ────────────────────────────────────────────────
    # 자동이체 서비스 약관에 동의하지 않으면 등록할 수 없습니다.
    if not data.terms_agreed:
        raise AutoTransferError(
            code="AUTO_ORDER_TERMS_NOT_AGREED",
            message="자동이체 약관에 동의해 주세요.",
            status_code=400,
        )

    # ── 5관문: 실행일 계산 + StandingOrder 저장 ─────────────────────────────
    # 모든 검문소를 프리패스했으므로 다음 실행일을 계산하고 DB에 등록합니다.
    # password_hash는 실행 시 재검증 없이 동의 시점을 증명하는 감사 기록용입니다.
    next_exec = _calc_next_execution(data.cycle, data.scheduled_day, data.scheduled_dow)

    order = StandingOrder(
        user_id=user_uuid,
        from_account_id=data.from_account_id,
        recipient_id=resolved.recipient_id,
        amount=data.amount,
        cycle=data.cycle,
        scheduled_day=data.scheduled_day,
        scheduled_dow=data.scheduled_dow,
        password_hash=user.pin_hash,
        terms_agreed_at=_now_kst(),
        status="active",
        next_execution_at=next_exec,
        transfer_note=data.transfer_note,
    )
    db.add(order)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise AutoTransferError(
            code="INTERNAL_ERROR",
            message="자동이체 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            status_code=500,
        ) from e

    return AutoTransferResult(
        order_id=str(order.order_id),
        to_name=resolved.recipient_name,
        bank_name=resolved.bank_name,
        account_masked=_mask_account(resolved.account_number),
        amount=order.amount,
        cycle=order.cycle,
        scheduled_day=order.scheduled_day,
        scheduled_dow=order.scheduled_dow,
        next_execution_at=next_exec.strftime("%Y-%m-%d"),
        status=order.status,
        transfer_note=order.transfer_note,
    )


# ── GET /api/auto-transfer ────────────────────────────────────────────────────

def list_auto_transfers(
    db: Session,
    user_id: str,
    status: str | None = None,
) -> list[AutoTransferListItem]:
    """사용자의 자동이체 목록을 반환합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 사용자 ID.
        status: 필터링할 상태값. None이면 전체 반환.

    Returns:
        AutoTransferListItem 목록 (등록일 내림차순).
    """
    user_uuid = uuid.UUID(user_id)
    query = db.query(StandingOrder).filter(StandingOrder.user_id == user_uuid)
    if status:
        query = query.filter(StandingOrder.status == status)
    orders = query.order_by(StandingOrder.created_at.desc()).all()

    result = []
    for order in orders:
        resolved = resolve_by_id(db, user_uuid, order.recipient_id)
        result.append(AutoTransferListItem(
            order_id=str(order.order_id),
            to_name=resolved.recipient_name,
            bank_name=resolved.bank_name,
            account_masked=_mask_account(resolved.account_number),
            amount=order.amount,
            cycle=order.cycle,
            scheduled_day=order.scheduled_day,
            scheduled_dow=order.scheduled_dow,
            next_execution_at=(
                order.next_execution_at.strftime("%Y-%m-%d")
                if order.next_execution_at else None
            ),
            status=order.status,
            transfer_note=order.transfer_note,
            created_at=order.created_at.isoformat(),
        ))
    return result


# ── PATCH /api/auto-transfer/{order_id}/status ───────────────────────────────

def update_status(
    db: Session,
    user_id: str,
    order_id: str,
    data: StatusUpdateRequest,
) -> StatusUpdateResult:
    """자동이체 상태를 변경합니다 (일시정지 / 재개 / 해지).

    order_id + user_id 소유권 이중 검증으로 타인의 자동이체 수정을 원천 차단합니다.
    cancelled 상태는 복구 불가이며, 허용되지 않은 전환 시 AUTO_ORDER_STATUS_INVALID를 반환합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 사용자 ID.
        order_id: 변경할 자동이체 ID.
        data: 변경할 상태값.

    Returns:
        StatusUpdateResult.

    Raises:
        AutoTransferError: 건 없음(AUTO_ORDER_NOT_FOUND) 또는 전환 불가(AUTO_ORDER_STATUS_INVALID).
    """
    user_uuid = uuid.UUID(user_id)
    order = (
        db.query(StandingOrder)
        .filter(StandingOrder.order_id == order_id, StandingOrder.user_id == user_uuid)
        .first()
    )
    if order is None:
        raise AutoTransferError(
            code="AUTO_ORDER_NOT_FOUND",
            message="자동이체 건을 찾을 수 없습니다.",
            status_code=404,
        )

    if data.status not in _ALLOWED_TRANSITIONS.get(order.status, set()):
        raise AutoTransferError(
            code="AUTO_ORDER_STATUS_INVALID",
            message=f"'{order.status}' 상태에서 '{data.status}'로 변경할 수 없습니다.",
            status_code=400,
        )

    order.status = data.status
    if data.status == "paused":
        order.next_execution_at = None
    elif data.status == "active":
        # 재개 시 오늘 기준으로 next_execution_at 재계산
        order.next_execution_at = _calc_next_execution(
            order.cycle, order.scheduled_day, order.scheduled_dow
        )

    db.commit()
    return StatusUpdateResult(order_id=str(order.order_id), status=order.status)


# ── POST /api/auto-transfer/{order_id}/label ─────────────────────────────────

def update_memo(
    db: Session,
    user_id: str,
    order_id: str,
    data: AutoTransferMemoRequest,
) -> AutoTransferMemoResult:
    """자동이체 건에 label을 사후 저장합니다.

    등록 완료 후 label을 편집하는 로직이므로 register_auto_transfer와 타이밍이
    분리됩니다.
    order_id + user_id 소유권 이중 검증으로 타인의 자동이체 수정을 원천 차단합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 사용자 ID.
        order_id: label을 저장할 자동이체 ID.
        data: 저장할 label 값.

    Returns:
        LabelResult.

    Raises:
        AutoTransferError: 건 없음/타인 소유 (AUTO_ORDER_NOT_FOUND, 404).
    """
    user_uuid = uuid.UUID(user_id)
    order = (
        db.query(StandingOrder)
        .filter(StandingOrder.order_id == order_id, StandingOrder.user_id == user_uuid)
        .first()
    )
    if order is None:
        raise AutoTransferError(
            code="AUTO_ORDER_NOT_FOUND",
            message="자동이체 건을 찾을 수 없습니다.",
            status_code=404,
        )

    order.transfer_note = data.transfer_note
    db.commit()
    return AutoTransferMemoResult(order_id=str(order.order_id), transfer_note=order.transfer_note)


# ── POST /api/auto-transfer/execute ──────────────────────────────────────────

def _execute_single_order(db: Session, order: StandingOrder) -> None:
    """단일 자동이체 건을 실행합니다.

    잔액 충분 시 balance 차감 + Transaction(completed) 생성 + next_execution_at 갱신.
    잔액 부족 시 Transaction(failed) 생성 후 다음 주기에 재시도 (status는 active 유지).
    with_for_update()로 동일 계좌 동시 차감을 방지합니다.
    """
    from_account = (
        db.query(Account)
        .filter(Account.account_id == order.from_account_id)
        .with_for_update()
        .first()
    )
    resolved = resolve_by_id(db, order.user_id, order.recipient_id)

    is_success = from_account is not None and from_account.balance >= order.amount

    if is_success:
        from_account.balance -= order.amount

    tx = Transaction(
        user_id=order.user_id,
        from_account_id=order.from_account_id,
        recipient_id=order.recipient_id,
        auto_order_id=order.order_id,
        to_bank_name=resolved.bank_name,
        to_account_number=encrypt(resolved.account_number),
        to_name=resolved.recipient_name,
        amount=order.amount,
        tx_type="auto_transfer",
        status="completed" if is_success else "failed",
    )
    db.add(tx)

    if is_success:
        order.next_execution_at = _calc_next_execution(
            order.cycle, order.scheduled_day, order.scheduled_dow
        )

    db.commit()


def run_due_auto_transfers(db: Session, user_id: str | None = None) -> dict:
    """오늘 실행 예정 자동이체를 일괄 실행합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: None이면 전체 유저 실행 (스케줄러용),
                 지정하면 해당 유저만 실행 (API 수동 트리거용).

    Returns:
        {"total": int, "success": int, "failed": int}
    """
    today_midnight = _now_kst().replace(hour=0, minute=0, second=0, microsecond=0)

    query = db.query(StandingOrder).filter(
        StandingOrder.status == "active",
        StandingOrder.next_execution_at <= today_midnight,
    )
    if user_id is not None:
        query = query.filter(StandingOrder.user_id == uuid.UUID(user_id))

    orders = query.all()

    success, failed = 0, 0
    for order in orders:
        try:
            _execute_single_order(db, order)
            success += 1
        except Exception:
            db.rollback()
            failed += 1

    return {"total": len(orders), "success": success, "failed": failed}
