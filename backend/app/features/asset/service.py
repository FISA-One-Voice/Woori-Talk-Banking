from datetime import datetime, timedelta, timezone
import logging
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.exception import BalanceError, HistoryError
from app.models.account import Account
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

VALID_PERIODS: frozenset[str] = frozenset({"이번달", "지난달", "최근7일"})


# ── DB 조회 ──────────────────────────────────────────────────────────────────

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
            user_message="계좌를 찾을 수 없습니다.",
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
            user_message="계좌를 찾을 수 없습니다.",
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
    return query.order_by(Transaction.created_at.desc()).all()


def get_expense_summary(
    db: Session, user_id: str, days: int = 30
) -> dict[str, int | list[dict[str, str | int]]]:
    """지출 요약을 반환합니다 (총액 및 카테고리 Top 5).

    Args:
        db: DB 세션.
        user_id: 사용자 UUID 문자열.
        days: 조회 기간(일수). 기본 30일.

    Returns:
        total(int), days(int), top_categories(list) 를 포함한 dict.

    Raises:
        HistoryError: 지출 거래 내역이 없을 때.
    """
    since = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None) - timedelta(
        days=days
    )
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == uuid.UUID(user_id),
            Transaction.created_at >= since,
            Transaction.status == "completed",
            or_(
                Transaction.category.is_(None),
                Transaction.category != "수입",
            ),
        )
        .all()
    )
    if not transactions:
        raise HistoryError(
            code="TX_NOT_FOUND",
            message="해당 기간에 지출 내역이 없습니다.",
            status_code=404,
            user_message="해당 기간에 지출 내역이 없습니다.",
        )
    total = sum(t.amount for t in transactions)
    category_totals: dict[str, int] = {}
    for t in transactions:
        cat = t.category or "기타"
        category_totals[cat] = category_totals.get(cat, 0) + t.amount
    top5 = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "total": total,
        "days": days,
        "top_categories": [{"category": k, "amount": v} for k, v in top5],
    }


# ── 슬롯 변환 헬퍼 ────────────────────────────────────────────────────────────

def normalize_period(period: str | None) -> str | None:
    """STT 오인식 보정 — '최근 7일', '최근칠일' 등을 정규화."""
    if not period:
        return period
    p = period.replace(" ", "")
    if p in ("최근7일", "최근칠일", "7일", "최근7", "최근칠"):
        return "최근7일"
    if p in ("이번달", "이번월", "이달"):
        return "이번달"
    if p in ("지난달", "저번달", "지난월", "전달", "저번월"):
        return "지난달"
    return period


def period_to_days(period: str | None) -> int:
    p = normalize_period(period)
    if p == "최근7일":
        return 7
    if p == "지난달":
        return 60
    return 30  # 이번달 기본값


def date_range_to_since(date_range: str | None) -> datetime | None:
    if not date_range:
        return None
    try:
        return datetime.strptime(date_range, "%Y-%m-%d")
    except ValueError:
        return None


# ── TTS 응답 생성 ─────────────────────────────────────────────────────────────

def query_balance_tts(db: Session, user_id: str) -> str:
    accounts = get_asset_summary(db, user_id)
    total = sum(a.balance for a in accounts)
    return f"잔액 조회해드리겠습니다. 전체 잔액은 {total:,}원입니다."


def query_transaction_list_tts(
    db: Session, user_id: str, period: str | None, date_range: str | None
) -> str:
    period = normalize_period(period)
    if period and period not in VALID_PERIODS:
        return "조회할 수 없는 기간입니다. 이번달, 지난달, 최근 7일 중 말씀해 주세요."
    since = date_range_to_since(date_range)
    days = None if since else period_to_days(period)
    txs = get_transaction_history(db, user_id, days=days)
    label = period or "이번달"
    completed = [t for t in txs if t.status == "completed"]
    if not completed:
        return f"{label} 거래 내역이 없습니다."
    total = len(completed)
    income_cnt = sum(1 for t in completed if t.category == "수입")
    expense_cnt = total - income_cnt
    result = f"{label} 거래내역은 총 {total}건입니다. 입금 {income_cnt}건, 출금 {expense_cnt}건입니다. "
    items = []
    for t in completed[:10]:
        try:
            dt = t.created_at
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            date_str = f"{dt.month}월 {dt.day}일"
        except Exception:
            date_str = ""
        sign = "입금" if t.category == "수입" else "출금"
        name = t.to_name or t.category or ""
        memo_str = f" 메모 {t.memo}" if t.memo else ""
        items.append(f"{date_str} {name} {sign} {abs(t.amount):,}원{memo_str}")
    result += ". ".join(items) + "."
    return result


def query_history_tts(
    db: Session,
    user_id: str,
    period: str | None,
    date_range: str | None,
    filter_type: str | None = None,
) -> str:
    period = normalize_period(period)
    if period and period not in VALID_PERIODS:
        return "조회할 수 없는 기간입니다. 이번달, 지난달, 최근 7일 중 말씀해 주세요."
    since = date_range_to_since(date_range)
    days = None if since else period_to_days(period)
    txs = get_transaction_history(db, user_id, days=days)
    label = period or "이번달"
    completed = [t for t in txs if t.status == "completed"]
    if not completed:
        return f"{label} 거래 내역이 없습니다."
    income = sum(t.amount for t in completed if t.category == "수입")
    expense = sum(t.amount for t in completed if t.category != "수입")
    if filter_type == "income":
        return f"{label} 수입 내역 알려드리겠습니다. 수입은 {income:,}원입니다."
    if filter_type == "expense":
        result = f"{label} 지출 내역 알려드리겠습니다. 지출은 {expense:,}원입니다."
        try:
            summary = get_expense_summary(db, user_id, days=days or 30)
            top = summary["top_categories"][:3]
            if top:
                cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top)
                result += f" 주요 지출은 {cat_text}입니다."
        except Exception as e:
            logger.warning("카테고리 요약 조회 실패 (비필수): %s", e)
        return result
    result = (
        f"{label} 지출 수입 내역 알려드리겠습니다. "
        f"수입은 {income:,}원, 지출은 {expense:,}원입니다."
    )
    try:
        summary = get_expense_summary(db, user_id, days=days or 30)
        top = summary["top_categories"][:3]
        if top:
            cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top)
            result += f" 주요 지출은 {cat_text}입니다."
    except Exception as e:
        logger.warning("카테고리 요약 조회 실패 (비필수): %s", e)
    return result


def query_category_tts(
    db: Session, user_id: str, period: str | None, category: str | None
) -> str:
    if not category:
        return "어떤 카테고리를 조회할까요? 예: 식비, 교통, 문화생활."
    days = period_to_days(period)
    txs = get_transaction_history(db, user_id, days=days, category=category)
    total = sum(t.amount for t in txs)
    label = period or "이번달"
    return f"{label} {category} 내역 알려드리겠습니다. 총 {len(txs)}건, {total:,}원 지출하셨습니다."


def query_top_category_tts(db: Session, user_id: str, period: str | None) -> str:
    days = period_to_days(period)
    label = period or "이번달"
    summary = get_expense_summary(db, user_id, days=days)
    top = summary["top_categories"]
    if not top:
        return f"{label} 지출 내역이 없습니다."
    top_cat = top[0]
    return (
        f"{label} 지출 순위 알려드리겠습니다. "
        f"가장 많이 지출한 항목은 {top_cat['category']}로 {top_cat['amount']:,}원입니다."
    )
