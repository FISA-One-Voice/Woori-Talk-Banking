from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.account import service
from app.features.account.schema import (
    AccountDetail,
    AccountSummaryItem,
    AccountSummaryResponse,
    AccountListResponse,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

# JWT 구현 전 임시 고정 user_id
TEMP_USER_ID = "ff49c2a0-9b82-4c4f-9f61-d39930b16dd6"


@router.get("/summary")
def get_account_summary(db: Session = Depends(get_db)):
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
    accounts = service.get_user_accounts(db, TEMP_USER_ID)

    data = AccountListResponse(
        accounts=[
            AccountSummaryItem(
                account_id=str(a.account_id),
                bank=a.bank_name,
                last4=a.account_number[-4:] if a.account_number else "****",
                alias=a.alias,
                balance=a.balance,
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