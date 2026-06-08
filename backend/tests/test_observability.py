"""observability 코어 모듈 단위 테스트.

검증 범위:
    - request_context : ContextVar UUID 생성·보존·리셋, async 태스크 격리
    - logging_config  : _RequestIdFilter request_id 주입, JSON 포매터 필드
    - middleware       : _extract_feature 경로→태그 매핑, X-Request-ID 전파
    - metrics          : 8개 메트릭 임포트, app_error_total 사전 초기화·증감
    - opensearch_writer: 성공 시 예외 미전파, 실패 시 warning 로그만 출력

실행:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_observability.py -v
"""
import asyncio
import json
import logging
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RequestLoggingMiddleware, _extract_feature
from app.core.request_context import get_request_id, request_id_var, set_request_id


# ──────────────────────────────────────────────────────────────────────────────
# 1. request_context
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=False)
def clean_request_id():
    """각 테스트 전후로 ContextVar를 빈 문자열로 초기화·복구."""
    token = request_id_var.set("")
    yield
    request_id_var.reset(token)


def test_request_id_generates_uuid_when_unset(clean_request_id):
    rid = get_request_id()
    uuid.UUID(rid)  # 유효한 UUID가 아니면 ValueError


def test_request_id_returns_same_value_on_repeat_calls(clean_request_id):
    assert get_request_id() == get_request_id()


def test_set_request_id_stores_custom_value(clean_request_id):
    token = set_request_id("fixed-id-abc")
    try:
        assert get_request_id() == "fixed-id-abc"
    finally:
        request_id_var.reset(token)


def test_reset_restores_previous_state(clean_request_id):
    token = set_request_id("temp-id")
    request_id_var.reset(token)
    # 리셋 후 빈 문자열 → 새 UUID 생성, 이전 값과 달라야 함
    new_rid = get_request_id()
    assert new_rid != "temp-id"
    uuid.UUID(new_rid)


async def test_async_task_isolation():
    """서로 다른 asyncio 태스크는 독립적인 request_id를 가져야 한다."""
    results: dict[str, str] = {}

    async def task(name: str, rid: str) -> None:
        token = request_id_var.set(rid)
        await asyncio.sleep(0)  # 다른 태스크로 컨텍스트 전환
        results[name] = get_request_id()
        request_id_var.reset(token)

    await asyncio.gather(task("A", "id-for-A"), task("B", "id-for-B"))
    assert results["A"] == "id-for-A"
    assert results["B"] == "id-for-B"


# ──────────────────────────────────────────────────────────────────────────────
# 2. logging_config
# ──────────────────────────────────────────────────────────────────────────────


def test_request_id_filter_injects_field():
    from app.core.logging_config import _RequestIdFilter

    flt = _RequestIdFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="",
        lineno=0, msg="hello", args=(), exc_info=None,
    )
    token = request_id_var.set("inject-test-id")
    try:
        result = flt.filter(record)
    finally:
        request_id_var.reset(token)

    assert result is True
    assert record.request_id == "inject-test-id"  # type: ignore[attr-defined]


def test_json_formatter_includes_required_fields(capsys):
    from app.core.logging_config import _AppJsonFormatter, _RequestIdFilter

    fmt = _AppJsonFormatter()
    flt = _RequestIdFilter()

    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    handler.addFilter(flt)

    test_logger = logging.getLogger("test.obs.json_fields")
    test_logger.handlers = [handler]
    test_logger.propagate = False
    test_logger.setLevel(logging.INFO)

    token = request_id_var.set("fmt-test-id")
    try:
        test_logger.info("test_message")
    finally:
        request_id_var.reset(token)
        test_logger.handlers.clear()

    captured = capsys.readouterr()
    out = (captured.out + captured.err).strip()
    data = json.loads(out.split("\n")[-1])

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert "logger" in data
    assert data["request_id"] == "fmt-test-id"


def test_setup_logging_runs_without_error():
    from app.core.logging_config import setup_logging
    setup_logging()  # 예외 없이 완료되어야 함


# ──────────────────────────────────────────────────────────────────────────────
# 3. middleware._extract_feature (순수 단위 테스트)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path,expected", [
    ("/api/voice/record", "voice"),
    ("/api/voice", "voice"),
    ("/api/transfer/execute", "transfer"),
    ("/api/auto-transfer/list", "auto_transfer"),
    ("/api/auto-transfer", "auto_transfer"),
    ("/api/asset/balance", "asset"),
    ("/api/auth/login", "auth"),
    ("/api/event/join", "event"),
    ("/api/recipients", "recipients"),
    ("/health", "unknown"),
    ("/metrics", "unknown"),
    ("/api/unknown-feature/x", "unknown"),
])
def test_extract_feature(path: str, expected: str):
    assert _extract_feature(path) == expected


# ──────────────────────────────────────────────────────────────────────────────
# 4. RequestLoggingMiddleware 통합 (최소 FastAPI 앱)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def middleware_client():
    """RequestLoggingMiddleware만 추가한 최소 FastAPI 앱 — DB 불필요."""
    _app = FastAPI()
    _app.add_middleware(RequestLoggingMiddleware)

    @_app.get("/api/voice/test")
    def _voice():
        return {"ok": True}

    with TestClient(_app) as c:
        yield c


def test_middleware_adds_x_request_id_header(middleware_client):
    resp = middleware_client.get("/api/voice/test")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    uuid.UUID(resp.headers["x-request-id"])


def test_middleware_preserves_incoming_x_request_id(middleware_client):
    custom_id = "client-trace-xyz-999"
    resp = middleware_client.get(
        "/api/voice/test",
        headers={"X-Request-ID": custom_id},
    )
    assert resp.headers["x-request-id"] == custom_id


def test_middleware_different_requests_get_different_ids(middleware_client):
    r1 = middleware_client.get("/api/voice/test")
    r2 = middleware_client.get("/api/voice/test")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


# ──────────────────────────────────────────────────────────────────────────────
# 5. metrics
# ──────────────────────────────────────────────────────────────────────────────


def test_all_metrics_importable():
    from app.core.metrics import (
        agent_node_executions_total,
        agent_tool_duration_seconds,
        app_error_total,
        asv_verification_total,
        auto_transfer_scheduler_runs_total,
        external_api_calls_total,
        transfer_total,
        voice_stage_duration,
    )
    for metric in [
        agent_node_executions_total, agent_tool_duration_seconds,
        app_error_total, asv_verification_total,
        auto_transfer_scheduler_runs_total, external_api_calls_total,
        transfer_total, voice_stage_duration,
    ]:
        assert metric is not None


@pytest.mark.parametrize("code", [
    "TOKEN_INVALID", "UNAUTHORIZED", "USER_NOT_FOUND",
    "STT_FAILED", "ASV_TIMEOUT", "INSUFFICIENT_BALANCE",
    "AGENT_CONFIG_ERROR", "EVENT_NOT_FOUND", "INTERNAL_ERROR",
    "AUTO_ORDER_NOT_FOUND", "SEARCH_FAILED", "SERVICE_UNAVAILABLE",
])
def test_app_error_total_preinitialized(code: str):
    """지정 에러 코드가 metrics.py 임포트 시점에 사전 등록되어야 한다."""
    from app.core.metrics import app_error_total

    assert (code,) in app_error_total._metrics, (
        f"'{code}' 코드가 app_error_total에 사전 초기화되지 않음"
    )


def test_app_error_total_increments():
    """inc() 호출 후 카운터 값이 1 증가해야 한다."""
    from app.core.metrics import app_error_total

    counter = app_error_total.labels(code="__PYTEST_ONLY__")
    before = counter._value.get()
    counter.inc()
    assert counter._value.get() == before + 1.0


def test_voice_stage_duration_observe_all_stages():
    """세 stage 모두 observe() 호출 시 예외 없이 동작해야 한다."""
    from app.core.metrics import voice_stage_duration

    voice_stage_duration.labels(stage="stt").observe(0.45)
    voice_stage_duration.labels(stage="agent").observe(1.20)
    voice_stage_duration.labels(stage="tts").observe(0.30)


# ──────────────────────────────────────────────────────────────────────────────
# 6. opensearch_writer
# ──────────────────────────────────────────────────────────────────────────────


async def test_opensearch_writer_success_does_not_raise(monkeypatch):
    """기록 성공 시 예외를 호출부로 전파하지 않아야 한다."""
    mock_client = MagicMock()
    mock_client.index.return_value = {"result": "created"}
    monkeypatch.setattr("app.core.opensearch.get_os_client", lambda: mock_client)

    from app.core import opensearch_writer
    # 모듈 캐시 갱신을 위해 reload가 아닌 직접 임포트
    from app.core.opensearch_writer import write_voice_pipeline_record_async

    await write_voice_pipeline_record_async({"intent": "transfer", "stt_ms": 400})
    mock_client.index.assert_called_once()


async def test_opensearch_writer_failure_logs_warning_not_raise(monkeypatch, caplog):
    """기록 실패 시 WARNING 로그만 남기고 예외를 전파하지 않아야 한다."""
    mock_client = MagicMock()
    mock_client.index.side_effect = ConnectionError("OpenSearch unavailable")
    monkeypatch.setattr("app.core.opensearch.get_os_client", lambda: mock_client)

    from app.core.opensearch_writer import write_voice_pipeline_record_async

    with caplog.at_level(logging.WARNING, logger="app.core.opensearch_writer"):
        await write_voice_pipeline_record_async({"intent": "balance"})  # 예외 미전파

    assert len(caplog.records) >= 1
    assert any("실패" in r.message for r in caplog.records)
