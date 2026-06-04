"""
자동이체 해지 에이전트 툴.

에이전트가 recipient 슬롯 수집 + 사용자 확인("네")을 받은 뒤 호출한다.
해당 수취인의 active/paused 상태 자동이체를 cancelled로 변경한다.
"""

import logging
import uuid

from langchain_core.tools import tool
from sqlalchemy import and_

from app.core.database import SessionLocal
from app.core.exception import AppError
from app.features.recipients.service import lookup_recipient_by_voice

logger = logging.getLogger(__name__)
from app.models.standing_order import StandingOrder


@tool
def cancel_auto_transfer(user_id: str, recipient: str) -> str:
    """확인 완료 후 수취인의 자동이체를 해지합니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.
        recipient: 해지할 수취인 이름 또는 별명.

    Returns:
        성공/실패 결과 TTS 텍스트.
    """
    db = SessionLocal()
    try:
        user_uuid = uuid.UUID(user_id)

        resolved = lookup_recipient_by_voice(db, user_uuid, recipient)
        if not resolved or not resolved.recipient_id:
            return f"'{recipient}'에 대한 등록 수취인을 찾을 수 없습니다."

        orders = (
            db.query(StandingOrder)
            .filter(
                and_(
                    StandingOrder.user_id == user_uuid,
                    StandingOrder.recipient_id == resolved.recipient_id,
                    StandingOrder.status.in_(["active", "paused"]),
                )
            )
            .all()
        )

        if not orders:
            return f"{resolved.recipient_name}에게 설정된 자동이체가 없습니다."

        for order in orders:
            order.status = "cancelled"
        db.commit()

        count = len(orders)
        name = resolved.recipient_name
        if count == 1:
            return f"{name}에게 설정된 자동이체가 해지되었습니다."
        return f"{name}에게 설정된 자동이체 {count}건이 모두 해지되었습니다."

    except AppError as e:
        db.rollback()
        return e.user_message or e.message
    except Exception as e:
        db.rollback()
        logger.error(
            "cancel_auto_transfer 실패: user=%s recipient=%s error=%s",
            user_id, recipient, e,
        )
        return "자동이체 해지 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        db.close()
