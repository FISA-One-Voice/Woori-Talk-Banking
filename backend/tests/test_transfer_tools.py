"""이체 에이전트 tool 단위 테스트.

검증 범위:
    - execute_transfer tool : JSON 반환, 수취인 조회 결과별 분기, 서비스 예외
    - add_note tool         : tx_id 기반 메모 저장, 서비스 예외, db.close 보장

실행:
    cd backend
    pytest tests/test_transfer_tools.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.exception import AppError
from app.shared.agent.slot_schema import FAILED_SCREEN_MAP
from app.shared.agent.tools.transfer import (
    add_note,
    execute_transfer,
)

_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_TX_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


def _patch_get_db(mock_db: MagicMock):
    return patch(
        "app.shared.agent.tools.transfer.get_db",
        side_effect=lambda: iter([mock_db]),
    )


def _invoke(mock_db: MagicMock, **kwargs) -> dict:
    result_raw = execute_transfer.invoke(kwargs)
    return json.loads(result_raw)


class TestExecuteTransferTool:
    def test_success(self, mock_db: MagicMock):
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.execute_transfer.return_value = {"txId": _TX_ID}
            data = _invoke(
                mock_db,
                user_id=_USER_ID,
                recipient="엄마",
                amount=10_000,
                account_number="98765432101234",
                bank_name="국민은행",
            )

        assert "엄마" in data["tts_text"]
        assert "10,000" in data["tts_text"]
        assert "완료" in data["tts_text"]
        assert data["success"] is True
        mock_svc.execute_transfer.assert_called_once()
        mock_db.close.assert_called_once()

    def test_returns_tx_id(self, mock_db: MagicMock):
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.execute_transfer.return_value = {"txId": _TX_ID}
            data = _invoke(
                mock_db,
                user_id=_USER_ID,
                recipient="엄마",
                amount=10_000,
                account_number="98765432101234",
                bank_name="국민은행",
            )

        assert data["tx_id"] == _TX_ID
        assert data["success"] is True
        assert "완료" in data["tts_text"]

    def test_from_slots_recipient_id(self, mock_db: MagicMock):
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.execute_transfer.return_value = {"txId": _TX_ID}
            data = _invoke(
                mock_db,
                user_id=_USER_ID,
                recipient="엄마",
                amount=10_000,
                recipient_id="rec-1",
                bank_name="국민은행",
                account_number="98765432101234",
            )

        assert data["tx_id"] == _TX_ID
        mock_svc.execute_transfer.assert_called_once()

    def test_missing_slots_returns_error(self, mock_db: MagicMock):
        """account_number도 recipient_id도 없으면 에러 반환 (resolve_node 우회 방어)."""
        with _patch_get_db(mock_db):
            data = _invoke(
                mock_db,
                user_id=_USER_ID,
                recipient="미등록수취인",
                amount=10_000,
            )

        assert data["tx_id"] is None
        assert data["success"] is False
        assert "찾을 수 없습니다" in data["tts_text"]
        mock_db.close.assert_called_once()

    def test_app_error_returns_no_tx_id(self, mock_db: MagicMock):
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            mock_svc.execute_transfer.side_effect = AppError(
                code="INSUFFICIENT_BALANCE",
                message="잔액이 부족합니다.",
                status_code=400,
                user_message="잔액이 부족합니다.",
            )
            data = _invoke(
                mock_db,
                user_id=_USER_ID,
                recipient="엄마",
                amount=10_000,
                account_number="98765432101234",
                bank_name="국민은행",
            )

        assert data["tx_id"] is None
        assert data["success"] is False
        assert "잔액" in data["tts_text"]


class TestTransferFailedScreenMap:
    def test_failed_screen_map_transfer(self) -> None:
        assert FAILED_SCREEN_MAP["transfer"] == "transfer/failed"


class TestAddNoteTool:
    def test_success_with_tx_id(self, mock_db: MagicMock):
        with (
            _patch_get_db(mock_db),
            patch("app.shared.agent.tools.transfer.transfer_service") as mock_svc,
        ):
            result = add_note.invoke(
                {"user_id": _USER_ID, "memo": "용돈", "tx_id": _TX_ID}
            )

        assert "용돈" in result
        mock_svc.update_memo.assert_called_once_with(
            db=mock_db,
            user_id=_USER_ID,
            tx_id=_TX_ID,
            memo="용돈",
        )
        mock_db.close.assert_called_once()

    def test_service_exception(self, mock_db: MagicMock):
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
