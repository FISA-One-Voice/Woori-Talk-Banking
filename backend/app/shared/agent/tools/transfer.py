"""이체 에이전트 tool — execute_transfer / add_note / get_transfer_history."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.recipients.service import lookup_recipient_by_voice
from app.features.transfer import service as transfer_service
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))


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
    db = next(get_db())
    try:
        resolved = lookup_recipient_by_voice(db, uuid.UUID(user_id), recipient)
        if resolved is None:
            return f"{recipient}님을 찾을 수 없습니다. 다시 확인해 주세요."

        transfer_service.execute_transfer(
            db=db,
            user_id=user_id,
            recipient=resolved.account_number,
            bank_name=resolved.bank_name,
            amount=amount,
            idempotency_key=str(uuid.uuid4()),
            recipient_name=resolved.recipient_name,
            recipient_id=str(resolved.recipient_id) if resolved.recipient_id else None,
            memo=memo,
        )
        result = f"{recipient}님께 {amount:,}원 이체가 완료되었습니다."
        if memo:
            result += f" 메모 '{memo}'가 저장되었습니다."
        return result
    except Exception as e:
        logger.error("execute_transfer 실패: user=%s error=%s", user_id, e)
        return "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()


@tool
def add_note(user_id: str, memo: str) -> str:
    """가장 최근 이체 완료 건(일반이체 또는 자동이체)에 메모를 추가합니다.

    '방금 이체에 메모 달아줘', '마지막 이체 메모 추가해줘' 등의 말에 사용합니다.
    memo 슬롯이 수집되면 execute_node에서 호출됩니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        memo: 추가할 메모 내용.

    Returns:
        TTS 친화적 메모 완료 안내 문자열.
    """
    db = next(get_db())
    try:
        user_uuid = uuid.UUID(user_id)
        tx = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_uuid,
                Transaction.status == "completed",
                Transaction.tx_type.in_(["transfer", "auto_transfer"]),
            )
            .order_by(Transaction.created_at.desc())
            .first()
        )
        if tx is None:
            return "최근 이체 내역이 없습니다."

        transfer_service.update_memo(db=db, user_id=user_id, tx_id=tx.tx_id, memo=memo)
        return f"'{memo}' 메모가 추가되었습니다."
    except Exception as e:
        logger.error("add_note 실패: user=%s error=%s", user_id, e)
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
