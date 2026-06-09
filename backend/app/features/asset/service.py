from datetime import datetime, timedelta, timezone
import logging
import re
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.exception import BalanceError, HistoryError
from app.models.account import Account
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

# 슬롯에서 허용되는 기간 값 (STT 정규화 후 이 셋 중 하나여야 유효)
VALID_PERIODS: frozenset[str] = frozenset({"이번달", "지난달", "최근7일"})


# ── DB 조회 ──────────────────────────────────────────────────────────────────
# 아래 함수들은 순수 DB 조회만 담당한다.
# 비즈니스 로직(TTS 문자열 생성 등)은 하단 TTS 응답 생성 섹션에서 처리한다.

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
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[Transaction]:
    """거래 내역을 조회합니다. account_id, days, category 필터를 지원합니다.

    Args:
        db: DB 세션.
        user_id: 사용자 UUID 문자열.
        account_id: 특정 계좌 필터 (None이면 전체 계좌).
        days: 최근 N일 필터. since가 있으면 무시.
        category: 카테고리 필터 (None이면 전체).
        since: 조회 시작 datetime (포함). 지정 시 days 무시.
        until: 조회 종료 datetime (미포함). 지난달 등 월 단위 필터에 사용.

    Returns:
        Transaction 객체 리스트 (최신순 정렬).
    """
    query = db.query(Transaction).filter(Transaction.user_id == uuid.UUID(user_id))

    if account_id:
        query = query.filter(Transaction.from_account_id == account_id)

    if since is not None:
        query = query.filter(Transaction.created_at >= since)
    elif days:
        computed_since = datetime.now(timezone(timedelta(hours=9))).replace(
            tzinfo=None
        ) - timedelta(days=days)
        query = query.filter(Transaction.created_at >= computed_since)

    if until is not None:
        query = query.filter(Transaction.created_at < until)

    if category:
        query = query.filter(Transaction.category == category)

    transactions = query.order_by(Transaction.created_at.desc()).all()

    if not transactions:
        raise HistoryError(
            code="TX_NOT_FOUND",
            message="거래 내역을 찾을 수 없습니다.",
            status_code=404,
            user_message="거래 내역을 찾을 수 없습니다.",
        )

    return transactions


def get_expense_summary(
    db: Session,
    user_id: str,
    days: int = 30,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, int | list[dict[str, str | int]]]:
    """지출 요약을 반환합니다 (총액 및 카테고리 Top 5).

    Args:
        db: DB 세션.
        user_id: 사용자 UUID 문자열.
        days: 조회 기간(일수). since가 있으면 무시.
        since: 조회 시작 datetime. 지정 시 days 무시.
        until: 조회 종료 datetime (미포함).

    Returns:
        total(int), days(int), top_categories(list) 를 포함한 dict.

    Raises:
        HistoryError: 지출 거래 내역이 없을 때.
    """
    if since is None:
        since = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None) - timedelta(
            days=days
        )
    filters = [
        Transaction.user_id == uuid.UUID(user_id),
        Transaction.created_at >= since,
        Transaction.status == "completed",
        or_(
            Transaction.category.is_(None),
            Transaction.category != "수입",
        ),
    ]
    if until is not None:
        filters.append(Transaction.created_at < until)
    transactions = (
        db.query(Transaction)
        .filter(*filters)
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

    # 카테고리별 합산
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


# ── 화면 TTS 문구 생성 ────────────────────────────────────────────────────────
# REST API 응답에 포함되어 프론트엔드가 재생만 하도록 한다.
# 프론트엔드에서 문자열을 직접 조합하지 않고 이 함수가 생성한 값을 사용한다.

KST = timezone(timedelta(hours=9))


def _format_amount(amount: int) -> str:
    """금액을 TTS 친화적 한국어 표현으로 변환한다."""
    if amount >= 100_000_000:
        eok = amount // 100_000_000
        man = (amount % 100_000_000) // 10_000
        return f"{eok}억 {man:,}만원" if man else f"{eok}억원"
    if amount >= 10_000:
        return f"{amount // 10_000:,}만원"
    return f"{amount:,}원"


def build_summary_tts(accounts: list, total_asset: int) -> str:
    """자산 요약 화면 진입 시 재생할 TTS 문구를 생성한다."""
    account_voice = ", ".join(
        f"{a.alias or a.account_type} {_format_amount(a.balance)}"
        for a in accounts
    )
    return (
        f"총 자산은 {_format_amount(total_asset)}입니다. "
        f"{account_voice}. "
        f"지출 수입 내역이나 거래내역은 화면을 꾹 눌러 음성으로 말씀하시면 알 수 있습니다."
    )


def build_transaction_tts(t) -> str:
    """거래 내역 카드 탭 시 재생할 TTS 문구를 생성한다."""
    try:
        dt = t.created_at
        if dt.tzinfo is not None:
            dt = dt.astimezone(KST).replace(tzinfo=None)
        date_str = f"{dt.month}월 {dt.day}일"
    except Exception:
        date_str = ""
    sign = "입금" if t.category == "수입" else "출금"
    name = t.to_name or t.category or ""
    memo_str = f". 메모 {t.memo}" if t.memo else ""
    return f"{date_str} {name} {sign} {abs(t.amount):,}원{memo_str}"


# ── 슬롯 변환 헬퍼 ────────────────────────────────────────────────────────────
# STT 음성 인식 결과를 시스템 내부 값으로 정규화하는 유틸 함수 모음.
# tools/asset.py의 @tool 함수에서 슬롯 값을 전처리할 때 사용한다.

def normalize_period(period: str | None) -> str | None:
    """STT 오인식 보정 — '최근 7일', '최근칠일', '최근 N일' 등을 정규화."""
    if not period:
        return period
    p = period.replace(" ", "")
    if p in ("최근7일", "최근칠일", "7일", "최근7", "최근칠"):
        return "최근7일"
    if p in ("이번달", "이번월", "이달"):
        return "이번달"
    if p in ("지난달", "저번달", "지난월", "전달", "저번월"):
        return "지난달"
    if p in ("이번주", "이번주간", "이주"):
        return "이번주"
    if p in ("지난주", "저번주", "지난주간", "전주"):
        return "지난주"
    m = re.match(r'최근(\d+)일', p)
    if m:
        return f"최근{m.group(1)}일"
    # "5월달", "5월" → "5월"
    m = re.match(r'(\d+)월', p)
    if m:
        return f"{m.group(1)}월"
    return period


def period_to_days(period: str | None) -> int:
    """period 슬롯 값을 조회 일수(int)로 변환한다."""
    p = normalize_period(period)
    if p == "최근7일":
        return 7
    if p == "지난달":
        return 60
    return 30  # 이번달 기본값


def period_to_date_range(period: str | None) -> tuple[datetime, datetime | None]:
    """period를 (since, until) KST datetime 쌍으로 변환한다.
    '지난달'은 전월 1일 00:00 ~ 이번달 1일 00:00 (exclusive)로 정확히 필터.
    '지난주'는 전주 월요일 00:00 ~ 이번주 월요일 00:00 (exclusive).
    """
    # KST 기준으로 since 날짜 계산 (DB 저장값이 naive datetime이므로 tzinfo 제거)
    now_kst = datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None)
    p = normalize_period(period)

    m = re.match(r'최근(\d+)일$', p or "")
    if m:
        return now_kst - timedelta(days=int(m.group(1))), None

    m = re.match(r'^(\d+)월$', p or "")
    if m:
        month = int(m.group(1))
        year = now_kst.year if month <= now_kst.month else now_kst.year - 1
        first_day = now_kst.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = month % 12 + 1
        next_year = year + 1 if month == 12 else year
        last_day = first_day.replace(year=next_year, month=next_month)
        return first_day, last_day

    if p == "지난달":
        first_this = now_kst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_prev = first_this - timedelta(days=1)
        first_prev = last_day_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return first_prev, first_this

    if p == "이번주":
        # 이번주 월요일 00:00 ~ 현재
        monday = now_kst - timedelta(days=now_kst.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        return monday, None

    if p == "지난주":
        # 지난주 월요일 00:00 ~ 이번주 월요일 00:00
        this_monday = now_kst - timedelta(days=now_kst.weekday())
        this_monday = this_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        last_monday = this_monday - timedelta(weeks=1)
        return last_monday, this_monday

    # 이번달 (기본값)
    first_this = now_kst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_this, None


def date_range_to_since(date_range: str | None) -> datetime | None:
    """date_range 슬롯(YYYY-MM-DD)을 datetime으로 변환한다. 파싱 실패 시 None 반환."""
    if not date_range:
        return None
    try:
        return datetime.strptime(date_range, "%Y-%m-%d")
    except ValueError:
        return None


# ── TTS 응답 생성 ─────────────────────────────────────────────────────────────
# 각 함수는 DB 조회 결과를 TTS로 읽힐 자연어 문자열로 변환한다.
# tools/asset.py의 query_asset @tool이 action 슬롯에 따라 아래 함수 중 하나를 호출한다.

def query_balance_tts(db: Session, user_id: str) -> str:
    """전체 잔액을 TTS 문자열로 반환한다."""
    accounts = get_asset_summary(db, user_id)
    total = sum(a.balance for a in accounts)
    return f"잔액 조회해드리겠습니다. 전체 잔액은 {total:,}원입니다."


def query_transaction_list_tts(
    db: Session, user_id: str, period: str | None, date_range: str | None
) -> str:
    """거래내역 목록을 TTS 문자열로 반환한다 (최대 10건 읽어줌)."""
    period = normalize_period(period)
    if period and period not in VALID_PERIODS and not re.match(r'최근\d+일$', period) and not re.match(r'^\d+월$', period):
        return "조회할 수 없는 기간입니다. 이번달, 지난달, 최근 N일, N월 형식으로 말씀해 주세요."

    custom_since = date_range_to_since(date_range)
    if custom_since:
        since, until = custom_since, None
    else:
        since, until = period_to_date_range(period)
    label = period or "이번달"
    txs = get_transaction_history(db, user_id, since=since, until=until)

    # status="completed" 건만 읽어줌 (pending/failed 제외)
    completed = [t for t in txs if t.status == "completed"]
    if not completed:
        raise HistoryError(
            code="TX_NOT_FOUND",
            message="거래 내역을 찾을 수 없습니다.",
            status_code=404,
            user_message=f"{label} 거래 내역이 없습니다.",
        )

    total = len(completed)
    income_cnt = sum(1 for t in completed if t.category == "수입")
    expense_cnt = total - income_cnt
    result = f"{label} 거래내역은 총 {total}건입니다. 입금 {income_cnt}건, 출금 {expense_cnt}건입니다. "

    items = []
    for t in completed[:10]:  # TTS가 너무 길어지지 않도록 최대 10건만 읽음
        try:
            dt = t.created_at
            if dt.tzinfo is not None:
                # DB가 timezone-aware datetime을 반환하면 KST로 변환 후 naive로 만든다
                dt = dt.astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)
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
    """수입/지출 요약을 TTS 문자열로 반환한다.

    filter_type: "income"=수입만, "expense"=지출만, None/"both"=둘다
    """
    period = normalize_period(period)
    if period and period not in VALID_PERIODS and not re.match(r'최근\d+일$', period) and not re.match(r'^\d+월$', period):
        return "조회할 수 없는 기간입니다. 이번달, 지난달, 최근 N일, N월 형식으로 말씀해 주세요."

    custom_since = date_range_to_since(date_range)
    if custom_since:
        since, until = custom_since, None
    else:
        since, until = period_to_date_range(period)
    label = period or "이번달"
    try:
        txs = get_transaction_history(db, user_id, since=since, until=until)
    except HistoryError:
        raise HistoryError(
            code="TX_NOT_FOUND",
            message=f"{label} 거래 내역이 없습니다.",
            status_code=404,
            user_message=f"{label} 거래 내역이 없습니다.",
        )

    completed = [t for t in txs if t.status == "completed"]
    if not completed:
        raise HistoryError(
            code="TX_NOT_FOUND",
            message=f"{label} 거래 내역이 없습니다.",
            status_code=404,
            user_message=f"{label} 거래 내역이 없습니다.",
        )

    income = sum(t.amount for t in completed if t.category == "수입")
    expense = sum(t.amount for t in completed if t.category != "수입")

    if filter_type == "income":
        return f"{label} 수입 내역 알려드리겠습니다. 수입은 {income:,}원입니다."

    if filter_type == "expense":
        result = f"{label} 지출 내역 알려드리겠습니다. 지출은 {expense:,}원입니다."
        try:
            # 주요 지출 카테고리 상위 3개 추가 (실패해도 기본 메시지는 반환)
            summary = get_expense_summary(db, user_id, since=since, until=until)
            top = summary["top_categories"][:3]
            if top:
                cat_text = ", ".join(f"{c['category']} {c['amount']:,}원" for c in top)
                result += f" 주요 지출은 {cat_text}입니다."
        except Exception as e:
            logger.warning("카테고리 요약 조회 실패 (비필수): %s", e)
        return result

    # filter_type == "both" 또는 None — 수입·지출 모두 요약
    result = (
        f"{label} 지출 수입 내역 알려드리겠습니다. "
        f"수입은 {income:,}원, 지출은 {expense:,}원입니다."
    )
    try:
        # 주요 지출 카테고리 상위 3개 추가 (실패해도 기본 메시지는 반환)
        summary = get_expense_summary(db, user_id, since=since, until=until)
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
    """카테고리별 지출을 TTS 문자열로 반환한다."""
    if not category:
        return "어떤 카테고리를 조회할까요? 예: 식비, 교통, 문화생활."
    since, until = period_to_date_range(period)
    label = normalize_period(period) or "이번달"
    txs = get_transaction_history(db, user_id, since=since, until=until, category=category)
    total = sum(t.amount for t in txs)
    return f"{label} {category} 내역 알려드리겠습니다. 총 {len(txs)}건, {total:,}원 지출하셨습니다."


def query_top_category_tts(db: Session, user_id: str, period: str | None) -> str:
    """카테고리 지출 순위 1위를 TTS 문자열로 반환한다."""
    since, until = period_to_date_range(period)
    label = normalize_period(period) or "이번달"
    summary = get_expense_summary(db, user_id, since=since, until=until)
    top = summary["top_categories"]
    if not top:
        return f"{label} 지출 내역이 없습니다."
    top_cat = top[0]
    return (
        f"{label} 지출 순위 알려드리겠습니다. "
        f"가장 많이 지출한 항목은 {top_cat['category']}로 {top_cat['amount']:,}원입니다."
    )


def get_compare_data(
    db: Session,
    user_id: str,
    period: str = "이번달",
    compare_period: str = "지난달",
    category: str | None = None,
) -> dict:
    """두 기간의 지출을 비교합니다."""
    since1, until1 = period_to_date_range(period)
    since2, until2 = period_to_date_range(compare_period)

    def _get_amount(since, until) -> int:
        try:
            if category:
                txs = get_transaction_history(db, user_id, since=since, until=until, category=category)
                return sum(t.amount for t in txs if t.status == "completed" and t.category != "수입")  # 수입 제외, 지출만 집계
            else:
                summary = get_expense_summary(db, user_id, since=since, until=until)
                return summary["total"]
        except Exception:
            return 0

    amount1 = _get_amount(since1, until1)
    amount2 = _get_amount(since2, until2)

    return {
        "period": period,
        "compare_period": compare_period,
        "category": category,
        "period_amount": amount1,
        "compare_amount": amount2,
        "diff": amount1 - amount2,
    }


def query_compare_tts(
    db: Session,
    user_id: str,
    period: str = "이번달",
    compare_period: str = "지난달",
    category: str | None = None,
) -> str:
    """두 기간 지출 비교를 TTS 문자열로 반환한다."""
    data = get_compare_data(db, user_id, period, compare_period, category)
    amount1 = data["period_amount"]
    amount2 = data["compare_amount"]
    diff = data["diff"]
    label = f"{category} " if category else ""

    if diff > 0:
        trend = f"{abs(diff):,}원 증가했습니다"
    elif diff < 0:
        trend = f"{abs(diff):,}원 감소했습니다"
    else:
        trend = "동일합니다"

    return (
        f"{label}지출 비교 알려드리겠습니다. "
        f"{period}는 {amount1:,}원, {compare_period}는 {amount2:,}원으로 "
        f"{trend}."
    )
