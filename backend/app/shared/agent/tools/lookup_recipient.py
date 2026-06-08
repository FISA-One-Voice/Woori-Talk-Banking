import logging
import uuid

from langchain_core.tools import tool

from app.core.database import SessionLocal
from app.features.recipients.service import lookup_recipient_by_voice

logger = logging.getLogger(__name__)


@tool
def lookup_recipient(user_id: str, recipient: str) -> str | None:
    """음성에서 추출한 별명·이름·전화번호로 등록 수취인의 실명을 조회합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        recipient: 발화에서 추출한 수취인 식별값 (별명, 실명, 전화번호 모두 허용).

    Returns:
        수취인 실명(str). 찾지 못하면 None.
    """
    logger.info("lookup_recipient_start", extra={"event": "lookup_recipient_start", "user_id": user_id, "recipient": recipient})
    db = SessionLocal()
    try:
        resolved = lookup_recipient_by_voice(db, uuid.UUID(user_id), recipient)
        result = resolved.recipient_name if resolved else None
        logger.info("lookup_recipient_result", extra={"event": "lookup_recipient_result", "user_id": user_id, "result": result})
        return resolved.recipient_name if resolved else None
    except Exception as e:
        logger.error("lookup_recipient_failed", extra={"event": "lookup_recipient_failed", "user_id": user_id, "error": str(e)})
        return None
    finally:
        db.close()
