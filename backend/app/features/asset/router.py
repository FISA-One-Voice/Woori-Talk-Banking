# =============================================================================
# backend/app/features/asset/router.py
#
# [이 파일의 역할]
# 자산 화면 URL 연결을 담당합니다.
# router.py 에는 try/except 없음 — 예외는 main.py 핸들러가 처리합니다.
#
# [엔드포인트 목록]
# GET /api/asset/summary              → 전체 계좌 잔액 조회
# GET /api/asset/balance/{account_id} → 계좌별 잔액 조회
# GET /api/asset/history              → 거래 내역 조회 (필터 지원)
# GET /api/asset/expense-summary      → 지출 요약 조회 (총액 + 카테고리 Top 5)
# GET /api/asset/compare              → 두 기간 지출 비교 (compare 화면용)
# =============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.asset import service
from app.features.asset.schema import (
    AccountBalanceItem,
    AssetSummaryResponse,
    CategoryItem,
    ExpenseSummaryResponse,
    TransactionItem,
    TransactionListResponse,
)
from app.features.asset.service import build_summary_tts, build_transaction_tts

router = APIRouter(prefix="/api/asset", tags=["asset"])


@router.get("/summary")
def get_asset_summary(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """전체 계좌 목록과 총 자산을 조회합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.

    Returns:
        total_asset(int)과 accounts 목록을 포함한 성공 응답 dict.

    Raises:
        AccountError: 조회할 계좌가 없는 경우 (ACCOUNT_NOT_FOUND).
    """
    accounts = service.get_asset_summary(db, user_id)
    total_asset = sum(a.balance for a in accounts)

    account_items = [
        AccountBalanceItem(
            account_id=str(a.account_id),
            bank_name=a.bank_name,
            account_type=a.account_type,
            alias=a.alias,
            balance=a.balance,
            is_primary=a.is_primary,
        )
        for a in accounts
    ]
    data = AssetSummaryResponse(
        total_asset=total_asset,
        accounts=account_items,
        tts_text=build_summary_tts(accounts, total_asset),
    )

    return {
        "success": True,
        "data": data,
        "message": f"계좌 {len(accounts)}개를 불러왔습니다.",
    }


@router.get("/balance/{account_id}")
def get_account_balance(
    account_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """특정 계좌의 잔액을 조회합니다.

    Args:
        account_id: 조회할 계좌 ID.
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.

    Returns:
        계좌 잔액 정보를 포함한 성공 응답 dict.

    Raises:
        AccountError: 해당 계좌를 찾을 수 없는 경우 (ACCOUNT_NOT_FOUND).
    """
    account = service.get_account_balance(db, user_id, account_id)

    data = AccountBalanceItem(
        account_id=str(account.account_id),
        bank_name=account.bank_name,
        account_type=account.account_type,
        alias=account.alias,
        balance=account.balance,
        is_primary=account.is_primary,
    )

    return {
        "success": True,
        "data": data,
        "message": "잔액을 불러왔습니다.",
    }


@router.get("/history")
def get_transaction_history(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    account_id: str | None = None,
    days: int | None = None,
    period: str | None = None,
    category: str | None = None,
) -> dict:
    """거래 내역을 조회합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.
        account_id: 특정 계좌로 필터링. None이면 전체 계좌 조회.
        days: 조회 기간(일수). period가 있으면 무시.
        period: "이번달"|"지난달"|"최근7일". 지정 시 정확한 월 범위로 필터.
        category: 거래 카테고리로 필터링. None이면 전체 카테고리 조회.

    Returns:
        transactions 목록과 total_count를 포함한 성공 응답 dict.

    Raises:
        AccountError: 거래 내역을 찾을 수 없는 경우 (TX_NOT_FOUND).
    """
    if period:
        since, until = service.period_to_date_range(period)
        transactions = service.get_transaction_history(
            db, user_id, account_id, category=category, since=since, until=until
        )
    else:
        transactions = service.get_transaction_history(
            db, user_id, account_id, days, category
        )

    data = TransactionListResponse(
        transactions=[
            TransactionItem(
                tx_id=str(t.tx_id),
                from_account_id=str(t.from_account_id),
                to_bank_name=t.to_bank_name,
                to_name=t.to_name,
                amount=t.amount,
                tx_type=t.tx_type,
                status=t.status,
                category=t.category,
                memo=t.memo,
                created_at=t.created_at,
                tts_text=build_transaction_tts(t),
            )
            for t in transactions
        ],
        total_count=len(transactions),
    )

    return {
        "success": True,
        "data": data,
        "message": f"거래 내역 {len(transactions)}건을 불러왔습니다.",
    }


@router.get("/expense-summary")
def get_expense_summary(
    days: int = 30,
    period: str | None = None,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """지출 요약을 조회합니다 (총액 및 카테고리 Top 5).

    Args:
        days: 조회 기간(일수). 기본 30일. period가 있으면 무시.
        period: "이번달"|"지난달"|"최근7일". 지정 시 정확한 월 범위로 필터.
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.

    Returns:
        total, days, top_categories 를 포함한 성공 응답 dict.

    Raises:
        HistoryError: 지출 내역이 없는 경우 (TX_NOT_FOUND).
    """
    if period:
        since, until = service.period_to_date_range(period)
        summary = service.get_expense_summary(db, user_id, since=since, until=until)
    else:
        summary = service.get_expense_summary(db, user_id, days)

    data = ExpenseSummaryResponse(
        total=summary["total"],
        days=summary["days"],
        top_categories=[
            CategoryItem(category=c["category"], amount=c["amount"])
            for c in summary["top_categories"]
        ],
    )

    return {
        "success": True,
        "data": data,
        "message": f"최근 {days}일 지출 요약입니다.",
    }


@router.get("/compare")
def get_compare(
    period: str = "이번달",
    compare_period: str = "지난달",
    category: str | None = None,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """두 기간의 지출을 비교합니다. (compare 화면 전용)

    Args:
        period: 기준 기간. 기본 "이번달".
        compare_period: 비교 기간. 기본 "지난달".
        category: 카테고리 필터. None이면 전체 지출 비교.
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.

    Returns:
        period_amount, compare_amount, diff 를 포함한 성공 응답 dict.
    """
    data = service.get_compare_data(db, user_id, period, compare_period, category)
    return {"success": True, "data": data, "message": "비교 결과입니다."}
