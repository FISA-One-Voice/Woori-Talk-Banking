"""전화·계좌만 말한 턴 — 송금 의도 확인 테스트."""

from langchain_core.messages import AIMessage, HumanMessage

from app.shared.agent.transfer_clarification import (
    build_transfer_clarification_offer,
    build_transfer_clarification_response,
    is_recipient_only_utterance,
    should_offer_transfer_clarification,
)
from app.shared.voice.message_utils import tts_text_from_messages


class TestRecipientOnlyDetection:
    def test_phone_only(self):
        assert is_recipient_only_utterance("010 1111 0003") is True

    def test_phone_with_transfer_keyword(self):
        assert is_recipient_only_utterance("010 1111 0003 이체해줘") is False

    def test_phone_with_amount(self):
        assert is_recipient_only_utterance("010 1111 0003 3만원") is False


class TestTransferClarificationFlow:
    def test_offer_sets_awaiting_flag(self):
        update = build_transfer_clarification_offer("010 1111 0003")
        assert update["awaiting_transfer_clarification"] is True
        assert update["draft_recipient"] == "010 1111 0003"
        assert "송금" in update["messages"][0].content

    def test_yes_starts_transfer(self):
        update = build_transfer_clarification_response("네", "010 1111 0003")
        assert update["pending_action"] == "transfer"
        assert update["navigate_to"] == "transfer"
        assert update["collected_slots"]["recipient"] == "010 1111 0003"
        assert update["awaiting_transfer_clarification"] is False

    def test_no_clears_state(self):
        update = build_transfer_clarification_response("아니요", "010 1111 0003")
        assert update["awaiting_transfer_clarification"] is False
        assert update.get("pending_action") is None

    def test_should_offer_when_idle(self):
        assert (
            should_offer_transfer_clarification(
                "010 1111 0003",
                pending_action=None,
                awaiting_memo_decision=False,
                awaiting_transfer_clarification=False,
            )
            is True
        )


class TestTtsMessageExtraction:
    def test_uses_last_ai_not_human(self):
        messages = [
            HumanMessage(content="010 1111 0003"),
            AIMessage(content="송금을 도와드릴까요?"),
        ]
        assert tts_text_from_messages(messages) == "송금을 도와드릴까요?"

    def test_fallback_when_no_ai_message(self):
        messages = [HumanMessage(content="010 1111 0003")]
        text = tts_text_from_messages(messages)
        assert text != "010 1111 0003"
        assert "도와드릴" in text
