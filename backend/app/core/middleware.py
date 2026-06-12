import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import request_id_var

logger = logging.getLogger(__name__)

_FEATURE_PREFIXES: list[tuple[str, str]] = [
    ("/api/auto-transfer", "auto_transfer"),
    ("/api/voice", "voice"),
    ("/api/transfer", "transfer"),
    ("/api/asset", "asset"),
    ("/api/auth", "auth"),
    ("/api/event", "event"),
    ("/api/recipients", "recipients"),
]


def _extract_feature(path: str) -> str:
    """요청 경로에서 feature 태그를 추출합니다.

    Args:
        path: HTTP 요청 경로 (예: "/api/voice").

    Returns:
        feature 태그 문자열. 매핑 없으면 "unknown".
    """
    for prefix, feature in _FEATURE_PREFIXES:
        if path.startswith(prefix):
            return feature
    return "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """모든 HTTP 요청/응답을 JSON 구조화 로그로 기록하는 미들웨어.

    X-Request-ID 헤더를 읽거나 없으면 UUID를 생성해 ContextVar에 저장합니다.
    응답 헤더에도 X-Request-ID를 포함시켜 클라이언트가 추적 가능하게 합니다.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        feature = _extract_feature(request.url.path)
        start = time.monotonic()

        try:
            logger.info(
                "request_start",
                extra={
                    "event": "request_start",
                    "method": request.method,
                    "path": request.url.path,
                    "feature": feature,
                },
            )
            response = await call_next(request)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "request_end",
                extra={
                    "event": "request_end",
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "feature": feature,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 예외 발생 시에도 ContextVar 누수 방지
            request_id_var.reset(token)
