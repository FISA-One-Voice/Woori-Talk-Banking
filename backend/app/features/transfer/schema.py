"""이체 API Pydantic 스키마."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient: str = Field(
        ..., alias="recipient", description="계좌번호 (10~14자리 숫자)"
    )
    bank_name: str = Field(..., alias="bankName")
    amount: int = Field(..., alias="amount", gt=0)
    idempotency_key: str = Field(
        ..., alias="idempotencyKey", min_length=1, max_length=100
    )
    recipient_name: Optional[str] = Field(None, alias="recipientName")
    recipient_id: Optional[str] = Field(None, alias="recipientId")


class MemoUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    memo: str = Field(..., alias="memo", max_length=255)
