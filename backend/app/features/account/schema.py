# =============================================================================
# backend/app/features/account/schema.py
#
# [이 파일의 역할]
# API 요청/응답의 데이터 형태를 Pydantic 모델로 정의합니다.
# ORM 객체(DB 행)를 API 응답 JSON 으로 변환하는 중간 다리 역할을 합니다.
# =============================================================================

from pydantic import BaseModel


class AccountDetail(BaseModel):
    """
    계좌 상세 정보.
    /api/accounts/summary 에서 계좌 목록의 각 항목으로 사용됩니다.
    """

    account_id: str
    bank_name: str
    account_number: str
    account_type: str          # 필수값으로 변경 (모델에서 nullable=False)
    alias: str | None
    balance: int
    is_primary: bool           # 기본 계좌 여부 추가

    class Config:
        from_attributes = True


class AccountSummaryItem(BaseModel):
    """
    계좌 간략 정보.
    /api/accounts/list 에서 송금 계좌 선택용으로 사용됩니다.
    계좌번호는 뒤 4자리(last4)만 노출합니다.
    """

    account_id: str
    bank: str
    last4: str
    alias: str | None
    balance: int
    is_primary: bool           # 기본 계좌 여부 추가


class AccountSummaryResponse(BaseModel):
    """
    /api/accounts/summary 최종 응답 형태.
    totalAsset: 보유 계좌 잔액 합산
    accounts: 계좌 상세 목록
    """

    totalAsset: int
    accounts: list[AccountDetail]


class AccountListResponse(BaseModel):
    """
    /api/accounts/list 최종 응답 형태.
    송금 화면에서 출금 계좌 선택용으로 사용됩니다.
    """

    accounts: list[AccountSummaryItem]