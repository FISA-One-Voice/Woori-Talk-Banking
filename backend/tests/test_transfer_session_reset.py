"""이체 완료 후 홈에서 새 송금 시작 시 세션 초기화 테스트."""

from app.shared.agent.transfer_intent import is_plain_transfer_start


class TestTransferRestartDetection:
    def test_plain_transfer_includes하고싶어(self):
        assert is_plain_transfer_start("송금하고 싶어")
