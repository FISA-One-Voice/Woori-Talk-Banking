# =============================================================================
# backend/app/features/account/router.py
#
# [이 파일의 역할]
# "어떤 URL 로 요청이 오면 어떤 함수를 실행할지" 를 정의합니다.
#
# [엔드포인트 목록]
# GET /api/accounts/summary → 계좌 목록 + 총 자산 조회
# GET /api/accounts/list    → 출금 가능 계좌 목록 조회 (송금용)
# =============================================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.account import service
from app.features.account.schema import (
    AccountDetail,
    AccountListResponse,
    AccountSummaryItem,
    AccountSummaryResponse,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/summary")
def get_account_summary(db: Session = Depends(get_db)):
    """
    계좌 목록 및 총 자산 조회.

    GET /api/accounts/summary
    성공: {"success": true, "data": {"totalAsset": int, "accounts": [...]}, "message": "..."}
    실패: {"success": false, "data": null, "message": "...", "error_code": "ACCOUNT_NOT_FOUND"}
    """
    accounts = service.get_user_accounts(db, TEMP_USER_ID)
    total_asset = sum(a.balance for a in accounts)

    data = AccountSummaryResponse(
        totalAsset=total_asset,
        accounts=[
            AccountDetail(
                account_id=str(a.account_id),
                bank_name=a.bank_name,
                account_number=a.account_number,
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
        "error_code": None,
    }


@router.get("/list")
def get_account_list(db: Session = Depends(get_db)):
    """
    출금 가능 계좌 목록 조회 (송금 화면에서 계좌 선택용).

    GET /api/accounts/list
    성공: {"success": true, "data": {"accounts": [...]}, "message": "..."}
    실패: {"success": false, "data": null, "message": "...", "error_code": "ACCOUNT_NOT_FOUND"}
    """
    accounts = service.get_user_accounts(db, TEMP_USER_ID)

    data = AccountListResponse(
        accounts=[
            AccountSummaryItem(
                account_id=str(a.account_id),
                bank=a.bank_name,
                last4=a.account_number[-4:] if a.account_number else "****",
                alias=a.alias,
                balance=a.balance,
                is_primary=a.is_primary,
            )
            for a in accounts
        ]
    )

    return {
        "success": True,
        "data": data,
        "message": f"출금 가능 계좌 {len(accounts)}개를 불러왔습니다.",
        "error_code": None,
    }