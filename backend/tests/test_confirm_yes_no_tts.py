"""확인(네/아니오) TTS에 공통 안내 문구가 포함되는지 검증."""

from app.features.transfer.service import format_confirm_message
from app.shared.agent.slot_schema import CONFIRM_YES_NO_SUFFIX
from app.shared.agent.transfer_clarification import clarification_offer_message


class TestConfirmYesNoSuffix:
    def test_transfer_confirm_includes_suffix(self):
        msg = format_confirm_message(
            "transfer",
            {"recipient": "엄마", "amount": 10000},
        )
        assert "이체할까요?" in msg
        assert msg.endswith(CONFIRM_YES_NO_SUFFIX.strip())

    def test_auto_transfer_confirm_includes_suffix(self):
        msg = format_confirm_message(
            "auto_transfer",
            {
                "recipient": "엄마",
                "amount": 50000,
                "cycle": "monthly",
                "scheduled_day": 15,
            },
        )
        assert CONFIRM_YES_NO_SUFFIX.strip() in msg

    def test_clarification_offer_includes_suffix(self):
        assert CONFIRM_YES_NO_SUFFIX.strip() in clarification_offer_message("phone")
        assert CONFIRM_YES_NO_SUFFIX.strip() in clarification_offer_message("account")
