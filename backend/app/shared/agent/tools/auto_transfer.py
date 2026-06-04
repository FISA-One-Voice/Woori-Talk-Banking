"""자동이체 슬롯 추출 tool.

[역할]
이번 발화에서 추출된 슬롯 값만 반환합니다.
화면 분기 판단과 수취인 조회는 에이전트(LLM + 프롬프트)가 담당합니다.

[변경 이력]
v1: 슬롯 파싱 + match_by_name DB 조회 + navigate_confirm 분기 판단 전부 담당
v2 (현재): 슬롯 추출만. 분기 판단 → 에이전트. DB 조회 → search_recipient tool.
"""

import json
import logging

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError

logger = logging.getLogger(__name__)


@tool
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
    """자동이체 발화에서 추출된 슬롯 값을 반환합니다.

    다음 유형의 발화 시 호출합니다:
    - '엄마한테 매월 15일 오만원 자동이체 등록해줘'
    - '우리은행 1002-123-456789 홍길동 매월 10일 오만원'

    수취인 조회(match_by_name)는 search_recipient tool이 담당합니다.
    화면 분기 판단은 에이전트가 슬롯 상태를 보고 결정합니다.

    Args:
        recipient_name: 발화에서 추출한 수취인 이름 또는 별명.
        to_account_number: 직접 입력 계좌번호.
        bank_name: 직접 입력 은행명.
        to_name: 직접 입력 수취인 실명.
        amount: 금액 (원 단위 정수).
        cycle: 'monthly' 또는 'weekly'.
        scheduled_day: 월 기준 날짜 (1~31, monthly 전용).
        scheduled_dow: 요일 (0=월~6=일, weekly 전용).
        transfer_note: 이체 메모 (선택).

    Returns:
        {"extracted": {채워진 슬롯 키: 값, ...}}
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
        logger.warning("add_auto_transfer_note AppError: user=%s code=%s", user_id, e.code)  # noqa: E501
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
