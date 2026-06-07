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
