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
