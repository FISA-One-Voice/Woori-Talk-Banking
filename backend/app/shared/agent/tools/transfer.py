"""이체 에이전트 tool — execute_transfer / add_note."""

import json
import logging
import uuid

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError
from app.features.transfer import service as transfer_service

logger = logging.getLogger(__name__)


@tool
def execute_transfer(
    user_id: str,
    recipient: str,
    amount: int,
    account_number: str | None = None,
    bank_name: str | None = None,
    recipient_id: str | None = None,
) -> str:
    """등록된 수취인에게 금액을 이체합니다.

    슬롯이 모두 수집되고 음성 인증이 완료된 뒤 execute_node에서 호출됩니다.
    '이체해줘', '보내줘', '송금해줘' 요청에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        recipient: 수취인 표시 이름 (resolve_node에서 정규화된 값).
        amount: 이체 금액 (원 단위 정수).
        account_number: 수취인 계좌번호 (resolve_node에서 채움).
        bank_name: 수취인 은행명 (resolve_node에서 채움).
        recipient_id: 등록 수취인 ID (resolve_node에서 채움, 선택).

    Returns:
        JSON: {"tts_text": str, "tx_id": str | None, "success": bool}
    """
    display_name = str(recipient or "수취인")
    db = next(get_db())
    try:
        if not account_number and not recipient_id:
            return json.dumps(
                {
                    "tts_text": (
                        f"{display_name}님을 찾을 수 없습니다. 다시 확인해 주세요."
                    ),
                    "tx_id": None,
                    "success": False,
                },
                ensure_ascii=False,
            )

        receipt = transfer_service.execute_transfer(
            db=db,
            user_id=user_id,
            recipient=str(account_number) if account_number else "",
            bank_name=str(bank_name) if bank_name else "",
            amount=int(amount),
            idempotency_key=str(uuid.uuid4()),
            recipient_name=display_name,
            recipient_id=str(recipient_id) if recipient_id else None,
        )
        tx_id = str(receipt["txId"]) if receipt.get("txId") is not None else None
        return json.dumps(
            {
                "tts_text": (
                    f"{display_name}님께 {int(amount):,}원 이체가 완료되었습니다."
                ),
                "tx_id": tx_id,
                "success": True,
            },
            ensure_ascii=False,
        )
    except AppError as e:
        logger.warning("execute_transfer AppError: user=%s code=%s", user_id, e.code)
        return json.dumps(
            {"tts_text": e.user_message or e.message, "tx_id": None, "success": False},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("execute_transfer 실패: user=%s error=%s", user_id, e)
        return json.dumps(
            {
                "tts_text": (
                    "이체 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                ),
                "tx_id": None,
                "success": False,
            },
            ensure_ascii=False,
        )
    finally:
        db.close()


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
        logger.warning(
            "add_note_error",
            extra={"event": "add_note_error", "user_id": user_id, "code": e.code},
        )
        return e.user_message or e.message
    except Exception as e:
        logger.error(
            "add_note_failed",
            extra={
                "event": "add_note_failed",
                "user_id": user_id,
                "tx_id": tx_id,
                "error": str(e),
            },
        )
        return "메모 추가 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()
