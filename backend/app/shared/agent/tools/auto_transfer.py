"""자동이체 슬롯 추출 tool.

[역할]
이번 발화에서 추출된 슬롯 값만 반환합니다.
화면 분기 판단과 수취인 조회는 에이전트(LLM + 프롬프트)가 담당합니다.

[변경 이력]
v1: 슬롯 파싱 + match_by_name DB 조회 + navigate_confirm 분기 판단 전부 담당
v2 (현재): 슬롯 추출만. 분기 판단 → 에이전트. DB 조회 → search_recipient tool.
"""

import json

from langchain_core.tools import tool


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
