"""액션별 필요 슬롯 정의, 화면 매핑, ASV 필요 액션 목록 (Issue #21, #48).

Design Ref:
    §slot_schema.py — SLOT_SCHEMA / SCREEN_MAP / ASV_REQUIRED_ACTIONS
"""

# ── 액션별 전체 슬롯 템플릿 ───────────────────────────────────────────────────────
# key: pending_action 값
# value: 슬롯명 → 기본값(None) 딕셔너리 또는 슬롯명 리스트

from app.features.recipients.service import classify_recipient_input

# ── 액션별 필요 슬롯 ─────────────────────────────────────────────────────────────
# key: pending_action 값 (intent_node가 설정)
# value: 슬롯 이름 목록 (각 슬롯명은 service.py 파라미터명과 일치)
SLOT_SCHEMA: dict[str, list[str]] = {
    "transfer": ["recipient", "amount"],
    "auto_transfer": ["recipient", "amount", "cycle", "scheduled_day"],
    "add_note": ["memo"],
    "asset": ["action"],  # action만 필수, period/category는 선택
}

# SCREEN_MAP에 없는 음성 전용 인텐트 (화면 이동 없음)
VOICE_ONLY_INTENTS: set[str] = {"add_note"}

# ── intent → 프론트엔드 화면 이름 매핑 ────────────────────────────────────────────
# Expo Router 경로명을 기준으로 정의한다.
SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer",
    "auto_transfer": "auto-transfer",
    "balance": "asset",
    "history": "asset/history?type=history",   # 거래내역 목록 화면
    "event": "event",
    "asset": "asset",
    "home": "home",
    "transfer_history": "asset/history?type=history",
    "cancel_auto_transfer": "auto-transfer"
}

# ── 수취인 검증이 필요한 액션 ────────────────────────────────────────────────────
# recipient 슬롯이 채워지는 즉시 resolve_node를 통해 수취인 존재 여부를 확인한다.
RECIPIENT_REQUIRED_ACTIONS: set[str] = {
    "transfer",
    "auto_transfer",
    "cancel_auto_transfer",
}

# ── ASV 음성 인증이 필요한 액션 ─────────────────────────────────────────────────
ASV_REQUIRED_ACTIONS: set[str] = {
    "transfer",
    "auto_transfer",
}

# ── 이체 완료 후 메모 제안 (에이전트 TTS) ─────────────────────────────────────────
MEMO_OFFER_SUFFIX: str = (
    " 메모를 남기시겠어요? 식비, 교통비, 쇼핑, 의료비, 문화생활, 기타 중 말씀해 주시거나, "
    "건너뛰기라고 말씀해 주세요."
)

# ── 슬롯별 TTS 질문 템플릿 ────────────────────────────────────────────────────────
SLOT_QUESTIONS: dict[str, str] = {
    "recipient": "누구에게 보낼까요? 별명이나 이름을 말씀해 주세요.",
    "bank_name": ("어느 은행 계좌인가요? 우리은행, 국민은행처럼 말씀해 주세요."),
    "amount": "얼마를 보낼까요?",
    "cycle": "매월 또는 매주 중 어떤 주기로 보낼까요?",
    "scheduled_day": "매월 며칠에 이체할까요?",
    "memo": "어떤 메모를 달까요?",
    # 자산 조회 슬롯 (Issue #48)
    "action": "잔액, 거래 내역, 카테고리 조회 중 어떤 것을 원하시나요?",
    "period": "언제 기간을 조회할까요? 이번달, 지난달, 최근 칠일 중 말씀해 주세요.",
    "category": "어떤 카테고리를 조회할까요? 예: 식비, 교통, 문화생활.",
    "date_range": "조회 시작 날짜를 말씀해 주세요. 예: 삼월 오일.",
}

SLOT_QUESTIONS_BY_ACTION: dict[str, dict[str, str]] = {
    "cancel_auto_transfer": {
        "recipient": "누구의 자동이체를 해지할까요? 이름이나 별명을 말씀해 주세요.",
    },
}

# ── 실행 완료 화면 경로 ────────────────────────────────────────────────────────────
COMPLETE_SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer/complete",
    "auto_transfer": "auto-transfer/complete",
    "cancel_auto_transfer": "auto-transfer",
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
ACTION_LABELS: dict[str, str] = {
    "transfer": "이체",
    "auto_transfer": "자동이체 등록",
    "asset": "자산 조회",
    "cancel_auto_transfer": "자동이체 해지",
}

# ── 확인 메시지 없이 즉시 실행하는 액션 ────────────────────────────────────────────
NO_CONFIRM_ACTIONS: set[str] = {"asset", "balance", "history", "event", "transfer_history"}

# ── 화면 전환 전용 인텐트 ─────────────────────────────────────────────────────────
# 화면이 자체적으로 데이터를 가져오고 TTS를 처리하므로
# intent_node에서 navigate_to만 설정하고 execute_node 없이 바로 END.
# balance/history는 에이전트가 잔액·내역을 TTS로 읽어주므로 여기에 포함하지 않음.
# transfer_history/event는 화면이 자체 데이터를 가져오므로 tool 없이 화면 이동만 함.
SCREEN_ONLY_INTENTS: set[str] = {"transfer_history", "event"}

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
