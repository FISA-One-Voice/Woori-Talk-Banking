"""자동이체 실행 tool.

[역할]
슬롯 + ASV 인증 + 최종 의사 확인이 완료된 후 자동이체를 DB에 등록합니다.
에이전트가 awaiting_confirmation=True + 동의 발화 확인 후에만 호출합니다.
"""

import json
import uuid

from langchain_core.tools import tool

from app.core.database import SessionLocal
from app.core.exception import AutoTransferError, RecipientError
from app.features.auto_transfer.schema import AutoTransferRequest
from app.features.auto_transfer.service import register_auto_transfer
from app.models.account import Account

_DOW_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


@tool
def execute_auto_transfer(user_id: str, slots_json: str) -> str:
    """슬롯 + ASV 인증 + 최종 의사 확인 완료 후 자동이체를 DB에 등록합니다.

    에이전트가 awaiting_confirmation=True + 동의 발화를 확인한 후에만 호출합니다.
    내부적으로 register_auto_transfer() 5관문을 통과합니다.
    password=None 으로 전달 — ASV 통과가 PIN 검증을 대체합니다.
    from_account_id 가 슬롯에 없으면 사용자의 주계좌를 자동으로 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        slots_json: 현재 슬롯 상태 JSON 문자열.

    Returns:
        {"success": true,  "order_id": "...", "next_execution_at": "...", "tts_text": "..."}
        {"success": false, "error_code": "...", "tts_text": "..."}
    """
    try:
        slots: dict = json.loads(slots_json)
    except (json.JSONDecodeError, TypeError):
        slots = {}

    db = SessionLocal()
    try:
        user_uuid = uuid.UUID(user_id)

        # from_account_id — 슬롯에 없으면 주계좌 자동 조회
        from_account_id = slots.get("fromAccountId") or slots.get("from_account_id")
        if not from_account_id:
            primary = (
                db.query(Account)
                .filter(
                    Account.user_id == user_uuid,
                    Account.is_primary.is_(True),
                )
                .first()
            )
            if primary is None:
                return json.dumps(
                    {
                        "success": False,
                        "error_code": "ACCOUNT_NOT_FOUND",
                        "tts_text": "출금 계좌를 찾을 수 없습니다.",
                    },
                    ensure_ascii=False,
                )
            from_account_id = str(primary.account_id)

        data = AutoTransferRequest.model_validate(
            {
                "fromAccountId": from_account_id,
                "amount": slots["amount"],
                "cycle": slots["cycle"],
                "scheduledDay": slots.get("scheduled_day"),
                "scheduledDow": slots.get("scheduled_dow"),
                "recipientId": slots.get("recipientId"),
                "toAccountNumber": slots.get("to_account_number"),
                "bankName": slots.get("bankName") or slots.get("bank_name"),
                "toName": slots.get("toName") or slots.get("to_name"),
                "password": None,       # ASV 통과가 PIN 대체
                "termsAgreed": True,    # 동의 발화가 약관 동의 대체
                "transferNote": slots.get("transfer_note"),
            }
        )

        result = register_auto_transfer(db, user_id, data)

        if result.cycle == "monthly":
            cycle_label = f"매월 {result.scheduled_day}일"
        else:
            dow = result.scheduled_dow or 0
            cycle_label = f"매주 {_DOW_LABELS[dow]}요일"

        tts_text = (
            f"{result.to_name or ''}님께 {cycle_label}에 "
            f"{result.amount:,}원 자동이체가 등록되었습니다."
        )

        return json.dumps(
            {
                "success": True,
                "order_id": result.order_id,
                "next_execution_at": result.next_execution_at,
                "tts_text": tts_text,
            },
            ensure_ascii=False,
        )

    except (AutoTransferError, RecipientError) as e:
        return json.dumps(
            {"success": False, "error_code": e.code, "tts_text": e.message},
            ensure_ascii=False,
        )
    except Exception:
        return json.dumps(
            {
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "tts_text": "자동이체 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            },
            ensure_ascii=False,
        )
    finally:
        db.close()
