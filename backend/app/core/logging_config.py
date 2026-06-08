import logging
import logging.handlers
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from app.core.request_context import get_request_id

_KST = timezone(timedelta(hours=9))
_LOG_FILE = Path.home() / "woori-logs" / "app.log"


class _RequestIdFilter(logging.Filter):
    """모든 로그 레코드에 request_id 필드를 자동 주입하는 필터."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()  # type: ignore[attr-defined]
        return True


class _AppJsonFormatter(JsonFormatter):
    """timestamp · level · logger · request_id 필드를 포함하는 JSON 포매터."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=_KST
        ).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["request_id"] = getattr(record, "request_id", "")


def setup_logging() -> None:
    """루트 로거를 JSON 포맷 StreamHandler로 교체합니다.

    기존 핸들러를 모두 제거하고 새 핸들러를 등록해 중복 출력을 방지합니다.
    앱 시작 시 main.py에서 가장 먼저 호출해야 합니다.
    """
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    fmt = _AppJsonFormatter()
    flt = _RequestIdFilter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    stream_handler.addFilter(flt)
    root.addHandler(stream_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(flt)
    root.addHandler(file_handler)
