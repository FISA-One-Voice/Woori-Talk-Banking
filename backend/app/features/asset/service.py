# =============================================================================
# backend/app/features/asset/service.py
#
# [이 파일의 역할]
# 자산 화면 비즈니스 로직을 담당합니다.
# - 전체 계좌 목록 + 잔액 조회
# - 계좌별 잔액 조회
# - 거래 내역 조회 (day, category 필터)
#
# [규칙]
# service.py 에서 raise → router.py 에서 전파 → main.py 에서 처리
# router.py 에는 try/except 없음
# =============================================================================

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exception import BalanceError, HistoryError
from app.models.account import Account
from app.models.transaction import Transaction


def get_asset_summary(db: Session, user_id: str) -> list[Account]:
    """
    사용자의 전체 계좌 목록과 잔액을 조회합니다.

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
        .filter(Account.user_id == user_id)
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
    """
    특정 계좌의 잔액을 조회합니다.

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
            Account.user_id == user_id,
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
    """
    거래 내역을 조회합니다. day, category 슬롯 필터를 지원합니다.

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
    query = db.query(Transaction).filter(Transaction.user_id == user_id)

    # 계좌 필터
    if account_id:
        query = query.filter(Transaction.from_account_id == account_id)

    # 날짜 필터
    if days:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        query = query.filter(Transaction.created_at >= since)

    # 카테고리 필터
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