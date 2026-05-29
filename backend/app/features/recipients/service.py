"""수취인 공통 조회·등록 서비스.

이체(transfer)와 자동이체(auto_transfer)에서 공통으로 사용하는
수취인 지정 로직을 제공합니다.

사용 예시:
    from app.features.recipients.service import (
        resolve_by_id,
        resolve_by_phone,
        create_recipient,
        match_by_name,
    )
"""

import re
import uuid

from sqlalchemy.orm import Session

from app.core.exception import RecipientError
from app.features.recipients.schema import ResolvedRecipient
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.user import User
from app.shared.crypto import decrypt, encrypt


def resolve_by_id(
    db: Session,
    user_uuid: uuid.UUID,
    recipient_id: str,
) -> ResolvedRecipient:
    """등록 수취인 ID로 수취 계좌 정보를 조회합니다.

    이체(transfer) REGISTERED 모드에서 사용합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID (본인 소유 수취인만 조회 가능).
        recipient_id: 조회할 등록 수취인 ID.

    Returns:
        ResolvedRecipient (account_number는 평문).

    Raises:
        RecipientError: 수취인이 존재하지 않거나 다른 사용자 소유인 경우
            (RECIPIENT_NOT_FOUND, 404).
    """
    recipient = (
        db.query(RegisteredRecipient)
        .filter(
            RegisteredRecipient.recipient_id == recipient_id,
            RegisteredRecipient.user_id == user_uuid,
        )
        .first()
    )
    if recipient is None:
        raise RecipientError(
            code="RECIPIENT_NOT_FOUND",
            message="등록된 수취인을 찾을 수 없습니다.",
            status_code=404,
        )

    return ResolvedRecipient(
        recipient_id=recipient.recipient_id,
        bank_name=recipient.bank_name,
        account_number=decrypt(recipient.account_number),
        recipient_name=recipient.recipient_name,
    )


def resolve_by_phone(
    db: Session,
    phone: str,
) -> ResolvedRecipient:
    """전화번호로 가입 사용자의 주계좌(is_primary=True)를 조회합니다.

    이체(transfer) PHONE 모드에서 사용합니다.

    Args:
        db: 데이터베이스 세션.
        phone: 수취인 전화번호.

    Returns:
        ResolvedRecipient — recipient_id는 None (등록 수취인 연결 없음).

    Raises:
        RecipientError: 해당 전화번호로 가입된 사용자가 없는 경우
            (TRANSFER_RECIPIENT_NOT_FOUND, 404).
        RecipientError: 가입 사용자의 주계좌가 없는 경우
            (TRANSFER_RECIPIENT_NOT_FOUND, 404).
    """
    target_user = db.query(User).filter(User.phone == phone).first()
    if target_user is None:
        raise RecipientError(
            code="TRANSFER_RECIPIENT_NOT_FOUND",
            message=(
                "가입되지 않은 전화번호입니다. "
                "수취 계좌번호와 은행명을 직접 입력해 주세요."
            ),
            status_code=404,
        )

    primary_account = (
        db.query(Account)
        .filter(
            Account.user_id == target_user.user_id,
            Account.is_primary.is_(True),
        )
        .first()
    )
    if primary_account is None:
        raise RecipientError(
            code="TRANSFER_RECIPIENT_NOT_FOUND",
            message=(
                "수취인의 주계좌를 찾을 수 없습니다. "
                "계좌번호와 은행명을 직접 입력해 주세요."
            ),
            status_code=404,
        )

    return ResolvedRecipient(
        recipient_id=None,
        bank_name=primary_account.bank_name,
        account_number=decrypt(primary_account.account_number),
        recipient_name=target_user.name,
    )



def create_recipient(
    db: Session,
    user_uuid: uuid.UUID,
    alias: str,
    bank_name: str,
    account_number: str,
    recipient_name: str,
) -> ResolvedRecipient:
    """수취인을 등록하고 반환합니다.

    account_number는 AES-256으로 암호화하여 저장합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID.
        alias: 수취인 별칭 (예: "엄마", "회사").
        bank_name: 수취 은행명.
        account_number: 수취 계좌번호 평문 (암호화 저장).
        recipient_name: 수취인 실명.

    Returns:
        ResolvedRecipient (account_number는 평문).
    """
    recipient = RegisteredRecipient(
        user_id=user_uuid,
        alias=alias,
        bank_name=bank_name,
        account_number=encrypt(account_number),
        recipient_name=recipient_name,
    )
    db.add(recipient)
    db.flush()

    return ResolvedRecipient(
        recipient_id=recipient.recipient_id,
        bank_name=recipient.bank_name,
        account_number=decrypt(recipient.account_number),
        recipient_name=recipient.recipient_name,
    )


def match_by_name(
    db: Session,
    user_uuid: uuid.UUID,
    name: str,
) -> list[RegisteredRecipient]:
    """별칭 또는 수취인 이름으로 등록 수취인을 검색합니다.

    음성 발화에서 추출한 이름으로 수취인을 찾을 때 사용합니다.
    동명이인이 여러 명이면 전체 목록을 반환하고, 클라이언트가 TTS로 안내합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID.
        name: 검색할 이름 (alias 또는 recipient_name 부분 일치).

    Returns:
        매칭된 RegisteredRecipient 목록. 없으면 빈 리스트.
    """
    return (
        db.query(RegisteredRecipient)
        .filter(
            RegisteredRecipient.user_id == user_uuid,
            RegisteredRecipient.alias.ilike(f"%{name}%")
            | RegisteredRecipient.recipient_name.ilike(f"%{name}%"),
        )
        .order_by(RegisteredRecipient.created_at.desc())
        .all()
    )


def classify_recipient_input(value: str) -> str:
    """음성에서 추출한 수취인 입력값의 형식을 분류합니다.

    Args:
        value: alias 슬롯 값 ("엄마", "01012345678", "110-123-456789" 등).

    Returns:
        "phone" | "account" | "name"
    """
    cleaned = value.replace("-", "").replace(" ", "")
    if re.fullmatch(r"01[0-9]{8,9}", cleaned):
        return "phone"
    if re.fullmatch(r"\d{10,14}", cleaned):
        return "account"
    return "name"


def lookup_recipient_by_voice(
    db: Session,
    user_uuid: uuid.UUID,
    alias: str,
) -> ResolvedRecipient | None:
    """음성 발화에서 추출한 수취인 정보를 분류하고 조회합니다.

    classify_recipient_input()으로 입력 형식을 판별한 뒤
    형식에 맞는 서비스 함수를 호출합니다.
    동명이인이 여러 명이거나 조회에 실패하면 None을 반환합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID.
        alias: alias 슬롯 값 (이름, 전화번호, 계좌번호 모두 허용).

    Returns:
        ResolvedRecipient (찾은 경우), None (못 찾은 경우).
    """
    kind = classify_recipient_input(alias)

    if kind == "phone":
        try:
            return resolve_by_phone(db, alias)
        except RecipientError:
            return None

    if kind == "account":
        # 계좌번호 직접 이체는 은행명 슬롯 별도 수집이 필요하므로 현재 미지원.
        # 이름/별명 재입력 유도.
        return None

    # kind == "name": alias 또는 실명으로 검색
    matches = match_by_name(db, user_uuid, alias)
    if len(matches) != 1:
        # 0명 또는 동명이인 → None (재입력 유도)
        return None
    return resolve_by_id(db, user_uuid, str(matches[0].recipient_id))
