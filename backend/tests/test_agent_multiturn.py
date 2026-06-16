"""멀티턴 에이전트 공통 스키마 테스트."""

from app.shared.agent.slot_schema import (
    ASV_REQUIRED_ACTIONS,
    SCREEN_MAP,
    SLOT_QUESTIONS,
    SLOT_SCHEMA,
)


class TestSlotSchema:
    """SLOT_SCHEMA / SCREEN_MAP / ASV_REQUIRED_ACTIONS 불변성 검증."""

    def test_transfer_slots_defined(self):
        """transfer 액션은 recipient, amount 슬롯을 요구해야 한다."""
        assert SLOT_SCHEMA["transfer"] == ["recipient", "amount"]

    def test_auto_transfer_slots_defined(self):
        """auto_transfer 액션은 4개 슬롯을 요구해야 한다."""
        assert set(SLOT_SCHEMA["auto_transfer"]) == {
            "recipient",
            "amount",
            "cycle",
            "scheduled_day",
        }

    def test_screen_map_has_all_intents(self):
        """SCREEN_MAP에 transfer, auto_transfer, balance, history, event가 모두 있어야 한다."""
        for intent in ["transfer", "auto_transfer", "balance", "history", "event"]:
            assert intent in SCREEN_MAP, f"SCREEN_MAP에 '{intent}'가 없습니다."

    def test_asv_required_actions_subset_of_slot_schema(self):
        """ASV 필요 액션은 SLOT_SCHEMA에 정의된 액션의 부분집합이어야 한다."""
        assert ASV_REQUIRED_ACTIONS.issubset(set(SLOT_SCHEMA.keys()))

    def test_slot_questions_cover_all_slots(self):
        """SLOT_QUESTIONS에 모든 슬롯 이름이 포함되어야 한다."""
        all_slots = {s for slots in SLOT_SCHEMA.values() for s in slots}
        for slot in all_slots:
            assert slot in SLOT_QUESTIONS, f"SLOT_QUESTIONS에 '{slot}'가 없습니다."
