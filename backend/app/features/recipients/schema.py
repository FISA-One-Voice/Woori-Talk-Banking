"""수취인 공통 타입 정의."""

from dataclasses import dataclass
from pydantic import BaseModel


@dataclass(frozen=True)
class ResolvedRecipient:
    """수취인 경로 해석 결과.

    이체(transfer)와 자동이체(auto_transfer) 양쪽에서 공통으로 사용합니다.
    account_number는 항상 평문으로 반환됩니다.

    Attributes:
        recipient_id: 등록 수취인 ID. 전화번호·직접입력 경로는 None.
        bank_name: 수취 은행명.
        account_number: 수취 계좌번호 (평문).
        recipient_name: 수취인 이름.
    """

    recipient_id: str | None
    bank_name: str
    account_number: str
    recipient_name: str | None


class ContactItem(BaseModel):
    """디바이스 연락처 단건 아이템.

    Attributes:
        name: 기기에 저장된 이름.
        phone: 기기에 저장된 전화번호.
    """

    name: str
    phone: str


class SyncContactsRequest(BaseModel):
    """디바이스 연락처 동기화 요청 스키마.

    Attributes:
        contacts: 전송할 연락처 목록.
    """

    contacts: list[ContactItem]
