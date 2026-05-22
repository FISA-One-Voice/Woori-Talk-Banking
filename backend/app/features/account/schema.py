from pydantic import BaseModel


class AccountDetail(BaseModel):
    account_id: str
    bank_name: str
    account_number: str
    account_type: str | None
    alias: str | None
    balance: int

    class Config:
        from_attributes = True


class AccountSummaryItem(BaseModel):
    account_id: str
    bank: str
    last4: str
    alias: str | None
    balance: int


class AccountSummaryResponse(BaseModel):
    totalAsset: int
    accounts: list[AccountDetail]


class AccountListResponse(BaseModel):
    accounts: list[AccountSummaryItem]