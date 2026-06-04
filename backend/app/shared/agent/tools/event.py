# =============================================================================
# backend/app/shared/agent/tools/event.py
#
# [이 파일의 역할]
# AI 에이전트가 이벤트 관련 발화를 인식하면 자동으로 실행되는 tool 함수입니다.
#
# [에이전트 연결 흐름]
# 1. 사용자: "이벤트 뭐 있어?" 발화
# 2. 에이전트: get_event_list tool 선택·실행
# 3. tool: DB에서 이벤트 조회 후 TTS 친화 문장 반환
# 4. 에이전트: 반환된 문장을 TTS로 읽어줌
# =============================================================================

from langchain_core.tools import tool

from app.core.database import get_db
from app.core.exception import AppError
from app.features.event.service import get_events_tts_text


@tool
def get_event_list(user_id: str) -> str:  # noqa: D401
    """이벤트 목록 조회를 요청할 때 호출합니다.

    트리거 발화 예시:
      - "이벤트 뭐 있어?"
      - "이벤트 알려줘"
      - "지금 이벤트 있어?"
      - "혜택 있는 이벤트 알려줘"

    Args:
        user_id: JWT에서 추출한 사용자 ID. voice/router.py 가 주입합니다.
                 이 파라미터는 모든 tool에 포함되어야 합니다 (인증 검증용).

    Returns:
        TTS로 읽힐 자연어 문자열.
        반드시 마크다운 없이, 숫자는 한국어로 작성하십시오.
        예: "현재 진행 중인 이벤트는 두 개입니다. 첫 번째, 봄맞이 이벤트. 두 번째, 신규 가입 혜택."

    """
    db = next(get_db())
    try:
        result = get_events_tts_text(db)
        return f"이벤트 화면으로 이동합니다. {result}"
    except AppError as e:
        return e.user_message or e.message
    finally:
        db.close()
