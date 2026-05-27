from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from app.core.exception import BalanceError, HistoryError
from app.models.account import Account
from app.models.transaction import Transaction


def get_asset_summary(db: Session, user_id: str) -> list[Account]:
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
    query = db.query(Transaction).filter(Transaction.user_id == uuid.UUID(user_id))

    if account_id:
        query = query.filter(Transaction.from_account_id == account_id)

    if days:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
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