from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from app.core.exception import BalanceError, HistoryError
from app.models.account import Account
from app.models.transaction import Transaction


def get_asset_summary(db: Session, user_id: str) -> list[Account]:
    """사용자의 전체 계좌 목록과 잔액을 조회합니다.

    Args:
        db: DB 세션.
        user_id: 조회할 사용자 UUID 문자열.

    Returns:
        Account 객체 리스트 (기본 계좌 우선 정렬).

    Raises:
        BalanceError: 계좌가 없을 때.
    """
    accounts = (
        db.query(Account)
        .filter(Account.user_id == uuid.UUID(user_id))
        .order_by(Account.is_primary.desc(), Account.created_at.asc())
        .all()
    )

    if not accounts:
        raise BalanceError(
            code="ACCOUNT_NOT_FOUND",
            message="계좌를 찾을 수 없습니다.",
            status_code=404,
        )

    return accounts


def get_account_balance(db: Session, user_id: str, account_id: str) -> Account:
    """특정 계좌의 잔액을 조회합니다.

    Args:
        db: DB 세션.
        user_id: 사용자 UUID 문자열.
        account_id: 조회할 계좌 ID.

    Returns:
        Account 객체.

    Raises:
        BalanceError: 계좌가 없거나 본인 계좌가 아닐 때.
    """
    account = (
        db.query(Account)
        .filter(
            Account.account_id == account_id,
            Account.user_id == uuid.UUID(user_id),
        )
        .first()
    )

    if not account:
        raise BalanceError(
            code="ACCOUNT_NOT_FOUND",
            message="계좌를 찾을 수 없습니다.",
            status_code=404,
        )

    return account


def get_transaction_history(
    db: Session,
    user_id: str,
    account_id: str | None = None,
    days: int | None = None,
    category: str | None = None,
) -> list[Transaction]:
    """거래 내역을 조회합니다. account_id, days, category 필터를 지원합니다.

    Args:
        db: DB 세션.
        user_id: 사용자 UUID 문자열.
        account_id: 특정 계좌 필터 (None이면 전체 계좌).
        days: 최근 N일 필터 (None이면 전체 기간).
        category: 카테고리 필터 (None이면 전체).

    Returns:
        Transaction 객체 리스트 (최신순 정렬).

    Raises:
        HistoryError: 거래 내역이 없을 때.
    """
    query = db.query(Transaction).filter(Transaction.user_id == uuid.UUID(user_id))

    if account_id:
        query = query.filter(Transaction.from_account_id == account_id)

    if days:
        since = datetime.now(timezone(timedelta(hours=9))).replace(
            tzinfo=None
        ) - timedelta(days=days)
        query = query.filter(Transaction.created_at >= since)

    if category:
        query = query.filter(Transaction.category == category)

    transactions = query.order_by(Transaction.created_at.desc()).all()

    if not transactions:
        raise HistoryError(
            code="TX_NOT_FOUND",
            message="거래 내역을 찾을 수 없습니다.",
            status_code=404,
        )

    return transactions
