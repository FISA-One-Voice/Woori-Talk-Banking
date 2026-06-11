"""자동이체 관련 Agent Tools.

execute_auto_transfer : 슬롯 + 사용자 확인 완료 후 자동이체 DB 등록
cancel_auto_transfer  : 수취인 자동이체 해지
list_auto_transfer    : 활성 자동이체 목록 조회
add_auto_transfer_note: 자동이체 건에 메모 추가

[parse_auto_transfer_slots]
v1 잔재. v2부터는 슬롯 추출을 LLM(IntentResult.extracted_slots)이 직접 처리하므로
에이전트에 등록되지 않습니다.
"""

import json
import logging
import re
import uuid

from langchain_core.tools import tool
from sqlalchemy import and_

from app.core.database import SessionLocal, get_db  # noqa: F401
from app.core.exception import AppError, AutoTransferError, RecipientError
from app.features.auto_transfer.schema import AutoTransferRequest
from app.features.auto_transfer.service import (
    list_auto_transfers,
    register_auto_transfer,
)
from app.features.recipients.service import (
    classify_recipient_input,
    lookup_recipient_by_voice,
)
from app.models.account import Account
from app.models.standing_order import StandingOrder

logger = logging.getLogger(__name__)

_CYCLE_LABEL = {"monthly": "매월", "weekly": "매주"}
_DOW_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


@tool
def execute_auto_transfer(
    user_id: str,
    recipient: str | None = None,
    amount: int | str | None = None,
    cycle: str | None = None,
    scheduled_day: int | str | None = None,
    scheduled_dow: int | str | None = None,
    recipient_id: str | None = None,
    from_account_id: str | None = None,
    transfer_note: str | None = None,
) -> str:
    """슬롯 + ASV 인증 + 최종 의사 확인 완료 후 자동이체를 DB에 등록합니다.

    에이전트가 awaiting_confirmation=True + 동의 발화를 확인한 후에만 호출합니다.
    내부적으로 register_auto_transfer() 5관문을 통과합니다.
    password=None 으로 전달 — ASV 통과가 PIN 검증을 대체합니다.
    from_account_id 가 슬롯에 없으면 사용자의 주계좌를 자동으로 사용합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        recipient: 수취인 이름 또는 별명.
        amount: 이체 금액 (원 단위).
        cycle: 'monthly' 또는 'weekly'.
        scheduled_day: 월 기준 날짜 (1~31, monthly 전용).
        scheduled_dow: 요일 (0=월~6=일, weekly 전용).
        recipient_id: 등록 수취인 ID (있으면 직접 사용).
        from_account_id: 출금 계좌 ID (없으면 주계좌 자동 사용).
        transfer_note: 이체 메모.

    Returns:
        {"success": true, "order_id": "...",
         "next_execution_at": "...", "tts_text": "..."}
        {"success": false, "error_code": "...", "tts_text": "..."}
    """
    slots: dict = {
        "recipient": recipient,
        "amount": amount,
        "cycle": cycle,
        "scheduled_day": scheduled_day,
        "scheduled_dow": scheduled_dow,
        "recipientId": recipient_id,
        "fromAccountId": from_account_id,
        "transfer_note": transfer_note,
    }

    db = None
    try:
        db = SessionLocal()
        user_uuid = uuid.UUID(user_id)

        cycle_raw = str(slots.get("cycle", ""))
        if (
            cycle_raw in ("monthly", "매월", "매달")
            or "월" in cycle_raw
            or "달" in cycle_raw
        ):
            slots["cycle"] = "monthly"
        elif cycle_raw in ("weekly", "매주") or "주" in cycle_raw:
            slots["cycle"] = "weekly"

        for key in ("scheduled_day", "scheduled_dow"):
            val = slots.get(key)
            if isinstance(val, str):
                nums = re.findall(r"\d+", val)
                slots[key] = int(nums[0]) if nums else None

        # weekly일 때 LLM이 scheduled_day에 0~6으로 저장하므로 scheduled_dow로 이동
        if slots.get("cycle") == "weekly" and slots.get("scheduled_day") is not None:
            slots["scheduled_dow"] = slots["scheduled_day"]
            slots["scheduled_day"] = None

        if isinstance(slots.get("amount"), str):
            nums = re.findall(r"\d+", str(slots["amount"]))
            slots["amount"] = int("".join(nums)) if nums else 0

        resolved_recipient_id = slots.get("recipientId")
        if not resolved_recipient_id:
            alias = slots.get("recipient") or slots.get("transfer")
            if alias:
                resolved = lookup_recipient_by_voice(db, uuid.UUID(user_id), alias)
                if resolved and resolved.recipient_id:
                    resolved_recipient_id = str(resolved.recipient_id)
                elif classify_recipient_input(alias) == "account":
                    slots["to_account_number"] = alias

        resolved_from_account_id = slots.get("fromAccountId") or slots.get(
            "from_account_id"
        )
        if not resolved_from_account_id:
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
            resolved_from_account_id = str(primary.account_id)

        data = AutoTransferRequest.model_validate(
            {
                "fromAccountId": resolved_from_account_id,
                "amount": slots["amount"],
                "cycle": slots["cycle"],
                "scheduledDay": slots.get("scheduled_day"),
                "scheduledDow": slots.get("scheduled_dow"),
                "recipientId": resolved_recipient_id,
                "toAccountNumber": slots.get("to_account_number"),
                "bankName": slots.get("bankName") or slots.get("bank_name"),
                "toName": slots.get("toName") or slots.get("to_name"),
                "password": None,
                "termsAgreed": True,
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
            {
                "success": False,
                "error_code": e.code,
                "tts_text": e.user_message or e.message,
            },
            ensure_ascii=False,
        )
    except Exception:
        return json.dumps(
            {
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "tts_text": (
                    "자동이체 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                ),
            },
            ensure_ascii=False,
        )
    finally:
        if db is not None:
            db.close()


@tool
def cancel_auto_transfer(user_id: str, recipient: str) -> str:
    """확인 완료 후 수취인의 자동이체를 해지합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        recipient: 해지할 수취인 이름 또는 별명.

    Returns:
        성공/실패 결과 TTS 텍스트.
    """
    db = None
    try:
        db = SessionLocal()
        user_uuid = uuid.UUID(user_id)

        resolved = lookup_recipient_by_voice(db, user_uuid, recipient)
        if not resolved or not resolved.recipient_id:
            return f"'{recipient}'에 대한 등록 수취인을 찾을 수 없습니다."

        orders = (
            db.query(StandingOrder)
            .filter(
                and_(
                    StandingOrder.user_id == user_uuid,
                    StandingOrder.recipient_id == resolved.recipient_id,
                    StandingOrder.status.in_(["active", "paused"]),
                )
            )
            .all()
        )

        if not orders:
            return f"{resolved.recipient_name}에게 설정된 자동이체가 없습니다."

        for order in orders:
            order.status = "cancelled"
        db.commit()

        count = len(orders)
        name = resolved.recipient_name
        if count == 1:
            return f"{name}에게 설정된 자동이체가 해지되었습니다."
        return f"{name}에게 설정된 자동이체 {count}건이 모두 해지되었습니다."

    except AppError as e:
        if db is not None:
            db.rollback()
        return e.user_message or e.message
    except Exception as e:
        if db is not None:
            db.rollback()
        logger.error(
            "cancel_auto_transfer 실패: user=%s recipient=%s error=%s",
            user_id,
            recipient,
            e,
        )
        return "자동이체 해지 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        if db is not None:
            db.close()


@tool
def list_auto_transfer(user_id: str) -> str:
    """사용자의 활성 자동이체 목록을 조회합니다.

    "자동이체 목록 보여줘", "자동이체 뭐 있어" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.

    Returns:
        TTS로 읽을 문자열.
    """
    db = None
    try:
        db = SessionLocal()
        orders = list_auto_transfers(db, user_id, status="active")
        if not orders:
            return "현재 등록된 자동이체가 없습니다."

        lines = [f"등록된 자동이체 내역이 {len(orders)}건 있습니다."]
        for i, o in enumerate(orders, 1):
            cycle = _CYCLE_LABEL.get(o.cycle, o.cycle)
            if o.cycle == "monthly" and o.scheduled_day:
                timing = f"{cycle} {o.scheduled_day}일"
            elif o.cycle == "weekly" and o.scheduled_dow is not None:
                days = ["월", "화", "수", "목", "금", "토", "일"]
                timing = f"{cycle} {days[o.scheduled_dow]}요일"
            else:
                timing = cycle
            lines.append(f"{i}번. {o.to_name} {o.amount:,}원 {timing}")
        return " ".join(lines)

    except AppError as e:
        return e.user_message or e.message
    except Exception as e:
        logger.error("list_auto_transfer 실패: user=%s error=%s", user_id, e)
        return "자동이체 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        if db is not None:
            db.close()


@tool
def add_auto_transfer_note(user_id: str, memo: str, order_id: str) -> str:
    """자동이체 건(order_id)에 메모를 추가합니다.

    자동이체 등록 직후 메모 제안에 사용합니다.
    order_id는 자동이체 완료 후 세션(last_order_id)에서 전달받습니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        memo: 추가할 메모 내용.
        order_id: 메모를 붙일 자동이체 ID (UUID 문자열).

    Returns:
        TTS 친화적 메모 완료 안내 문자열.
    """
    from app.features.auto_transfer import service as auto_transfer_service
    from app.features.auto_transfer.schema import AutoTransferMemoRequest

    db = next(get_db())
    try:
        auto_transfer_service.update_memo(
            db=db,
            user_id=user_id,
            order_id=order_id,
            data=AutoTransferMemoRequest(transfer_note=memo),
        )
        return f"'{memo}' 메모가 추가되었습니다."
    except AppError as e:
        logger.warning(
            "add_auto_transfer_note AppError: user=%s code=%s", user_id, e.code
        )
        return e.user_message or e.message
    except Exception as e:
        logger.error(
            "add_auto_transfer_note 실패: user=%s order_id=%s error=%s",
            user_id,
            order_id,
            e,
        )
        return "메모 추가 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()


def parse_auto_transfer_slots(
    recipient_name: str | None = None,
    to_account_number: str | None = None,
    bank_name: str | None = None,
    to_name: str | None = None,
    amount: int | None = None,
    cycle: str | None = None,
    scheduled_day: int | None = None,
    scheduled_dow: int | None = None,
    transfer_note: str | None = None,
) -> str:
    """[v1 잔재 — 미사용] 자동이체 발화에서 추출된 슬롯 값을 반환합니다.

    v2부터는 LLM(IntentResult.extracted_slots)이 슬롯 추출을 직접 담당하므로
    에이전트에 등록하지 않습니다.
    """
    return json.dumps(
        {
            "extracted": {
                k: v
                for k, v in {
                    "recipient_name": recipient_name,
                    "to_account_number": to_account_number,
                    "bank_name": bank_name,
                    "to_name": to_name,
                    "amount": amount,
                    "cycle": cycle,
                    "scheduled_day": scheduled_day,
                    "scheduled_dow": scheduled_dow,
                    "transfer_note": transfer_note,
                }.items()
                if v is not None
            }
        },
        ensure_ascii=False,
    )
