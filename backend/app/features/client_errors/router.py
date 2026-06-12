"""클라이언트(프론트엔드) 에러 리포트 라우터."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.jwt_utils import get_current_user_id
from app.core.opensearch_writer import write_client_error_async

router = APIRouter(prefix="/api/client-errors", tags=["ClientErrors"])


class ClientErrorRequest(BaseModel):
    feature: str
    error_type: str        # "timeout" | "network" | "http_4xx" | "http_5xx" | "unknown"
    error_message: str
    url: str | None = None
    method: str | None = None
    status_code: int | None = None


@router.post("/")
async def report_client_error(
    req: ClientErrorRequest,
    user_id: str = Depends(get_current_user_id),
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "ERROR",
        "event": "client_error",
        "feature": req.feature,
        "error_type": req.error_type,
        "error_message": req.error_message,
        "url": req.url,
        "method": req.method,
        "status_code": req.status_code,
        "user_id": user_id,
        "platform": "react-native",
    }
    asyncio.create_task(write_client_error_async(record))
    return {"success": True, "message": "에러 리포트가 접수되었습니다."}
