"""화면 담당자가 실제 tool을 등록하기 전까지 사용하는 mock 구현체 (Issue #21).

각 mock tool은 실제 service 호출 없이 하드코딩된 TTS 친화적 응답을 반환한다.
DB, 외부 API 없이도 StateGraph 흐름을 검증할 수 있다.

사용 방법:
    개발/테스트: USE_MOCK_TOOLS=true (기본값) → tools/__init__.py가 자동 활성화
    실제 배포: 화면 담당자가 실제 tool을 완성하면 USE_MOCK_TOOLS=false로 전환

담당자별 교체 대상:
    공통        (공통): mock_lookup_recipient → features/transfer/tools (또는 recipients)
    balance  담당자 (B): mock_get_balance → features/balance/tools
    history  담당자 (B): mock_get_history → features/history/tools
    transfer 담당자 (C): mock_execute_transfer → features/transfer/tools
    auto_transfer 담당자 (D): mock_register_auto_transfer → features/auto_transfer/tools
    event 담당자 (E): mock_get_events → features/event/tools

Design Ref (Issue #21):
    §3 — mock_tools.py: 화면 탐색·tool 사용 테스트를 위한 mock 구현
"""

from langchain_core.tools import tool

# ── 잔액 조회 ──────────────────────────────────────────────────────────────────


@tool
def mock_get_balance(user_id: str) -> str:
    """잔액을 조회합니다.

    '잔액 얼마야', '돈 얼마 있어', '잔액 알려줘', '계좌 잔액' 등의 말에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.

    Returns:
        TTS 친화적 잔액 안내 문자열.
        예: "현재 입출금 통장 잔액은 오백만 원이고, 저축 통장 잔액은 삼백만 원입니다."
    """
    return (
        "현재 입출금 통장 잔액은 오백만 원이고, 저축 통장 잔액은 삼백만 원입니다. "
        "총 보유 금액은 팔백만 원입니다."
    )


# ── 거래 내역 조회 ─────────────────────────────────────────────────────────────


@tool
def mock_get_history(user_id: str, days: int = 7, category: str = "") -> str:
    """거래 내역을 조회합니다.

    '최근 거래 내역', '이번 달 지출', '최근 칠 일 내역', '소비 내역' 등의 말에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.
        days: 조회할 일수 (기본 7일).
        category: 카테고리 필터 (없으면 전체).

    Returns:
        TTS 친화적 거래 내역 안내 문자열.
    """
    return (
        f"최근 {days}일간 거래 내역입니다. "
        "편의점 만 이천 원, 카페 오천 원, 식당 이만 사천 원입니다. "
        "총 삼만 천 원을 지출하셨습니다."
    )


# ── 이체 실행 ────────────────────────────────────────────────────────────────


@tool
def mock_execute_transfer(alias: str, amount: int) -> str:
    """등록된 수취인에게 금액을 이체합니다.

    슬롯이 모두 수집되고 사용자가 확인('네')한 뒤 execute_node에서 호출됩니다.
    SLOT_SCHEMA["transfer"]의 슬롯("alias", "amount")과 파라미터가 일치해야 합니다.

    Args:
        alias: 수취인 별명 (예: "엄마", "회사"). SLOT_SCHEMA의 "alias"와 일치.
        amount: 이체 금액 (원 단위). SLOT_SCHEMA의 "amount"와 일치.

    Returns:
        TTS 친화적 이체 완료 안내 문자열.
    """
    formatted = _format_amount(amount)
    return f"{alias}에게 {formatted} 이체가 완료되었습니다."


# ── 자동이체 등록 ─────────────────────────────────────────────────────────────


@tool
def mock_register_auto_transfer(
    alias: str,
    amount: int,
    cycle: str,
    scheduled_day: int,
) -> str:
    """자동이체를 등록합니다.

    슬롯이 모두 수집되고 사용자가 확인('네')한 뒤 execute_node에서 호출됩니다.
    SLOT_SCHEMA["auto_transfer"]의 슬롯과 파라미터가 일치해야 합니다.

    Args:
        alias: 수취인 별명. SLOT_SCHEMA의 "alias"와 일치.
        amount: 이체 금액 (원 단위). SLOT_SCHEMA의 "amount"와 일치.
        cycle: 주기 ("monthly" 또는 "weekly"). SLOT_SCHEMA의 "cycle"와 일치.
        scheduled_day: 이체일 (1~31). SLOT_SCHEMA의 "scheduled_day"와 일치.

    Returns:
        TTS 친화적 자동이체 등록 완료 안내 문자열.
    """
    formatted = _format_amount(amount)
    freq_label = "매월" if cycle == "monthly" else "매주"
    return (
        f"{alias}에게 {freq_label} {scheduled_day}일 {formatted} "
        "자동이체가 등록되었습니다."
    )


# ── 수취인 조회 (resolve_node용) ─────────────────────────────────────────────


@tool
def mock_lookup_recipient(user_id: str, alias: str) -> str | None:
    """수취인 별명·이름으로 등록된 수취인을 조회합니다 (mock).

    실제 툴 등록 전까지 하드코딩된 mock DB를 사용합니다.
    transfer/auto_transfer 담당자가 실제 lookup_recipient 툴로 교체합니다.

    Args:
        user_id: 요청 사용자 ID.
        alias: alias 슬롯 값 (이름, 전화번호, 계좌번호 모두 허용).

    Returns:
        정규화된 수취인 이름 문자열 (찾은 경우), None (없는 경우).
    """
    mock_db: dict[str, str] = {
        "엄마": "홍어머니",
        "아빠": "홍아버지",
        "친구": "김철수",
        "회사": "우리회사",
    }
    return mock_db.get(alias)


# ── 이벤트 조회 ────────────────────────────────────────────────────────────────


@tool
def mock_get_events(user_id: str) -> str:
    """현재 진행 중인 이벤트 목록을 조회합니다.

    '이벤트 뭐 있어', '행사 알려줘', '이번 달 이벤트', '혜택 알려줘' 등의 말에 사용합니다.

    Args:
        user_id: 현재 로그인한 사용자 ID.

    Returns:
        TTS 친화적 이벤트 안내 문자열.
    """
    return (
        "현재 진행 중인 이벤트는 두 가지입니다. "
        "첫째, 우리 은행 앱 이용 고객 대상 캐시백 이벤트로 이번 달 말까지 진행됩니다. "
        "둘째, 자동이체 신규 등록 시 천 원 적립 혜택 이벤트입니다."
    )


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────


def _format_amount(amount: int) -> str:
    """금액을 TTS 친화적 한국어 표현으로 변환한다.

    Args:
        amount: 원 단위 정수 금액.

    Returns:
        한국어 단위 포함 금액 문자열.
        예: 100000 → "십만 원", 50000 → "오만 원", 1500 → "천오백 원"
    """
    if amount <= 0:
        return "영 원"

    units = [
        (100_000_000, "억"),
        (10_000, "만"),
        (1_000, "천"),
        (100, "백"),
        (10, "십"),
    ]
    parts: list[str] = []
    remaining = amount
    for unit_val, unit_name in units:
        if remaining >= unit_val:
            cnt = remaining // unit_val
            remaining %= unit_val
            parts.append(f"{cnt}{unit_name}")
    if remaining > 0:
        parts.append(str(remaining))

    return "".join(parts) + " 원"
