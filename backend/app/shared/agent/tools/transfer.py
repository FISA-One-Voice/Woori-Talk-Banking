"""이체 에이전트 tool — execute_transfer / add_note / get_transfer_history."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError
from app.features.recipients.service import (
    lookup_recipient_for_transfer,
    resolve_by_id,
    resolve_direct_account,
)
from app.features.transfer import service as transfer_service

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))


def run_execute_transfer(
    user_id: str,
    recipient: str,
    amount: int,
    *,
    collected_slots: dict | None = None,
) -> tuple[str, str | None]:
    """이체를 실행하고 (TTS 메시지, tx_id)를 반환한다.

    execute_node에서 tx_id를 세션 상태에 저장할 때 사용한다.
    collected_slots에 resolve 결과(recipient_id, account_number, bank_name)가 있으면
    이름 재조회 없이 이체한다.
    """
    db = next(get_db())
    slots = collected_slots or {}
    try:
        user_uuid = uuid.UUID(user_id)
        resolved = None

        recipient_id = slots.get("recipient_id")
        if recipient_id:
            resolved = resolve_by_id(db, user_uuid, str(recipient_id))
        elif slots.get("account_number") and slots.get("bank_name"):
            resolved = resolve_direct_account(
                str(slots["account_number"]),
                str(slots["bank_name"]),
                recipient_name=str(slots.get("recipient") or recipient or "수취인"),
            )
        else:
            resolved = lookup_recipient_for_transfer(
                db,
                user_uuid,
                recipient,
                bank_name=str(slots["bank_name"]) if slots.get("bank_name") else None,
            )

        if resolved is None:
            return f"{recipient}님을 찾을 수 없습니다. 다시 확인해 주세요.", None

        display_name = str(
            slots.get("recipient") or recipient or resolved.recipient_name
        )
        receipt = transfer_service.execute_transfer(
            db=db,
            user_id=user_id,
            recipient=resolved.account_number,
            bank_name=resolved.bank_name,
            amount=amount,
            idempotency_key=str(uuid.uuid4()),
            recipient_name=resolved.recipient_name,
            recipient_id=str(resolved.recipient_id) if resolved.recipient_id else None,
        )
        tx_id = receipt["txId"]
        return f"{display_name}님께 {amount:,}원 이체가 완료되었습니다.", tx_id
    except AppError as e:
        logger.warning("execute_transfer AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message, None
    except Exception as e:
        logger.error("execute_transfer 실패: user=%s error=%s", user_id, e)
        return "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", None
    finally:
        db.close()


@tool
def execute_transfer(
    user_id: str,
    recipient: str,
    amount: int,
    memo: str | None = None,
) -> str:
    """등록된 수취인에게 금액을 이체합니다.

    슬롯이 모두 수집되고 음성 인증이 완료된 뒤 execute_node에서 호출됩니다.
    '이체해줘', '보내줘', '송금해줘' 요청에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        recipient: 수취인 이름 (resolve_node에서 정규화된 값).
        amount: 이체 금액 (원 단위 정수).
        memo: 이체 메모 (선택, 사용자가 언급한 경우에만 전달).

    Returns:
        TTS 친화적 이체 완료 안내 문자열.
    """
    message, _ = run_execute_transfer(user_id, recipient, amount)
    return message


@tool
def add_note(user_id: str, memo: str, tx_id: str) -> str:
    """지정한 이체 거래(tx_id)에 메모를 추가합니다.

    '방금 이체에 메모 달아줘' 등의 말에 사용합니다.
    tx_id는 이체 직후 세션(last_tx_id) 또는 슬롯에서 전달받습니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        memo: 추가할 메모 내용.
        tx_id: 메모를 붙일 트랜잭션 ID (UUID 문자열).

    Returns:
        TTS 친화적 메모 완료 안내 문자열.
    """
    db = next(get_db())
    try:
        transfer_service.update_memo(db=db, user_id=user_id, tx_id=tx_id, memo=memo)
        return f"'{memo}' 메모가 추가되었습니다."
    except AppError as e:
        logger.warning("add_note AppError: user=%s code=%s", user_id, e.code)
        return e.user_message or e.message
    except Exception as e:
        logger.error("add_note 실패: user=%s tx_id=%s error=%s", user_id, tx_id, e)
        return "메모 추가 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()


@tool
def get_transfer_history(user_id: str, days: int = 30) -> str:
    """최근 이체 내역(일반이체 + 자동이체)을 메모와 함께 조회합니다.

    '내 이체 내역 알려줘', '자동이체 뭐 있어', '최근에 누구한테 보냈어' 등에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        days: 조회 기간(일수, 기본 30일).

    Returns:
        TTS 친화적 이체 내역 요약 문자열.
    """
    db = next(get_db())
    try:
        user_uuid = uuid.UUID(user_id)
        since = datetime.now(_KST).replace(tzinfo=None) - timedelta(days=days)

        txs = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_uuid,
                Transaction.status == "completed",
                Transaction.tx_type.in_(["transfer", "auto_transfer"]),
                Transaction.created_at >= since,
            )
            .order_by(Transaction.created_at.desc())
            .limit(10)
            .all()
        )

        if not txs:
            return f"최근 {days}일간 이체 내역이 없습니다."

        parts = []
        for tx in txs:
            type_label = "자동이체" if tx.tx_type == "auto_transfer" else "이체"
            name = tx.to_name or "수취인"
            text = f"{name}에게 {tx.amount:,}원 {type_label}"
            if tx.memo:
                text += f", 메모 '{tx.memo}'"
            parts.append(text)

        return f"이체 내역 알려드리겠습니다. 최근 {len(txs)}건입니다. " + ". ".join(parts) + "."
    except Exception as e:
        logger.error("get_transfer_history 실패: user=%s error=%s", user_id, e)
        return "이체 내역 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()
