"""이체 에이전트 tool 래퍼 단위 테스트.

검증 범위:
    - execute_transfer tool : 수취인 조회 결과별 분기, 서비스 예외, 잘못된 UUID, db.close 보장
    - add_note tool         : 지정 tx_id로 update_memo, tx_id 없음, 서비스 예외, db.close 보장

실행:
    cd backend
    pytest tests/test_transfer_tools.py -v

주의:
    - DB를 직접 사용하지 않습니다. 모든 외부 의존성을 mock으로 대체합니다.
    - 서비스 로직 자체는 test_transfer_service.py에서 별도 검증합니다.
    - 이 파일이 검증하는 것: 툴 래퍼의 TTS 문자열 반환 / 예외 흡수 / db.close 보장
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.shared.agent.tools.transfer import add_note, execute_transfer

# ── 공통 상수 ──────────────────────────────────────────────────────────────────
_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_TX_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"


# ── 공통 픽스처 ────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_db() -> MagicMock:
    """테스트별로 독립된 mock DB 세션을 반환합니다."""
    return MagicMock()


def _patch_get_db(mock_db: MagicMock):
    """get_db()를 mock_db를 yield하는 제너레이터로 대체하는 patch를 반환합니다.

    transfer.py는 next(get_db())로 세션을 얻기 때문에 각 호출마다 신선한 iterator가
    필요합니다. return_value가 아닌 side_effect를 사용하는 이유가 바로 이 때문입니다.
    """
    return patch(
        "app.shared.agent.tools.transfer.get_db",
        side_effect=lambda: iter([mock_db]),
    )


# ── TestExecuteTransferTool ─────────────────────────────────────────────────────
class TestExecuteTransferTool:
    """execute_transfer tool 래퍼 동작 검증."""

    def test_success(self, mock_db: MagicMock):
        """[이체 성공] 수취인이 정상 조회되면 transfer_service.execute_transfer를 호출하고
        '{recipient}님께 {amount:,}원 이체가 완료되었습니다.' 메시지를 반환해야 한다."""
        mock_resolved = MagicMock()
        mock_resolved.account_number = "98765432101234"
        mock_resolved.bank_name = "국민은행"
        mock_resolved.recipient_name = "홍길순"
        mock_resolved.recipient_id = uuid.uuid4()

        with (
            _patch_get_db(mock_db),
            patch(
                "app.shared.agent.tools.transfer.lookup_recipient_by_voice",
                return_value=mock_resolved,
            ),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.execute_transfer.return_value = {"txId": _TX_ID}
            result = execute_transfer.invoke(
                {"user_id": _USER_ID, "recipient": "엄마", "amount": 10_000}
            )

        assert "엄마" in result
        assert "10,000" in result
        assert "완료" in result
        mock_svc.execute_transfer.assert_called_once()
        mock_db.close.assert_called_once()

    def test_recipient_not_found(self, mock_db: MagicMock):
        """[수취인 없음] lookup_recipient_by_voice가 None을 반환하면
        서비스를 호출하지 않고 '찾을 수 없습니다' 메시지를 반환해야 한다."""
        with (
            _patch_get_db(mock_db),
            patch(
                "app.shared.agent.tools.transfer.lookup_recipient_by_voice",
                return_value=None,
            ),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            result = execute_transfer.invoke(
                {"user_id": _USER_ID, "recipient": "모르는사람", "amount": 10_000}
            )

        assert "찾을 수 없습니다" in result
        mock_svc.execute_transfer.assert_not_called()
        mock_db.close.assert_called_once()

    def test_service_exception(self, mock_db: MagicMock):
        """[서비스 예외] transfer_service.execute_transfer가 예외를 발생시키면
        예외가 호출자에게 전파되지 않고 오류 안내 문자열을 반환해야 한다."""
        mock_resolved = MagicMock()
        mock_resolved.account_number = "98765432101234"
        mock_resolved.bank_name = "국민은행"
        mock_resolved.recipient_name = "홍길순"
        mock_resolved.recipient_id = uuid.uuid4()

        with (
            _patch_get_db(mock_db),
            patch(
                "app.shared.agent.tools.transfer.lookup_recipient_by_voice",
                return_value=mock_resolved,
            ),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.execute_transfer.side_effect = RuntimeError("DB 연결 실패")
            result = execute_transfer.invoke(
                {"user_id": _USER_ID, "recipient": "엄마", "amount": 10_000}
            )

        assert "오류" in result
        mock_db.close.assert_called_once()

    def test_invalid_user_id(self, mock_db: MagicMock):
        """[잘못된 user_id] uuid.UUID() 변환에 실패하는 문자열을 전달하면
        ValueError가 tool 외부로 전파되지 않고 오류 문자열을 반환해야 한다."""
        with (
            _patch_get_db(mock_db),
            patch(
                "app.shared.agent.tools.transfer.lookup_recipient_by_voice"
            ) as mock_lookup,
        ):
            result = execute_transfer.invoke(
                {"user_id": "not-a-uuid", "recipient": "엄마", "amount": 10_000}
            )

        assert "오류" in result
        mock_lookup.assert_not_called()
        mock_db.close.assert_called_once()


# ── TestAddNoteTool ─────────────────────────────────────────────────────────────
class TestAddNoteTool:
    """add_note tool 래퍼 동작 검증 (지정 tx_id, router와 동일 service)."""

    def test_success(self, mock_db: MagicMock):
        """[메모 추가 성공] update_memo를 올바른 tx_id로 호출한다."""
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            result = add_note.invoke(
                {"user_id": _USER_ID, "memo": "용돈", "tx_id": _TX_ID}
            )

        assert "용돈" in result
        assert "추가" in result
        mock_svc.update_memo.assert_called_once_with(
            db=mock_db,
            user_id=_USER_ID,
            tx_id=_TX_ID,
            memo="용돈",
        )
        mock_db.close.assert_called_once()

    def test_missing_tx_id(self):
        """[tx_id 없음] DB·update_memo 없이 안내 메시지를 반환해야 한다."""
        with patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc:
            result = add_note.invoke({"user_id": _USER_ID, "memo": "메모", "tx_id": ""})

        assert "이체" in result
        mock_svc.update_memo.assert_not_called()

    def test_service_exception(self, mock_db: MagicMock):
        """[서비스 예외] update_memo 예외 시 오류 문자열을 반환하고 db.close를 보장한다."""
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.update_memo.side_effect = RuntimeError("메모 저장 실패")
            result = add_note.invoke(
                {"user_id": _USER_ID, "memo": "용돈", "tx_id": _TX_ID}
            )

        assert "오류" in result
        mock_db.close.assert_called_once()
