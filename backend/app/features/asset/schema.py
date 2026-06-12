# =============================================================================
# backend/app/features/asset/schema.py
#
# [이 파일의 역할]
# 자산 화면 API 요청/응답 형태를 Pydantic 모델로 정의합니다.
#
# [스키마 목록]
# AccountBalanceItem      → 계좌별 잔액 정보
# AssetSummaryResponse    → GET /api/asset/summary 응답
# TransactionItem         → 거래 내역 단건
# TransactionListResponse → GET /api/asset/history 응답
# =============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountBalanceItem(BaseModel):
    """계좌별 잔액 정보."""

    model_config = ConfigDict(from_attributes=True)

    account_id: str
    bank_name: str
    account_type: str
    alias: str | None
    balance: int
    is_primary: bool


class AssetSummaryResponse(BaseModel):
    """전체 자산 요약 응답."""

    total_asset: int
    accounts: list[AccountBalanceItem]
    tts_text: str = ""  # 화면 진입 시 재생할 TTS 안내 문구 (백엔드 생성)


class TransactionItem(BaseModel):
    """거래 내역 단건."""

    model_config = ConfigDict(from_attributes=True)

    tx_id: str
    from_account_id: str
    to_bank_name: str
    to_name: str | None
    amount: int
    tx_type: str
    status: str
    category: str | None
    memo: str | None
    created_at: datetime
    tts_text: str = ""  # 카드 탭 시 재생할 TTS 문구 (백엔드 생성)


class TransactionListResponse(BaseModel):
    """거래 내역 목록 응답."""

    transactions: list[TransactionItem]
    total_count: int


class CategoryItem(BaseModel):
    """카테고리별 지출 단건."""

    category: str
    amount: int


class ExpenseSummaryResponse(BaseModel):
    """지출 요약 응답 (총액 + 카테고리 Top 5)."""

    total: int
    days: int
    top_categories: list[CategoryItem]
