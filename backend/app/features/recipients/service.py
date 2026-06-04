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

import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exception import RecipientError
from app.features.recipients.schema import ResolvedRecipient, ContactItem
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.user import User
from app.shared.crypto import decrypt, encrypt

logger = logging.getLogger(__name__)

_ACCOUNT_DIGITS_RE = re.compile(r"^\d{10,14}$")


def normalize_account_digits(value: str) -> str | None:
    """계좌번호 문자열을 숫자만 10~14자리로 정규화한다. 형식이 맞지 않으면 None."""
    cleaned = value.replace("-", "").replace(" ", "")
    if _ACCOUNT_DIGITS_RE.fullmatch(cleaned):
        return cleaned
    return None


def match_by_registered_account(
    db: Session,
    user_uuid: uuid.UUID,
    account_digits: str,
) -> RegisteredRecipient | None:
    """등록 수취인 중 계좌번호가 일치하는 행을 찾는다.

    암호화 저장으로 DB equality 조회가 불가해 복호화 후 비교한다.
    0건·2건 이상이면 None (동일 계좌 중복 등록 시 별명으로 재질문 유도).
    """
    digits = normalize_account_digits(account_digits)
    if not digits:
        return None

    matches: list[RegisteredRecipient] = []
    rows = (
        db.query(RegisteredRecipient)
        .filter(RegisteredRecipient.user_id == user_uuid)
        .all()
    )
    for row in rows:
        plain = decrypt(row.account_number)
        if plain and normalize_account_digits(plain) == digits:
            matches.append(row)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning(
            "account_digits matched multiple registered recipients user=%s",
            user_uuid,
        )
    return None


def resolve_by_registered_account(
    db: Session,
    user_uuid: uuid.UUID,
    account_digits: str,
) -> ResolvedRecipient | None:
    """등록된 계좌번호로 수취인을 조회한다. 미등록이면 None."""
    row = match_by_registered_account(db, user_uuid, account_digits)
    if row is None:
        return None
    return resolve_by_id(db, user_uuid, str(row.recipient_id))


def resolve_direct_account(
    account_digits: str,
    bank_name: str,
    recipient_name: str | None = None,
) -> ResolvedRecipient | None:
    """미등록 계좌 직접 이체용 ResolvedRecipient를 만든다."""
    digits = normalize_account_digits(account_digits)
    if not digits or not bank_name.strip():
        return None
    return ResolvedRecipient(
        recipient_id=None,
        bank_name=bank_name.strip(),
        account_number=digits,
        recipient_name=recipient_name or "수취인",
    )


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
            user_message="등록된 수취인을 찾을 수 없습니다.",
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
            user_message="가입되지 않은 전화번호입니다. 수취 계좌번호와 은행명을 직접 입력해 주세요.",
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
            user_message="수취인의 계좌를 찾을 수 없습니다. 계좌번호와 은행명을 직접 입력해 주세요.",
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


def _normalize_phone_digits(value: str) -> str | None:
    """전화번호에서 숫자만 추출 (01x 10~11자리)."""
    cleaned = value.replace("-", "").replace(" ", "")
    if re.fullmatch(r"01[0-9]{8,9}", cleaned):
        return cleaned
    return None


def match_by_phone_alias(
    db: Session,
    user_uuid: uuid.UUID,
    phone: str,
) -> RegisteredRecipient | None:
    """등록 수취인 별칭이 전화번호(숫자만 동일)인 경우 1건을 반환한다."""
    digits = _normalize_phone_digits(phone)
    if not digits:
        return None

    rows = (
        db.query(RegisteredRecipient)
        .filter(RegisteredRecipient.user_id == user_uuid)
        .all()
    )
    matches: list[RegisteredRecipient] = []
    for row in rows:
        alias_digits = _normalize_phone_digits(row.alias)
        if alias_digits == digits:
            matches.append(row)
        elif row.alias.replace("-", "").replace(" ", "") == digits:
            matches.append(row)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning(
            "phone alias matched multiple registered recipients user=%s",
            user_uuid,
        )
    return None


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

    logger.info("alias '%s' classified as '%s'", alias, kind)

    if kind == "phone":
        registered = match_by_phone_alias(db, user_uuid, alias)
        if registered is not None:
            return resolve_by_id(db, user_uuid, str(registered.recipient_id))
        try:
            cleaned = alias.replace("-", "").replace(" ", "")
            if len(cleaned) == 11:
                formatted = f"{cleaned[:3]}-{cleaned[3:7]}-{cleaned[7:]}"
            elif len(cleaned) == 10:
                formatted = f"{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"
            else:
                formatted = cleaned
            return resolve_by_phone(db, formatted)
        except RecipientError:
            return None

    if kind == "account":
        # 등록 수취인 계좌면 bank_name·recipient_id를 DB에서 채운다.
        # 미등록 계좌는 graph가 bank_name 수집 후 resolve_direct_account로 처리한다.
        return resolve_by_registered_account(db, user_uuid, alias)

    # kind == "name": alias 또는 실명으로 검색
    matches = match_by_name(db, user_uuid, alias)
    if len(matches) != 1:
        # 0명 또는 동명이인 → None (재입력 유도)
        return None
    return resolve_by_id(db, user_uuid, str(matches[0].recipient_id))


def sync_device_contacts(
    db: Session,
    user_uuid: uuid.UUID,
    contacts: list[ContactItem],
) -> int:
    """디바이스 연락처를 받아 가입된 사용자인 경우 수취인으로 자동 등록합니다.

    Args:
        db: 데이터베이스 세션.
        user_uuid: 요청 사용자 UUID.
        contacts: 연락처 목록 (name, phone).

    Returns:
        새로 등록된 수취인 수.
    """
    added_count = 0

    # 내 수취인 이름(alias) 목록 (중복 방지용)
    existing_aliases = {
        r.alias
        for r in db.query(RegisteredRecipient)
        .filter(RegisteredRecipient.user_id == user_uuid)
        .all()
    }

    # 1. 모든 연락처의 전화번호 정규화 및 매핑 준비
    contact_map = {}
    for c in contacts:
        if not c.phone or not c.name:
            continue

        try:
            phone_digits = re.sub(r"\D", "", c.phone)
            if phone_digits.startswith("82"):
                phone_digits = "0" + phone_digits[2:]

            # 빈 번호 필터링
            if not phone_digits:
                continue

            contact_map[phone_digits] = c.name
        except Exception:
            # 정규표현식 파싱 중 오류 발생 시 해당 연락처 건너뜀
            continue

    phone_list = list(contact_map.keys())
    if not phone_list:
        return 0

    # 2. 우리 톡 뱅킹 가입자 한번에 검색 (IN 절)
    target_users = db.query(User).filter(User.phone.in_(phone_list)).all()
    if not target_users:
        return 0

    user_ids = [u.user_id for u in target_users]

    # 3. 해당 가입자들의 주계좌 한번에 검색 (IN 절)
    primary_accounts = (
        db.query(Account)
        .filter(Account.user_id.in_(user_ids), Account.is_primary.is_(True))
        .all()
    )
    account_by_user = {a.user_id: a for a in primary_accounts}

    # 4. 필터링 및 일괄 등록
    for user in target_users:
        primary_account = account_by_user.get(user.user_id)
        if not primary_account:
            continue

        contact_name = contact_map.get(user.phone)
        if not contact_name or contact_name in existing_aliases:
            continue

        recipient = RegisteredRecipient(
            user_id=user_uuid,
            alias=contact_name,
            bank_name=primary_account.bank_name,
            account_number=primary_account.account_number,
            recipient_name=user.name,
        )
        db.add(recipient)
        existing_aliases.add(contact_name)
        added_count += 1

    db.commit()
    return added_count


def lookup_recipient_for_transfer(
    db: Session,
    user_uuid: uuid.UUID,
    recipient: str,
    bank_name: str | None = None,
) -> ResolvedRecipient | None:
    """이체 resolve용 조회 — 계좌·은행명 조합을 포함한다."""
    kind = classify_recipient_input(recipient)
    if kind == "account":
        registered = resolve_by_registered_account(db, user_uuid, recipient)
        if registered is not None:
            return registered
        if bank_name and bank_name.strip():
            return resolve_direct_account(recipient, bank_name.strip())
        return None
    return lookup_recipient_by_voice(db, user_uuid, recipient)


def find_recipient_by_voice(
    user_id: str,
    recipient: str,
    bank_name: str | None = None,
) -> ResolvedRecipient | None:
    """음성 발화 수취인 조회 — DB 세션을 내부에서 관리하는 에이전트용 래퍼.

    graph.py의 resolve_node에서 호출한다.

    Args:
        user_id: 요청 사용자 UUID 문자열.
        recipient: 수취인 이름·별명·전화번호·계좌번호.
        bank_name: 미등록 계좌 직접 이체 시 수집된 은행명.

    Returns:
        ResolvedRecipient (찾은 경우), None (없는 경우).
    """
    db = next(get_db())
    try:
        return lookup_recipient_for_transfer(
            db, uuid.UUID(user_id), recipient, bank_name=bank_name
        )
    except Exception:
        logger.exception("find_recipient_by_voice failed user=%s", user_id)
        return None
    finally:
        db.close()
