import uuid

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.auto_transfer import service
from app.features.auto_transfer.schema import (
    AutoTransferMemoRequest,
    AutoTransferRequest,
    StatusUpdateRequest,
)
from app.models.account import Account

router = APIRouter(prefix="/api/auto-transfer", tags=["자동이체"])


def _mask(account_number: str) -> str:
    if len(account_number) <= 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]


@router.get("/accounts", response_model=dict)
def list_from_accounts(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체 출금 가능 계좌 목록을 반환합니다. (주계좌 우선 정렬)"""
    accounts = (
        db.query(Account)
        .filter(Account.user_id == uuid.UUID(user_id))
        .order_by(Account.is_primary.desc())
        .all()
    )
    return {
        "success": True,
        "data": [
            {
                "accountId": a.account_id,
                "bankName": a.bank_name,
                "accountMasked": _mask(a.account_number),
                "balance": a.balance,
                "alias": a.alias or a.account_type,
                "isPrimary": a.is_primary,
            }
            for a in accounts
        ],
        "message": "계좌 목록을 조회했습니다.",
    }


@router.post("", response_model=dict)
def register(
    data: AutoTransferRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체를 등록합니다.

    PIN 검증 통과 후 StandingOrder가 생성되며 status='active'로 시작합니다.
    PHONE / DIRECT 모드는 RegisteredRecipient를 자동 생성합니다.
    """
    result = service.register_auto_transfer(db, user_id, data)
    return {
        "success": True,
        "data": result.model_dump(by_alias=True),
        "message": "자동이체가 등록되었습니다.",
    }


@router.get("", response_model=dict)
def list_orders(
    status: str | None = Query(
        default=None, description="'active' | 'paused' | 'cancelled'"
    ),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체 목록을 조회합니다.

    status 파라미터로 'active' / 'paused' / 'cancelled' 필터링이 가능합니다.
    미지정 시 전체를 등록일 내림차순으로 반환합니다.
    """
    items = service.list_auto_transfers(db, user_id, status)
    return {
        "success": True,
        "data": [item.model_dump(by_alias=True) for item in items],
        "message": "자동이체 목록을 조회했습니다.",
    }


@router.post("/execute", response_model=dict)
def execute(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """오늘 실행 예정인 자동이체를 일괄 실행합니다.

    에이전트 툴과 스케줄러(APScheduler) 양쪽에서 호출합니다.
    JWT 기반 본인 자동이체만 실행합니다.
    """
    result = service.run_due_auto_transfers(db, user_id)
    success = result["success"]
    failed = result["failed"]
    total = result["total"]
    return {
        "success": True,
        "data": result,
        "message": (
            f"자동이체 {total}건 중 {success}건 완료"
            + (f", {failed}건 잔액 부족으로 실패." if failed else ".")
        ),
    }


@router.patch("/{order_id}/status", response_model=dict)
def update_status(
    order_id: str = Path(..., description="상태를 변경할 자동이체 ID"),
    body: StatusUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체 상태를 변경합니다 (일시정지 / 재개 / 해지).

    허용 전환: active→paused/cancelled, paused→active/cancelled.
    cancelled 상태는 복구 불가입니다.
    """
    result = service.update_status(db, user_id, order_id, body)
    return {
        "success": True,
        "data": result.model_dump(by_alias=True),
        "message": "자동이체 상태가 변경되었습니다.",
    }


@router.post("/{order_id}/memo", response_model=dict)
def save_memo(
    order_id: str = Path(..., description="메모를 저장할 자동이체 ID"),
    body: AutoTransferMemoRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """자동이체 건에 메모를 사후 저장합니다.

    standing_orders.label 컬럼에 저장됩니다. (예: '월세', '공과금', '용돈')
    메모는 100자 이하이며 선택 항목입니다.
    본인 자동이체가 아닌 orderId 요청 시 404를 반환합니다.
    """
    result = service.update_memo(db, user_id, order_id, body)
    return {
        "success": True,
        "data": result.model_dump(by_alias=True),
        "message": "메모가 저장되었습니다.",
    }
