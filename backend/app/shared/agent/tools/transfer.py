"""이체 에이전트 tool — execute_transfer / add_note / get_transfer_history.

비즈니스 로직은 features/transfer/service.py에 있고,
여기서는 @tool 데코레이터로 wrapping만 한다.
"""

from langchain_core.tools import tool

from app.core.database import get_db
from app.features.transfer.service import (
    add_note_tts,
    execute_transfer_tts,
    get_transfer_history_tts,
)


def run_execute_transfer(
    user_id: str,
    recipient: str,
    amount: int,
    *,
    collected_slots: dict | None = None,
) -> tuple[str, str | None]:
    """이체를 실행하고 (TTS 메시지, tx_id)를 반환한다.

    graph.py의 execute_node에서 tx_id를 세션 상태에 저장할 때 사용한다.
    """
    db = next(get_db())
    try:
        return execute_transfer_tts(db, user_id, recipient, amount, collected_slots)
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
        memo: 이체 메모 (선택).

    Returns:
        TTS 친화적 이체 완료 안내 문자열.
    """
    message, _ = run_execute_transfer(user_id, recipient, amount)
    return message


@tool
def add_note(user_id: str, memo: str, tx_id: str) -> str:
    """지정한 이체 거래(tx_id)에 메모를 추가합니다.

    '방금 이체에 메모 달아줘' 등의 말에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        memo: 추가할 메모 내용.
        tx_id: 메모를 붙일 트랜잭션 ID (UUID 문자열).

    Returns:
        TTS 친화적 메모 완료 안내 문자열.
    """
    db = next(get_db())
    try:
        return add_note_tts(db, user_id, memo, tx_id)
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
        return get_transfer_history_tts(db, user_id, days)
    finally:
        db.close()
