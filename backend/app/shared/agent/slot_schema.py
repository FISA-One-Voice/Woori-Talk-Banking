"""액션별 필요 슬롯 정의, 화면 매핑, ASV 필요 액션 목록 (Issue #21).

Design Ref (Issue #21):
    §slot_schema.py — SLOT_SCHEMA / SCREEN_MAP / ASV_REQUIRED_ACTIONS
"""

# ── 액션별 필요 슬롯 ─────────────────────────────────────────────────────────────
# key: pending_action 값 (intent_node가 설정)
# value: 슬롯 이름 목록 (각 슬롯명은 service.py 파라미터명과 일치)
SLOT_SCHEMA: dict[str, list[str]] = {
    "transfer": ["recipient", "amount"],
    "auto_transfer": ["recipient", "amount", "cycle", "scheduled_day"],
}

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
}

# ── 수취인 검증이 필요한 액션 ────────────────────────────────────────────────────
# recipient 슬롯이 채워지는 즉시 resolve_node를 통해 수취인 존재 여부를 확인한다.
RECIPIENT_REQUIRED_ACTIONS: set[str] = {"transfer", "auto_transfer"}

# ── ASV 음성 인증이 필요한 액션 ─────────────────────────────────────────────────
# 금전 이동이 발생하는 액션만 포함한다.
# 해당 액션의 확인("네") 수신 후 awaiting_asv_audio=True를 설정한다.
ASV_REQUIRED_ACTIONS: set[str] = {
    "transfer",  # 계좌 이체
    "auto_transfer",  # 자동이체 등록
}

# ── 슬롯별 TTS 질문 템플릿 ────────────────────────────────────────────────────────
# slot_fill_node에서 첫 번째 누락 슬롯의 질문을 TTS로 반환한다.
SLOT_QUESTIONS: dict[str, str] = {
    "recipient": "누구에게 보낼까요? 별명이나 이름, 계좌번호를 말씀해 주세요.",
    "amount": "얼마를 보낼까요?",
    "cycle": "매월 또는 매주 중 어떤 주기로 보낼까요?",
    "scheduled_day": "매월 며칠에 이체할까요?",
}

# ── 실행 완료 화면 경로 ────────────────────────────────────────────────────────────
# execute_node 실행 후 navigate_to에 설정되어 프론트엔드 완료 화면으로 이동한다.
COMPLETE_SCREEN_MAP: dict[str, str] = {
    "transfer": "transfer/complete",
    "auto_transfer": "auto-transfer/complete",
}

# ── 액션 한국어 레이블 ────────────────────────────────────────────────────────────
# confirm_node의 확인 메시지 생성에 사용한다.
ACTION_LABELS: dict[str, str] = {
    "transfer": "이체",
    "auto_transfer": "자동이체 등록",
}

# ── 유효한 인텐트 목록 ─────────────────────────────────────────────────────────────
VALID_INTENTS: set[str] = set(SCREEN_MAP.keys())
