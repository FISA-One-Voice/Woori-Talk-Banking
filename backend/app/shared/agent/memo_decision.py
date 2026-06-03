"""이체 직후 메모 제안 턴 — 발화 파싱 헬퍼."""

from langchain_core.messages import AIMessage

from app.shared.agent.slot_schema import SLOT_QUESTIONS

_SKIP_KEYWORDS = (
    "건너뛰",
    "건너뛸",
    "안 할",
    "안할",
    "필요 없",
    "필요없",
    "괜찮",
    "됐어",
    "됐습니다",
    "아니요",
    "아니오",
    "싫어",
    "안 해",
)

_YES_KEYWORDS = ("네", "예", "응", "좋아", "할게", "남겨", "적어", "달아")

MEMO_CATEGORIES: tuple[str, ...] = (
    "식비",
    "교통비",
    "쇼핑",
    "의료비",
    "문화생활",
    "기타",
)


def last_user_text(messages: list) -> str:
    """대화 이력에서 마지막 사용자 발화 텍스트를 반환한다."""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return str(msg.content).strip()
    return ""


def match_memo_category(text: str) -> str | None:
    """발화에서 메모 카테고리(식비 등)를 찾으면 반환한다."""
    normalized = text.replace(" ", "")
    for category in MEMO_CATEGORIES:
        if category in normalized:
            return category
    return None


def is_memo_skip(text: str) -> bool:
    """메모 거절·건너뛰기 발화인지 판별한다."""
    normalized = text.replace(" ", "")
    return any(kw in normalized for kw in _SKIP_KEYWORDS)


def is_memo_accept_without_category(text: str) -> bool:
    """메모를 남기겠다는 긍정만 있고 카테고리는 없는 경우."""
    if is_memo_skip(text):
        return False
    if match_memo_category(text):
        return False
    normalized = text.replace(" ", "")
    return any(kw in normalized for kw in _YES_KEYWORDS)


def build_memo_decision_update(text: str, note_action: str = "add_note") -> dict:
    """메모 제안 대기 중 사용자 발화를 상태 갱신 dict로 변환한다.

    Args:
        text: 사용자 발화 텍스트.
        note_action: 메모 저장 액션 이름. 일반 이체는 "add_note",
            자동이체는 "add_auto_transfer_note".
    """
    if is_memo_skip(text):
        return {
            "awaiting_memo_decision": False,
            "pending_action": None,
            "navigate_to": "home",
            "messages": [AIMessage(content="알겠습니다. 홈으로 이동합니다.")],
        }

    category = match_memo_category(text)
    if category:
        return {
            "awaiting_memo_decision": False,
            "pending_action": note_action,
            "collected_slots": {"memo": category},
            "execution_ready": True,
            "messages": [AIMessage(content=f"{category}로 메모를 남기겠습니다.")],
        }

    if is_memo_accept_without_category(text):
        return {
            "awaiting_memo_decision": False,
            "pending_action": note_action,
            "collected_slots": {},
            "messages": [AIMessage(content=SLOT_QUESTIONS["memo"])],
        }

    return {
        "awaiting_memo_decision": True,
        "messages": [
            AIMessage(
                content=(
                    "식비, 교통비, 쇼핑, 의료비, 문화생활, 기타 중 말씀해 주시거나, "
                    "건너뛰기라고 말씀해 주세요."
                )
            )
        ],
    }
