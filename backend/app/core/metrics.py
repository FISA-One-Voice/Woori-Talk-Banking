from prometheus_client import Counter, Histogram

voice_stage_duration = Histogram(
    "voice_pipeline_stage_duration_seconds",
    "음성 파이프라인 단계별 레이턴시 (stt / agent / tts)",
    labelnames=["stage"],
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

agent_node_executions_total = Counter(
    "agent_node_executions_total",
    "에이전트 액션별 실행 횟수",
    labelnames=["node"],
)

agent_tool_duration_seconds = Histogram(
    "agent_tool_duration_seconds",
    "에이전트 tool별 실행 시간",
    labelnames=["node"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

app_error_total = Counter(
    "app_error_total",
    "AppError 코드별 발생 횟수",
    labelnames=["code"],
)

# 발생 전이어도 Grafana에서 0으로 표시되도록 사전 초기화
for _code in [
    "TOKEN_INVALID", "UNAUTHORIZED", "USER_NOT_FOUND",
    "STT_FAILED", "VOICE_AUDIO_INVALID_FORMAT", "VOICE_AUDIO_TOO_LARGE",
    "VOICE_AUDIO_TOO_LONG", "VOICE_VECTOR_EXTRACT_FAILED", "TTS_SPEED_OUT_OF_RANGE",
    "ASV_NOT_ENROLLED", "ASV_SERVER_ERROR", "ASV_TIMEOUT",
    "ACCOUNT_NOT_FOUND", "INVALID_ACCOUNT_FORMAT", "INSUFFICIENT_BALANCE",
    "TRANSFER_ACCOUNT_NOT_FOUND", "TRANSFER_PENDING", "TRANSFER_RECIPIENT_NOT_FOUND",
    "TRANSACTION_NOT_FOUND", "IDEMPOTENCY_KEY_USED", "TX_NOT_FOUND",
    "AUTO_ORDER_ACCOUNT_NOT_FOUND", "AUTO_ORDER_NOT_FOUND", "AUTO_ORDER_STATUS_INVALID",
    "AUTO_ORDER_TERMS_NOT_AGREED", "AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID",
    "AGENT_CONFIG_ERROR", "AGENT_INIT_FAILED",
    "SEARCH_FAILED", "INDEX_CREATION_FAILED",
    "EVENT_NOT_FOUND", "INVALID_EVENT_ID", "ALREADY_PARTICIPATED",
    "RECIPIENT_NOT_FOUND", "INTERNAL_ERROR", "INVALID_REQUEST", "SERVICE_UNAVAILABLE",
]:
    app_error_total.labels(code=_code)

external_api_calls_total = Counter(
    "external_api_calls_total",
    "외부 API 호출 성공·실패 횟수",
    labelnames=["service", "status"],
)

transfer_total = Counter(
    "transfer_total",
    "이체 실행 결과 횟수",
    labelnames=["status"],
)

auto_transfer_scheduler_runs_total = Counter(
    "auto_transfer_scheduler_runs_total",
    "APScheduler 자동이체 실행 결과 횟수",
    labelnames=["status"],
)

asv_verification_total = Counter(
    "asv_verification_total",
    "ASV 화자 인증 결과 횟수",
    labelnames=["result"],
)
