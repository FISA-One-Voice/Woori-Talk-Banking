"""액션별 필요 슬롯 정의, 화면 매핑, ASV 필요 액션 목록 (Issue #21).

Design Ref (Issue #21):
    §slot_schema.py — SLOT_SCHEMA / SCREEN_MAP / ASV_REQUIRED_ACTIONS
"""

from app.features.recipients.service import classify_recipient_input

# ── 액션별 필요 슬롯 ─────────────────────────────────────────────────────────────
# key: pending_action 값 (intent_node가 설정)
# value: 슬롯 이름 목록 (각 슬롯명은 service.py 파라미터명과 일치)
SLOT_SCHEMA: dict[str, list[str]] = {
    "transfer": ["recipient", "amount"],
    "auto_transfer": ["recipient", "amount", "cycle", "scheduled_day"],
    "cancel_auto_transfer": ["recipient"],
    "add_note": ["memo"],
}

# SCREEN_MAP에 없는 음성 전용 인텐트 (화면 이동 없음)
VOICE_ONLY_INTENTS: set[str] = {"add_note"}

# ── intent → 프론트엔드 화면 이름 매핑 ────────────────────────────────────────────
# Expo Router 경로명을 기준으로 정의한다.
# intent_node가 navigate_to에 이 값을 설정하면 _layout.tsx가 화면을 이동시킨다.
SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer",
    "auto_transfer": "auto-transfer",
    "balance": "balance",
    "history": "balance",  # 자산 화면에 통합 (Issue #9)
    "event": "event",
    "home": "home",
    "cancel_auto_transfer": "auto-transfer",
    "list_auto_transfer": "auto-transfer",
}

# ── 수취인 검증이 필요한 액션 ────────────────────────────────────────────────────
# recipient 슬롯이 채워지는 즉시 resolve_node를 통해 수취인 존재 여부를 확인한다.
RECIPIENT_REQUIRED_ACTIONS: set[str] = {
    "transfer",
    "auto_transfer",
    "cancel_auto_transfer",
}

# ── ASV 음성 인증이 필요한 액션 ─────────────────────────────────────────────────
# 금전 이동이 발생하는 액션만 포함한다.
# 해당 액션의 확인("네") 수신 후 awaiting_asv_audio=True를 설정한다.
ASV_REQUIRED_ACTIONS: set[str] = {
    "transfer",  # 계좌 이체
    "auto_transfer",  # 자동이체 등록
}

# ── 이체 완료 후 메모 제안 (에이전트 TTS) ─────────────────────────────────────────
MEMO_OFFER_SUFFIX: str = (
    " 메모를 남기시겠어요? 식비, 교통비, 쇼핑, 의료비, 문화생활, 기타 중 말씀해 주시거나, "
    "건너뛰기라고 말씀해 주세요."
)

# 이체 실패 TTS 끝 — 프론트 transfer/failed 자동 홈 이동과 동기화
TRANSFER_FAILED_HOME_SUFFIX: str = " 홈 화면으로 이동합니다."

# ── 슬롯별 TTS 질문 템플릿 ────────────────────────────────────────────────────────
# slot_fill_node에서 첫 번째 누락 슬롯의 질문을 TTS로 반환한다.
SLOT_QUESTIONS: dict[str, str] = {
    "recipient": "누구에게 보낼까요? 별명이나 이름을 말씀해 주세요.",
    "bank_name": ("어느 은행 계좌인가요? 우리은행, 국민은행처럼 말씀해 주세요."),
    "amount": "얼마를 보낼까요?",
    "cycle": "매월 또는 매주 중 어떤 주기로 보낼까요?",
    "scheduled_day": "매월 며칠에 이체할까요?",
    "memo": "어떤 메모를 달까요?",
}

SLOT_QUESTIONS_BY_ACTION: dict[str, dict[str, str]] = {
    "cancel_auto_transfer": {
        "recipient": "누구의 자동이체를 해지할까요? 이름이나 별명을 말씀해 주세요.",
    },
}

# ── 실행 완료 화면 경로 ────────────────────────────────────────────────────────────
# execute_node 실행 후 navigate_to에 설정되어 프론트엔드 완료 화면으로 이동한다.
COMPLETE_SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer/complete",
    "auto_transfer": "auto-transfer/complete",
    "cancel_auto_transfer": "auto-transfer",
    "list_auto_transfer": "auto-transfer",
}

# execute_node 이체 실패 시 프론트엔드 실패 화면 (SCR004-F08)
FAILED_SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer/failed",
}

# ── 확인(네/아니오) TTS 안내 ─────────────────────────────────────────────────────
# confirm_node·transfer_clarification·프론트 오버레이와 동일 문구.
CONFIRM_YES_NO_SUFFIX: str = (
    " 네 또는 아니오라고 말씀하시거나, 수정사항을 말씀해 주세요."
)

ACTIONS_WITH_YES_NO_CONFIRM: set[str] = {
    "transfer",
    "auto_transfer",
    "cancel_auto_transfer",
}

# ── 액션 한국어 레이블 ────────────────────────────────────────────────────────────
# confirm_node의 확인 메시지 생성에 사용한다.
ACTION_LABELS: dict[str, str] = {
    "transfer": "이체",
    "auto_transfer": "자동이체 등록",
    "cancel_auto_transfer": "자동이체 해지",
    "list_auto_transfer": "자동이체 조회",
}

# ── 화면 전환 전용 인텐트 ─────────────────────────────────────────────────────────
# 화면이 자체적으로 데이터를 가져오고 TTS를 처리하므로
# intent_node에서 navigate_to만 설정하고 execute_node 없이 바로 END.
# balance/history는 에이전트가 잔액·내역을 TTS로 읽어주므로 여기에 포함하지 않음.
SCREEN_ONLY_INTENTS: set[str] = set()

# ── 유효한 인텐트 목록 ─────────────────────────────────────────────────────────────
VALID_INTENTS: set[str] = set(SCREEN_MAP.keys()) | VOICE_ONLY_INTENTS


def transfer_missing_slots(collected_slots: dict) -> list[str]:
    """transfer 액션의 누락 슬롯 (미등록 계좌는 bank_name 동적 포함)."""
    missing: list[str] = []
    recipient = collected_slots.get("recipient")
    if not recipient:
        missing.append("recipient")
    elif (
        classify_recipient_input(str(recipient)) == "account"
        and not collected_slots.get("recipient_id")
        and not collected_slots.get("bank_name")
    ):
        missing.append("bank_name")
    if not collected_slots.get("amount"):
        missing.append("amount")
    return missing


# ── 슬롯 유효성 검사 ─────────────────────────────────────────────────────────────


def valid_scheduled_day(value: object, cycle: object) -> bool:
    """자동이체 주기에 맞는 scheduled_day 값인지 확인한다."""
    if value is None or cycle is None:
        return False
    try:
        day = int(value)
    except (TypeError, ValueError):
        return False
    if cycle == "monthly":
        return 1 <= day <= 31
    if cycle == "weekly":
        return 0 <= day <= 6
    return False


def missing_slots(pending_action: str, collected_slots: dict) -> list[str]:
    """pending_action에 따라 수집되지 않은 슬롯 이름 목록을 반환한다."""
    if pending_action == "transfer":
        return transfer_missing_slots(collected_slots)
    required = SLOT_SCHEMA.get(pending_action, [])
    result: list[str] = []
    for slot_name in required:
        value = collected_slots.get(slot_name)
        if slot_name == "scheduled_day":
            if not valid_scheduled_day(value, collected_slots.get("cycle")):
                result.append(slot_name)
        elif not value:
            result.append(slot_name)
    return result


# ── STT·한국어 금액·요일 파싱 ────────────────────────────────────────────────────

KOR_DOW_MAP: dict[str, int] = {
    "월": 0,
    "월요일": 0,
    "화": 1,
    "화요일": 1,
    "수": 2,
    "수요일": 2,
    "목": 3,
    "목요일": 3,
    "금": 4,
    "금요일": 4,
    "토": 5,
    "토요일": 5,
    "일": 6,
    "일요일": 6,
}

STT_AMOUNT_ALIASES: dict[str, int] = {
    "전원": 1000,
    "천원": 1000,
    "천": 1000,
    "만원": 10000,
    "만": 10000,
}


def _kor_to_int(text: str) -> int | None:
    """순수 한국어 숫자 문자열을 정수로 변환한다."""
    _DIGIT = {
        "일": 1,
        "이": 2,
        "삼": 3,
        "사": 4,
        "오": 5,
        "육": 6,
        "칠": 7,
        "팔": 8,
        "구": 9,
    }
    _SMALL = {"십": 10, "백": 100, "천": 1000}

    def _below_10000(s: str) -> int:
        result, current = 0, 0
        for ch in s:
            if ch in _DIGIT:
                current = _DIGIT[ch]
            elif ch in _SMALL:
                result += (current or 1) * _SMALL[ch]
                current = 0
        return result + current

    total = 0
    if "억" in text:
        parts = text.split("억", 1)
        total += (_below_10000(parts[0]) or 1) * 100_000_000
        text = parts[1]
    if "만" in text:
        parts = text.split("만", 1)
        total += (_below_10000(parts[0]) or 1) * 10_000
        text = parts[1]
    total += _below_10000(text)
    return total if total > 0 else None


def parse_korean_amount(raw: str) -> str | None:
    """한국어·STT 오인식 금액 표현을 정수 문자열로 변환한다.

    STT 오인식("전원"→천원), 한국어 숫자("오만원"→50000),
    숫자+단위("1000원"→1000) 세 경우를 처리한다.
    변환 불가 시 None을 반환한다.
    """
    import re as _re

    text = str(raw).strip().replace(" ", "").replace(",", "")
    if not text:
        return None
    if text in STT_AMOUNT_ALIASES:
        return str(STT_AMOUNT_ALIASES[text])
    text_no_won = _re.sub(r"원$", "", text)
    try:
        val = int(text_no_won)
        return str(val) if val > 0 else None
    except ValueError:
        pass
    val = _kor_to_int(text_no_won)
    return str(val) if val is not None and val > 0 else None


def normalize_scheduled_day(slots: dict, extracted_slots: dict) -> dict:
    """STT 오류 보정 및 한글 요일명 → 정수 변환."""
    normalized = dict(slots)
    for key, value in extracted_slots.items():
        if key == "scheduled_day" and value is not None:
            kor_key = str(value).replace(" ", "")
            if kor_key in KOR_DOW_MAP:
                value = KOR_DOW_MAP[kor_key]
            else:
                try:
                    day_int = int(value)
                except (TypeError, ValueError):
                    day_int = None
                if day_int is not None and 32 <= day_int <= 91 and day_int % 10 == 1:
                    value = day_int // 10
        normalized[key] = value
    return normalized
