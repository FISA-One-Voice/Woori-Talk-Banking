"""이체 에이전트 tool — execute_transfer / add_note."""

import logging
import uuid

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.recipients.service import lookup_recipient_by_voice
from app.features.transfer import service as transfer_service

logger = logging.getLogger(__name__)


def run_execute_transfer(
    user_id: str, recipient: str, amount: int
) -> tuple[str, str | None]:
    """이체를 실행하고 (TTS 메시지, tx_id)를 반환한다.

    execute_node에서 tx_id를 세션 상태에 저장할 때 사용한다.
    """
    db = next(get_db())
    try:
        resolved = lookup_recipient_by_voice(db, uuid.UUID(user_id), recipient)
        if resolved is None:
            return f"{recipient}님을 찾을 수 없습니다. 다시 확인해 주세요.", None

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
        return f"{recipient}님께 {amount:,}원 이체가 완료되었습니다.", tx_id
    except Exception as e:
        logger.error("execute_transfer 실패: user=%s error=%s", user_id, e)
        return "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", None
    finally:
        db.close()


@tool
def execute_transfer(user_id: str, recipient: str, amount: int) -> str:
    """등록된 수취인에게 금액을 이체합니다.

    슬롯이 모두 수집되고 음성 인증이 완료된 뒤 execute_node에서 호출됩니다.
    '이체해줘', '보내줘', '송금해줘' 요청에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        recipient: 수취인 이름 (resolve_node에서 정규화된 값).
        amount: 이체 금액 (원 단위 정수).

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
    except Exception as e:
        logger.error("add_note 실패: user=%s tx_id=%s error=%s", user_id, tx_id, e)
        return "메모 추가 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()
