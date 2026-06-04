"""자동이체 실행 tool.

[역할]
슬롯 + ASV 인증 + 최종 의사 확인이 완료된 후 자동이체를 DB에 등록합니다.
에이전트가 awaiting_confirmation=True + 동의 발화 확인 후에만 호출합니다.
"""

import json
import re
import uuid

from langchain_core.tools import tool

from app.core.database import SessionLocal
from app.core.exception import AutoTransferError, RecipientError
from app.features.auto_transfer.schema import AutoTransferRequest
from app.features.auto_transfer.service import register_auto_transfer
from app.features.recipients.service import lookup_recipient_by_voice
from app.models.account import Account

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
        {"success": true,  "order_id": "...", "next_execution_at": "...", "tts_text": "..."}
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

    db = SessionLocal()
    try:
        user_uuid = uuid.UUID(user_id)

        # ── 슬롯 값 정규화 ──────────────────────────────────────────────────────────
        # cycle: 한국어 표현 → 영문 코드
        cycle_raw = str(slots.get("cycle", ""))
        if (
            cycle_raw in ("monthly", "매월", "매달")
            or "월" in cycle_raw
            or "달" in cycle_raw
        ):
            slots["cycle"] = "monthly"
        elif cycle_raw in ("weekly", "매주") or "주" in cycle_raw:
            slots["cycle"] = "weekly"

        # scheduled_day / scheduled_dow: 문자열 → 정수
        for key in ("scheduled_day", "scheduled_dow"):
            val = slots.get(key)
            if isinstance(val, str):
                nums = re.findall(r"\d+", val)
                slots[key] = int(nums[0]) if nums else None

        # amount: 문자열 → 정수
        if isinstance(slots.get("amount"), str):
            nums = re.findall(r"\d+", str(slots["amount"]))
            slots["amount"] = int("".join(nums)) if nums else 0

        # recipientId — recipient 또는 transfer 슬롯 값으로 DB 재조회
        recipient_id = slots.get("recipientId")
        if not recipient_id:
            alias = slots.get("recipient") or slots.get("transfer")
            if alias:
                resolved = lookup_recipient_by_voice(db, uuid.UUID(user_id), alias)
                if resolved and resolved.recipient_id:
                    recipient_id = str(resolved.recipient_id)

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
                "recipientId": recipient_id,
                "toAccountNumber": slots.get("to_account_number"),
                "bankName": slots.get("bankName") or slots.get("bank_name"),
                "toName": slots.get("toName") or slots.get("to_name"),
                "password": None,  # ASV 통과가 PIN 대체
                "termsAgreed": True,  # 동의 발화가 약관 동의 대체
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
