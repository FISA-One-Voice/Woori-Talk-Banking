"""이체·메모 Agent Tool.

'이체해줘', '보내줘', '메모 달아줘' 같은 음성 명령을 처리합니다.

tool이 에이전트에 연결되는 방식:
    1. tools/__init__.py 의 _REAL_TOOLS 에 등록
    2. shared/voice/router.py 가 build_graph(ALL_TOOLS) 호출
    3. execute_node가 슬롯·ASV 완료 후 run_* 호출 (transfer/add_note는 tx_id 연동)
"""

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
    """이체 실행. (TTS 메시지, txId 또는 None) — graph가 last_tx_id에 저장한다."""
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
        return (
            f"{recipient}님께 {amount:,}원 이체가 완료되었습니다.",
            receipt.get("txId"),
        )
    except Exception as e:
        logger.error("execute_transfer 실패: user=%s error=%s", user_id, e)
        return "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", None
    finally:
        db.close()


def run_add_note(user_id: str, memo: str, tx_id: str) -> str:
    """지정 tx_id에 메모 저장 (router POST /{tx_id}/memo 와 동일 service)."""
    if not tx_id:
        return "이체 정보가 없습니다. 먼저 이체를 완료한 뒤 메모를 남겨 주세요."

    db = next(get_db())
    try:
        transfer_service.update_memo(db=db, user_id=user_id, tx_id=tx_id, memo=memo)
        return f"'{memo}' 메모가 추가되었습니다."
    except Exception as e:
        logger.error("add_note 실패: user=%s tx_id=%s error=%s", user_id, tx_id, e)
        return "메모 추가 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
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
    msg, _ = run_execute_transfer(user_id, recipient, amount)
    return msg


@tool
def add_note(user_id: str, memo: str, tx_id: str) -> str:
    """지정한 이체 건에 메모를 추가합니다.

    tx_id는 execute_node가 이체 직후 state.last_tx_id에서 주입한다.
    '방금 이체에 메모 달아줘' 등 — Phase B intent 연동 시 사용.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        memo: 추가할 메모 내용.
        tx_id: 메모를 붙일 트랜잭션 ID (이체 영수증 txId).

    Returns:
        TTS 친화적 메모 완료 안내 문자열.
    """
    return run_add_note(user_id, memo, tx_id)
