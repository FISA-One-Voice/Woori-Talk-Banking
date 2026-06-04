from pydantic import BaseModel, ConfigDict, Field, model_validator


class AutoTransferRequest(BaseModel):
    """POST /api/auto-transfer 요청 바디.

    수취인 지정 2가지 방법 (XOR — 정확히 하나만 허용):
        1. recipientId     — 등록 즐겨찾기 UUID (에이전트가 별명→ID 변환 후 전달)
        2. toAccountNumber — 계좌번호 직접 입력 (bankName, toName 필수)

    DIRECT 모드(toAccountNumber)는 내부적으로 RegisteredRecipient를 자동 생성하여
    StandingOrder.recipient_id(nullable=False) 제약을 충족합니다.

    cycle 검증 규칙:
        cycle='monthly' → scheduledDay(1~31) 필수
        cycle='weekly'  → scheduledDow(0~6)  필수  (0=월, 6=일)
    """

    model_config = ConfigDict(populate_by_name=True)

    from_account_id: str = Field(alias="fromAccountId")
    amount: int = Field(gt=0)
    cycle: str
    scheduled_day: int | None = Field(default=None, ge=1, le=31, alias="scheduledDay")
    scheduled_dow: int | None = Field(default=None, ge=0, le=6, alias="scheduledDow")
    password: str | None = Field(default=None)
    terms_agreed: bool = Field(alias="termsAgreed")
    transfer_note: str | None = Field(
        default=None, max_length=100, alias="transferNote"
    )

    # 수취인 지정 2가지 방법 (XOR — 정확히 하나만 허용)
    recipient_id: str | None = Field(default=None, alias="recipientId")
    to_account_number: str | None = Field(default=None, alias="toAccountNumber")

    # DIRECT(toAccountNumber) 모드 추가 필드
    bank_name: str | None = Field(default=None, alias="bankName")
    to_name: str | None = Field(default=None, alias="toName")

    @model_validator(mode="after")
    def validate_recipient_and_cycle(self) -> "AutoTransferRequest":
        """수취인 지정 방법(XOR)과 cycle 스케줄 필드를 검증합니다."""
        provided = [
            v for v in [self.recipient_id, self.to_account_number] if v is not None
        ]
        if len(provided) != 1:
            raise ValueError(
                "recipientId, toAccountNumber 중 정확히 하나만 제공해야 합니다."
            )

        if self.to_account_number is not None:
            if not self.bank_name or not self.to_name:
                raise ValueError(
                    "toAccountNumber 사용 시 bankName과 toName은 필수입니다."
                )

        if self.cycle == "monthly":
            if self.scheduled_day is None:
                raise ValueError("monthly 주기에는 scheduledDay(1~31)가 필요합니다.")
        elif self.cycle == "weekly":
            if self.scheduled_dow is None:
                raise ValueError("weekly 주기에는 scheduledDow(0~6)가 필요합니다.")
        else:
            raise ValueError("cycle은 'monthly' 또는 'weekly'여야 합니다.")

        return self


class AutoTransferResult(BaseModel):
    """POST /api/auto-transfer 성공 응답 data 필드."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    to_name: str | None = Field(alias="toName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")
    amount: int
    cycle: str
    scheduled_day: int | None = Field(default=None, alias="scheduledDay")
    scheduled_dow: int | None = Field(default=None, alias="scheduledDow")
    next_execution_at: str = Field(alias="nextExecutionAt")
    status: str
    transfer_note: str | None = Field(default=None, alias="transferNote")


class AutoTransferListItem(BaseModel):
    """GET /api/auto-transfer 목록 응답 항목 1건."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    to_name: str | None = Field(alias="toName")
    bank_name: str = Field(alias="bankName")
    account_masked: str = Field(alias="accountMasked")
    amount: int
    cycle: str
    scheduled_day: int | None = Field(default=None, alias="scheduledDay")
    scheduled_dow: int | None = Field(default=None, alias="scheduledDow")
    next_execution_at: str | None = Field(default=None, alias="nextExecutionAt")
    status: str
    transfer_note: str | None = Field(default=None, alias="transferNote")
    created_at: str = Field(alias="createdAt")


class StatusUpdateRequest(BaseModel):
    """PATCH /api/auto-transfer/{orderId}/status 요청 바디.

    허용 전환:
        active  → paused / cancelled
        paused  → active / cancelled
        cancelled → 전환 불가
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str


class StatusUpdateResult(BaseModel):
    """PATCH /api/auto-transfer/{orderId}/status 성공 응답 data 필드."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    status: str


class AutoTransferMemoRequest(BaseModel):
    """POST /api/auto-transfer/{orderId}/memo 요청 바디.

    standing_orders.transfer_note 컬럼에 저장되는 이체 메모입니다.
    (예: '월세', '공과금', '용돈')
    transfer/schema.py 의 MemoRequest 와 구분하기 위해 접두사를 붙입니다.
    """

    model_config = ConfigDict(populate_by_name=True)

    transfer_note: str | None = Field(
        default=None, max_length=100, alias="transferNote"
    )


class AutoTransferMemoResult(BaseModel):
    """POST /api/auto-transfer/{orderId}/memo 성공 응답 data 필드."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    transfer_note: str | None = Field(alias="transferNote")
