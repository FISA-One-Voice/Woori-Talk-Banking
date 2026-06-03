"""이체 완료 후 홈에서 새 송금 시작 시 세션 초기화 테스트."""

from app.shared.agent.graph import (
    _is_transfer_restart_utterance,
    _should_restart_transfer_flow,
)
from app.shared.agent.transfer_intent import is_plain_transfer_start


class TestTransferRestartDetection:
    def test_restart_keywords(self):
        assert _is_transfer_restart_utterance("송금")
        assert _is_transfer_restart_utterance("이체 하기")
        assert not _is_transfer_restart_utterance("안유민")

    def test_restart_when_pending_transfer_on_home(self):
        state = {"awaiting_confirmation": False, "awaiting_asv_audio": False}
        assert _should_restart_transfer_flow("transfer", "transfer", "송금", state)

    def test_no_restart_during_confirm(self):
        state = {"awaiting_confirmation": True, "awaiting_asv_audio": False}
        assert not _should_restart_transfer_flow(
            "transfer", "transfer", "송금", state
        )

    def test_plain_transfer_includes하고싶어(self):
        assert is_plain_transfer_start("송금하고 싶어")
