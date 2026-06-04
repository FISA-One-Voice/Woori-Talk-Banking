"""이체 직후 메모 제안 발화 파싱 테스트."""

from app.shared.agent.memo_decision import (
    build_memo_decision_update,
    is_memo_skip,
    match_memo_category,
)


class TestMemoDecisionParsing:
    def test_skip(self):
        assert is_memo_skip("건너뛸게")
        update = build_memo_decision_update("아니요 괜찮아요")
        assert update["awaiting_memo_decision"] is False
        assert update["navigate_to"] == "home"

    def test_category_triggers_execute(self):
        update = build_memo_decision_update("식비로 해줘")
        assert match_memo_category("식비로 해줘") == "식비"
        assert update["pending_action"] == "add_note"
        assert update["collected_slots"]["memo"] == "식비"
        assert update["execution_ready"] is True

    def test_yes_keeps_memo_awaiting_without_slot_fill_trap(self):
        update = build_memo_decision_update("네 남길게")
        assert update["awaiting_memo_decision"] is True
        assert update.get("pending_action") is None
        assert "execution_ready" not in update

    def test_skip_clears_tx_and_slots(self):
        update = build_memo_decision_update("건너뛰기")
        assert update["pending_action"] is None
        assert update["collected_slots"] == {}
        assert update["last_tx_id"] is None
        assert "건너뛰" in update["messages"][-1].content

    def test_unclear_reprompts(self):
        update = build_memo_decision_update("음...")
        assert update["awaiting_memo_decision"] is True
