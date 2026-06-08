import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def write_voice_pipeline_record_async(record: dict[str, Any]) -> None:
    """voice_pipeline 레코드를 OpenSearch에 비동기로 기록합니다.

    opensearch-py의 client.index()는 동기 함수이므로 run_in_executor로
    thread pool에서 실행해 이벤트 루프 블로킹을 방지합니다.
    실패 시 warning 로그만 남기고 예외를 호출부로 전파하지 않습니다 (fire-and-forget).

    Args:
        record: voice_pipeline 인덱스에 저장할 레코드 딕셔너리.
    """
    loop = asyncio.get_event_loop()
    try:
        from app.core.opensearch import get_os_client

        client = get_os_client()
        await loop.run_in_executor(
            None,
            lambda: client.index(index="voice_pipeline", body=record),
        )
    except Exception as e:
        logger.warning("voice_pipeline OpenSearch 기록 실패: %s", e)


async def write_client_error_async(record: dict[str, Any]) -> None:
    """client_error 레코드를 OpenSearch app_logs에 비동기로 기록합니다."""
    loop = asyncio.get_event_loop()
    try:
        from app.core.opensearch import APP_LOGS_INDEX, get_os_client

        client = get_os_client()
        await loop.run_in_executor(
            None,
            lambda: client.index(index=APP_LOGS_INDEX, body=record),
        )
    except Exception as e:
        logger.warning("client_error OpenSearch 기록 실패: %s", e)


def write_transfer_audit_record(record: dict[str, Any]) -> None:
    """transfer_audit 레코드를 OpenSearch에 동기로 기록합니다.

    run_execute_transfer 는 LangGraph 도구로 동기 스레드에서 실행되므로
    이벤트 루프 없이 직접 client.index() 를 호출합니다.
    실패 시 warning 로그만 남기고 예외를 전파하지 않습니다 (fire-and-forget).
    """
    try:
        from app.core.opensearch import TRANSFER_AUDIT_INDEX, get_os_client

        get_os_client().index(index=TRANSFER_AUDIT_INDEX, body=record)
    except Exception as e:
        logger.warning("transfer_audit OpenSearch 기록 실패: %s", e)
