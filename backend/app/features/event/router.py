# =============================================================================
# backend/app/features/account/router.py
#
# [이 파일의 역할]
# "어떤 URL 로 요청이 오면 어떤 함수를 실행할지" 를 정의합니다.
# 실제 처리 로직은 service.py 에 있고, 이 파일은 URL ↔ 함수를 연결하기만 합니다.
#
# [다른 파일과의 관계]
# ├─ main.py          → 이 파일의 router 를 앱에 등록합니다.
# ├─ service.py       → 실제 비즈니스 로직 함수를 호출합니다.
# ├─ database.py      → get_db() 로 DB 세션을 주입받습니다.
# └─ schema.py        → 응답 형태를 가져옵니다.
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

# ── 임시 사용자 인증 ────────────────────────────────────────────────────────────
# 실제 서비스에서는 JWT 토큰을 검증해서 로그인한 사용자의 UUID 를 가져와야 합니다.
# auth 모듈이 완성되면 아래 상수를 삭제하고 Depends(get_current_user) 로 교체하세요.
TEMP_USER_ID = "ff49c2a0-9b82-4c4f-9f61-d39930b16dd6"  # TODO: JWT 토큰 검증으로 교체 예정

# ── 라우터 생성 ─────────────────────────────────────────────────────────────────
# prefix="/api/accounts" → 이 파일의 모든 경로 앞에 /api/accounts 가 자동으로 붙습니다.
# tags=["accounts"]      → Swagger UI (localhost:8000/docs) 에서 그룹화됩니다.
router = APIRouter(prefix="/api/accounts", tags=["accounts"])


# ── 엔드포인트 1: 계좌 목록 + 총 자산 조회 ──────────────────────────────────────
@router.get("/summary")
def get_account_summary(db: Session = Depends(get_db)):
    """
    계좌 목록 및 총 자산 조회.

    GET /api/accounts/summary
    성공: {"success": true, "data": {"totalAsset": int, "accounts": [...]}, "message": "..."}
    실패: {"success": false, "data": null, "message": "...", "error_code": "ACCOUNT_NOT_FOUND"}
    """
    accounts = service.get_user_accounts(db, TEMP_USER_ID)

    # 전체 잔액 합산
    total_asset = sum(a.balance for a in accounts)

    # AccountSummaryResponse 형태로 변환
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


# ── 엔드포인트 2: 출금 가능 계좌 목록 조회 ──────────────────────────────────────
@router.get("/list")
def get_account_list(db: Session = Depends(get_db)):
    """
    출금 가능 계좌 목록 조회 (송금 화면에서 계좌 선택용).

    GET /api/accounts/list
    성공: {"success": true, "data": {"accounts": [...]}, "message": "..."}
    실패: {"success": false, "data": null, "message": "...", "error_code": "ACCOUNT_NOT_FOUND"}

    프론트엔드는 error_code 값으로 분기 처리해야 합니다. message 로 분기하면 안 됩니다.
    """
    accounts = service.get_user_accounts(db, TEMP_USER_ID)

    # AccountListResponse 형태로 변환
    # 계좌번호는 뒤 4자리만 노출 (보안)
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