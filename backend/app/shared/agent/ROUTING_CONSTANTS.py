"""멀티에이전트 라우팅 계약 상수.

포함하는 것  : 에이전트 간 읽기 경계, navigate_to 허용값
포함 안 하는 것: 각 에이전트의 domain action 집합 (해당 subgraph 파일 내부에 정의)
"""

# ── 각 에이전트의 읽기 계약 ────────────────────────────────────────────────────
# 단독 테스트 시 최소 mock state 구성 기준으로 사용한다.

TRANSFER_READ: frozenset[str] = frozenset({
    "messages", "user_id",
    "pending_action", "collected_slots",
    "awaiting_confirmation", "awaiting_asv_audio",
    "execution_ready", "recipient_validated", "asv_retry_count",
    "awaiting_memo_decision", "awaiting_transfer_clarification",
    "draft_recipient", "last_tx_id", "last_order_id",
})

ASSET_READ: frozenset[str] = frozenset({
    "messages", "user_id", "analytics_period", "agent_domain",
})

RAG_READ: frozenset[str] = frozenset({
    "messages", "user_id",
})

# ── 각 에이전트가 설정 가능한 navigate_to 값 ──────────────────────────────────

SUPERVISOR_NAVIGATE_VALUES: frozenset[str | None] = frozenset({"home", None})

TRANSFER_NAVIGATE_VALUES: frozenset[str | None] = frozenset({
    "transfer", "transfer/complete",
    "auto-transfer", "auto-transfer/complete",
    "home", None,
})

ASSET_NAVIGATE_VALUES: frozenset[str | None] = frozenset({
    "asset", "asset/history", "balance", "report", None,
})

RAG_NAVIGATE_VALUES: frozenset[str | None] = frozenset({None})
