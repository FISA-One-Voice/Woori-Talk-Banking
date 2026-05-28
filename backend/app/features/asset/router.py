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
# =============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.asset import service
from app.features.asset.schema import (
    AccountBalanceItem,
    AssetSummaryResponse,
    TransactionItem,
    TransactionListResponse,
)

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

    data = AssetSummaryResponse(
        total_asset=total_asset,
        accounts=[
            AccountBalanceItem(
                account_id=str(a.account_id),
                bank_name=a.bank_name,
                account_type=a.account_type,
                alias=a.alias,
                balance=a.balance,
                is_primary=a.is_primary,
            )
            for a in accounts
        ],
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
    category: str | None = None,
) -> dict:
    """거래 내역을 조회합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: JWT에서 추출한 인증 사용자 ID.
        account_id: 특정 계좌로 필터링. None이면 전체 계좌 조회.
        days: 조회 기간(일수). None이면 전체 기간 조회.
        category: 거래 카테고리로 필터링. None이면 전체 카테고리 조회.

    Returns:
        transactions 목록과 total_count를 포함한 성공 응답 dict.

    Raises:
        AccountError: 거래 내역을 찾을 수 없는 경우 (TX_NOT_FOUND).
    """
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
