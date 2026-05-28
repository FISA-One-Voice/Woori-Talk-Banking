"""수취인 API 라우터."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.recipients import service
from app.models.recipient import RegisteredRecipient

router = APIRouter(prefix="/api", tags=["수취인"])


class RecipientItem(BaseModel):
    """등록 수취인 단건 응답 스키마."""

    model_config = ConfigDict(populate_by_name=True)

    recipient_id: str = Field(alias="recipientId")
    alias: str
    recipient_name: str = Field(alias="recipientName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")


def _mask_account(account_number: str) -> str:
    """계좌번호 뒤 4자리를 제외하고 마스킹합니다."""
    if len(account_number) <= 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]


def _to_item(r: RegisteredRecipient) -> dict:
    from app.shared.crypto import decrypt

    plain = decrypt(r.account_number) or ""
    return RecipientItem(
        recipient_id=str(r.recipient_id),
        alias=r.alias,
        recipient_name=r.recipient_name,
        bank_name=r.bank_name,
        account_masked=_mask_account(plain),
    ).model_dump(by_alias=True)


@router.get("/recipients", response_model=dict)
def list_recipients(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """로그인한 사용자의 등록 수취인 목록을 반환합니다.

    Args:
        db: 데이터베이스 세션 (의존성 주입).
        user_id: JWT에서 추출한 사용자 ID.

    Returns:
        등록 수취인 목록 (최신 등록순, 계좌번호 마스킹).
    """
    recipients = (
        db.query(RegisteredRecipient)
        .filter(RegisteredRecipient.user_id == uuid.UUID(user_id))
        .order_by(RegisteredRecipient.created_at.desc())
        .all()
    )
    return {
        "success": True,
        "data": [_to_item(r) for r in recipients],
        "message": "수취인 목록을 조회했습니다.",
    }


@router.get("/contacts/match", response_model=dict)
def match_contacts(
    name: str = Query(..., description="검색할 수취인 이름 또는 별칭"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """이름 또는 별칭으로 등록 수취인을 검색합니다.

    음성 발화에서 추출한 이름으로 수취인을 찾을 때 사용합니다.
    결과가 여러 명이면 동명이인(CONTACT_AMBIGUOUS) 처리를 위해 전체 목록을 반환합니다.

    Args:
        name: 검색할 수취인 이름 또는 별칭 (부분 일치).
        db: 데이터베이스 세션 (의존성 주입).
        user_id: JWT에서 추출한 사용자 ID.

    Returns:
        매칭된 수취인 목록 (계좌번호 마스킹). 없으면 빈 리스트.
    """
    matched = service.match_by_name(db, uuid.UUID(user_id), name)
    return {
        "success": True,
        "data": {"matched": [_to_item(r) for r in matched]},
        "message": f"{len(matched)}명의 수취인을 찾았습니다.",
    }
