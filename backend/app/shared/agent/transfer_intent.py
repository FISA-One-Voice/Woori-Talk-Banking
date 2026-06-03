"""일회성 송금 intent — bare 발화용 좁은 fast path + 재시작 판별."""

import re

from langchain_core.messages import HumanMessage

from app.shared.agent.session_reset import clear_conversation_messages
from app.shared.agent.slot_schema import SCREEN_MAP
from app.shared.agent.transfer_clarification import has_amount_hint

_TRANSFER_START_HINTS = (
    "이체",
    "송금",
    "보내",
    "송금해",
    "이체해",
    "돈보내",
    "송금하기",
    "이체하기",
)

_AUTO_TRANSFER_HINTS = (
    "자동이체",
    "정기이체",
    "정기송금",
    "자동송금",
    "매달이체",
)

_HOME_HINTS = ("홈으로", "처음으로", "홈화면", "홈이동", "메인화면")

_BALANCE_HINTS = ("잔액", "잔고", "얼마남", "남은돈", "계좌잔액")

_RECIPIENT_PARTICLE = re.compile(r"(에게|한테|께)")
_PHONE_IN_TEXT = re.compile(r"01[0-9][\s-]?[0-9]{3,4}[\s-]?[0-9]{4}")


def _normalize(text: str) -> str:
    return text.replace(" ", "")


def is_plain_transfer_start(text: str) -> bool:
    """일회성 이체 시작 발화(자동이체·홈·잔액 제외)."""
    normalized = _normalize(text)
    if any(hint in normalized for hint in _AUTO_TRANSFER_HINTS):
        return False
    if any(hint in normalized for hint in _HOME_HINTS) or normalized in ("홈",):
        return False
    if any(hint in normalized for hint in _BALANCE_HINTS):
        return False
    return any(hint in normalized for hint in _TRANSFER_START_HINTS)


def has_recipient_hint(text: str) -> bool:
    """수취인 이름·조사·전화번호가 포함된 발화인지."""
    stripped = text.strip()
    if not stripped:
        return False
    if _RECIPIENT_PARTICLE.search(stripped):
        return True
    return _PHONE_IN_TEXT.search(stripped) is not None


def should_use_bare_transfer_fast_start(text: str) -> bool:
    """수취인·금액 없이 송금만 말한 bare 발화 — pre-LLM fast path 대상."""
    return (
        is_plain_transfer_start(text)
        and not has_amount_hint(text)
        and not has_recipient_hint(text)
    )


def build_bare_transfer_start_update(user_text: str) -> dict:
    """bare 송금 발화 — transfer 시작 후 slot_fill에서 수취인 질문."""
    return {
        "pending_action": "transfer",
        "navigate_to": SCREEN_MAP["transfer"],
        "collected_slots": {},
        "recipient_validated": False,
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "execution_ready": False,
        "asv_retry_count": 0,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "last_tx_id": None,
        "messages": [
            *clear_conversation_messages(),
            HumanMessage(content=user_text),
        ],
    }
