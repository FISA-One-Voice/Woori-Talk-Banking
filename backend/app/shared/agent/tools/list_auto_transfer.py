"""자동이체 조회 Agent Tool.

"자동이체 목록 보여줘", "자동이체 뭐 있어" 같은 음성 명령을 처리합니다.
"""

import logging

from langchain_core.tools import tool

from app.core.database import SessionLocal
from app.core.exception import AppError
from app.features.auto_transfer.service import list_auto_transfers

logger = logging.getLogger(__name__)

_CYCLE_LABEL = {"monthly": "매월", "weekly": "매주"}


@tool
def list_auto_transfer(user_id: str) -> str:
    """사용자의 활성 자동이체 목록을 조회합니다.

    "자동이체 목록 보여줘", "자동이체 뭐 있어", "자동이체 확인해줘" 같은 발화에 사용됩니다.

    Args:
        user_id: JWT에서 추출한 사용자 ID.

    Returns:
        TTS로 읽을 문자열.
    """
    db = None
    try:
        db = SessionLocal()
        orders = list_auto_transfers(db, user_id, status="active")
        if not orders:
            return "현재 등록된 자동이체가 없습니다."

        lines = [f"등록된 자동이체 내역이 {len(orders)}건 있습니다."]
        for i, o in enumerate(orders, 1):
            cycle = _CYCLE_LABEL.get(o.cycle, o.cycle)
            if o.cycle == "monthly" and o.scheduled_day:
                timing = f"{cycle} {o.scheduled_day}일"
            elif o.cycle == "weekly" and o.scheduled_dow is not None:
                days = ["월", "화", "수", "목", "금", "토", "일"]
                timing = f"{cycle} {days[o.scheduled_dow]}요일"
            else:
                timing = cycle
            lines.append(f"{i}번. {o.to_name} {o.amount:,}원 {timing}")
        return " ".join(lines)

    except AppError as e:
        return e.user_message or e.message
    except Exception as e:
        logger.error("list_auto_transfer 실패: user=%s error=%s", user_id, e)
        return "자동이체 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    finally:
        if db is not None:
            db.close()
