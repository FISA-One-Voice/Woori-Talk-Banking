"""이체·메모 Agent Tool.

'이체해줘', '보내줘', '메모 달아줘' 같은 음성 명령을 처리합니다.

tool이 에이전트에 연결되는 방식:
    1. tools/__init__.py 의 _REAL_TOOLS 에 등록
    2. shared/voice/router.py 가 build_graph(ALL_TOOLS) 호출
    3. execute_node가 슬롯·ASV 완료 후 tool 실행
"""

import logging
import uuid

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.recipients.service import lookup_recipient_by_voice
from app.features.transfer import service as transfer_service
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)


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
        )
        return f"{recipient}님께 {amount:,}원 이체가 완료되었습니다."
    except Exception as e:
        logger.error("execute_transfer 실패: user=%s error=%s", user_id, e)
        return "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()


@tool
def add_note(user_id: str, memo: str) -> str:
    """가장 최근 이체 완료 건에 메모를 추가합니다.

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
                Transaction.tx_type == "transfer",
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
