"""bare 송금 발화 — 좁은 fast path 단위 테스트."""

from app.shared.agent.transfer_intent import (
    build_bare_transfer_start_update,
    should_use_bare_transfer_fast_start,
)


class TestBareTransferFastStartDetection:
    def test_bare_utterances_use_fast_path(self):
        assert should_use_bare_transfer_fast_start("송금하고 싶어")
        assert should_use_bare_transfer_fast_start("이체 하고 싶어")
        assert should_use_bare_transfer_fast_start("이체해줘")
        assert should_use_bare_transfer_fast_start("돈 보내고 싶어")

    def test_compound_utterances_skip_fast_path(self):
        assert not should_use_bare_transfer_fast_start("이도원한테 4500원 보내고 싶어")
        assert not should_use_bare_transfer_fast_start("이도헌에게 4천원을 보내고싶어")
        assert not should_use_bare_transfer_fast_start(
            "010 1111 0003으로 돈 보내고 싶어"
        )

    def test_auto_transfer_not_bare(self):
        assert not should_use_bare_transfer_fast_start("자동이체 등록")

    def test_build_start_sets_transfer_pending(self):
        update = build_bare_transfer_start_update("송금하고 싶어")
        assert update["pending_action"] == "transfer"
        assert update["navigate_to"] == "transfer"
        assert update["collected_slots"] == {}
