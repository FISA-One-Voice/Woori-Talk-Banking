"""transfer 동적 누락 슬롯 테스트."""

from app.shared.agent.slot_schema import transfer_missing_slots


def test_transfer_missing_only_amount():
    missing = transfer_missing_slots(
        {"recipient": "엄마", "recipient_id": "r1", "bank_name": "국민은행"}
    )
    assert missing == ["amount"]


def test_unregistered_account_needs_bank():
    missing = transfer_missing_slots({"recipient": "99998888777766"})
    assert missing == ["bank_name", "amount"]


def test_unregistered_account_with_bank_needs_amount():
    missing = transfer_missing_slots(
        {"recipient": "99998888777766", "bank_name": "신한은행"}
    )
    assert missing == ["amount"]
