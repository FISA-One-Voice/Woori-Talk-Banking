"""액션별 필요 슬롯 정의, 화면 매핑, ASV 필요 액션 목록 (Issue #21, #48).

Design Ref:
    §slot_schema.py — SLOT_SCHEMA / SCREEN_MAP / ASV_REQUIRED_ACTIONS
"""

# ── 액션별 전체 슬롯 템플릿 ───────────────────────────────────────────────────────
# key: pending_action 값
# value: 슬롯명 → 기본값(None) 딕셔너리 또는 슬롯명 리스트
SLOT_SCHEMA: dict[str, dict | list] = {
    "transfer": ["recipient", "amount"],
    "auto_transfer": ["recipient", "amount", "cycle", "scheduled_day"],
    "add_note": ["memo"],
    # Issue #48: 자산 조회 — 가능한 모든 슬롯 정의
    "asset": {
        "action": None,      # "balance" / "history" / "category"
        "period": None,      # "이번달" / "지난달" / "최근7일"
        "date_range": None,  # 시작일 ISO "YYYY-MM-DD"
        "category": None,    # "식비" / "문화생활" / "교통" (action=category 시 사용)
    },
}

# ── 액션별 필수 슬롯 ───────────────────────────────────────────────────────────────
# _missing_slots()가 이 목록을 기준으로 "아직 못 채운 슬롯"을 판단한다.
REQUIRED_SLOTS: dict[str, list[str]] = {
    "transfer": ["recipient", "amount"],
    "auto_transfer": ["recipient", "amount", "cycle", "scheduled_day"],
    "add_note": ["memo"],
    "asset": ["action"],  # action만 필수, period/date_range/category는 optional
}

# ── intent → 프론트엔드 화면 이름 매핑 ────────────────────────────────────────────
# Expo Router 경로명을 기준으로 정의한다.
SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer",
    "auto_transfer": "auto-transfer",
    "balance": "asset",
    "history": "asset/history",
    "event": "event",
    "asset": "asset",
    "home": "home",
}

# ── 수취인 검증이 필요한 액션 ────────────────────────────────────────────────────
RECIPIENT_REQUIRED_ACTIONS: set[str] = {"transfer", "auto_transfer"}

# ── ASV 음성 인증이 필요한 액션 ─────────────────────────────────────────────────
ASV_REQUIRED_ACTIONS: set[str] = {
    "transfer",
    "auto_transfer",
}

# ── 슬롯별 TTS 질문 템플릿 ────────────────────────────────────────────────────────
SLOT_QUESTIONS: dict[str, str] = {
    "recipient": "누구에게 보낼까요? 별명이나 이름을 말씀해 주세요.",
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

# ── 실행 완료 화면 경로 ────────────────────────────────────────────────────────────
COMPLETE_SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer/complete",
    "auto_transfer": "auto-transfer/complete",
}

# ── 액션 한국어 레이블 ────────────────────────────────────────────────────────────
ACTION_LABELS: dict[str, str] = {
    "transfer": "이체",
    "auto_transfer": "자동이체 등록",
    "asset": "자산 조회",
}

# ── 확인 메시지 없이 즉시 실행하는 액션 ────────────────────────────────────────────
NO_CONFIRM_ACTIONS: set[str] = {"asset", "balance", "history", "event"}

# ── 화면 전환 전용 인텐트 ─────────────────────────────────────────────────────────
# 화면이 자체적으로 데이터를 가져오고 TTS를 처리하므로
# intent_node에서 navigate_to만 설정하고 execute_node 없이 바로 END.
SCREEN_ONLY_INTENTS: set[str] = {"event"}

# ── 유효한 인텐트 목록 ─────────────────────────────────────────────────────────────
VALID_INTENTS: set[str] = set(SCREEN_MAP.keys())
