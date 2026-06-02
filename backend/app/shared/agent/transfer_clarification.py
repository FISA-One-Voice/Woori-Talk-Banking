"""전화·계좌만 말한 애매한 턴 — 송금 의도 확인 멀티턴."""

import re

from langchain_core.messages import AIMessage

from app.features.recipients.service import classify_recipient_input

_TRANSFER_KEYWORDS = (
    "이체",
    "송금",
    "보내",
    "보낼",
    "보내줘",
    "이체해",
    "송금해",
    "송금하",
    "이체하",
    "송금할",
    "이체할",
    "보내고",
    "이체하고",
)

_BALANCE_KEYWORDS = ("잔액", "잔고", "얼마 남", "남은 돈", "남은돈")

_AMOUNT_PATTERN = re.compile(
    r"(\d+[\d,\s]*\s*원|"
    r"\d+\s*만\s*원?|"
    r"\d+만|"
    r"[일이삼사오육칠팔구십백천만억]+원)"
)

_YES_KEYWORDS = ("네", "예", "응", "맞아", "그래", "좋아", "해줘", "할게", "송금", "이체")

_NO_KEYWORDS = (
    "아니",
    "아뇨",
    "안 할",
    "안할",
    "취소",
    "됐어",
    "괜찮",
    "싫어",
    "하지 마",
    "하지마",
)


def _normalize(text: str) -> str:
    return text.replace(" ", "").strip()


def has_transfer_intent_keyword(text: str) -> bool:
    """발화에 이체·송금 의도 키워드가 있는지."""
    normalized = _normalize(text)
    return any(kw in normalized for kw in _TRANSFER_KEYWORDS)


def has_amount_hint(text: str) -> bool:
    """금액이 함께 언급된 것으로 보이는지."""
    if _AMOUNT_PATTERN.search(text):
        return True
    normalized = _normalize(text)
    return any(token in normalized for token in ("만원", "천원", "억원", "원을", "원보내"))


def is_recipient_only_utterance(text: str) -> bool:
    """전화·계좌만 있고 이체 의도·금액이 없는 발화인지."""
    stripped = text.strip()
    if not stripped:
        return False
    if has_transfer_intent_keyword(stripped):
        return False
    if has_amount_hint(stripped):
        return False
    kind = classify_recipient_input(stripped)
    return kind in ("phone", "account")


def is_clarification_yes(text: str) -> bool:
    normalized = _normalize(text)
    return any(kw in normalized for kw in _YES_KEYWORDS)


def is_clarification_no(text: str) -> bool:
    normalized = _normalize(text)
    return any(kw in normalized for kw in _NO_KEYWORDS)


def is_balance_request(text: str) -> bool:
    normalized = _normalize(text)
    return any(kw in normalized for kw in _BALANCE_KEYWORDS)


def clarification_offer_message(kind: str) -> str:
    """수취인 힌트 형식별 TTS 안내."""
    if kind == "account":
        return (
            "송금을 도와드릴까요? "
            "등록된 별명이나 전화번호를 말씀해 주셔도 됩니다. "
            "네 또는 아니오로 말씀해 주세요."
        )
    return "송금을 도와드릴까요? 네 또는 아니오로 말씀해 주세요."


def build_transfer_clarification_offer(user_text: str) -> dict:
    """애매한 수취인 힌트 턴 — 송금 여부 질문."""
    kind = classify_recipient_input(user_text.strip())
    return {
        "awaiting_transfer_clarification": True,
        "draft_recipient": user_text.strip(),
        "navigate_to": None,
        "messages": [AIMessage(content=clarification_offer_message(kind))],
    }


def build_transfer_clarification_response(user_text: str, draft_recipient: str) -> dict:
    """송금 확인 대기 중 사용자 발화 처리."""
    if is_clarification_no(user_text):
        return {
            "awaiting_transfer_clarification": False,
            "draft_recipient": None,
            "pending_action": None,
            "collected_slots": {},
            "navigate_to": None,
            "messages": [
                AIMessage(
                    content="알겠습니다. 이체, 잔액 조회, 홈 이동 중 필요하신 것을 말씀해 주세요."
                )
            ],
        }

    if is_balance_request(user_text):
        return {
            "awaiting_transfer_clarification": False,
            "draft_recipient": None,
            "pending_action": None,
            "collected_slots": {},
            "navigate_to": "balance",
            "messages": [AIMessage(content="잔액 화면으로 이동합니다.")],
        }

    if is_clarification_yes(user_text) or has_transfer_intent_keyword(user_text):
        return {
            "awaiting_transfer_clarification": False,
            "draft_recipient": None,
            "pending_action": "transfer",
            "collected_slots": {"recipient": draft_recipient},
            "recipient_validated": False,
            "navigate_to": "transfer",
            "messages": [AIMessage(content="이체 화면으로 이동합니다. 이어서 안내해 드리겠습니다.")],
        }

    return {
        "awaiting_transfer_clarification": True,
        "draft_recipient": draft_recipient,
        "messages": [
            AIMessage(
                content=(
                    "송금을 원하시면 네, 원하지 않으시면 아니오로 말씀해 주세요. "
                    "잔액 조회를 원하시면 잔액이라고 말씀해 주세요."
                )
            )
        ],
    }


def should_offer_transfer_clarification(
    user_text: str,
    *,
    pending_action: str | None,
    awaiting_memo_decision: bool,
    awaiting_transfer_clarification: bool,
) -> bool:
    """송금 의도 확인 턴을 시작할지."""
    if awaiting_transfer_clarification or awaiting_memo_decision:
        return False
    if pending_action:
        return False
    return is_recipient_only_utterance(user_text)
