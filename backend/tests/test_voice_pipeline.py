"""음성 파이프라인 서비스 테스트 (Issue #7).

테스트 범위:
    Layer A — 유닛 테스트 (외부 의존성 모두 mock):
        - process_voice_pipeline 정상 흐름 분기 (STT→Agent→TTS)
        - process_voice_pipeline ASV 흐름 분기 (awaiting_asv_audio=True)
        - ASV 성공 → execution_ready 설정 → execute_node 진행
        - ASV 실패 1~2회 → retry_count 증가, awaiting_asv_audio=True 유지
        - ASV 실패 3회 → 취소 메시지, awaiting_asv_audio=False, 상태 초기화
        - 음성 미등록 사용자 → ASVError(ASV_NOT_ENROLLED) 발생
        - STTError 전파 확인

    Layer B — 스키마 구조 검증 (의존성 없음):
        - VoiceResponseData 기본값 확인
        - ASVResult / AntiSpoofResult 필드 확인

실행 방법:
    cd backend
    .venv/bin/pytest tests/test_voice_pipeline.py -v
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exception import ASVError, STTError
from app.shared.voice.schema import AntiSpoofResult, ASVResult, VoiceResponseData
from app.shared.voice.service import (
    _call_anti_spoofing_ec2,
    _call_asv_ec2,
    _get_user_embedding,
    _handle_asv_flow,
    _handle_normal_flow,
    _resolve_navigate_to,
    process_voice_pipeline,
    reset_voice_state,
)


# ── 테스트 픽스처 ────────────────────────────────────────────────────────────────

FAKE_USER_ID = str(uuid.uuid4())
FAKE_AUDIO = b"FAKE_AUDIO_BYTES"
FAKE_TRANSCRIPT = "엄마에게 오만 원 이체해줘"
FAKE_AGENT_RESPONSE = "엄마에게 오만 원 이체가 완료되었습니다."
FAKE_AUDIO_B64 = "FAKE_BASE64_MP3"
FAKE_EMBEDDING = [0.1] * 192  # 192차원 더미 임베딩


def _make_agent_result(
    response_text: str = FAKE_AGENT_RESPONSE,
    navigate_to: str | None = None,
    collected_slots: dict | None = None,
    awaiting_confirmation: bool = False,
    awaiting_asv_audio: bool = False,
    pending_action: str | None = None,
):
    """graph.ainvoke() 반환값 모의 객체 생성 헬퍼."""
    from langchain_core.messages import AIMessage

    return {
        "messages": [AIMessage(content=response_text)],
        "navigate_to": navigate_to,
        "collected_slots": collected_slots or {},
        "awaiting_confirmation": awaiting_confirmation,
        "awaiting_asv_audio": awaiting_asv_audio,
        "pending_action": pending_action,
    }


def _make_mock_graph(
    state_values: dict | None = None,
    invoke_result: dict | None = None,
):
    """LangGraph 그래프 모의 객체 생성 헬퍼."""
    graph = MagicMock()

    # get_state() 반환값 설정
    state_snapshot = MagicMock()
    state_snapshot.values = state_values if state_values is not None else {}
    graph.get_state.return_value = state_snapshot

    # ainvoke() 반환값 설정
    graph.ainvoke = AsyncMock(return_value=invoke_result or _make_agent_result())

    # aupdate_state() 반환값 설정
    graph.aupdate_state = AsyncMock(return_value=None)

    return graph


# ── Layer B: 스키마 구조 검증 ────────────────────────────────────────────────────


class TestSchemas:
    """VoiceResponseData, ASVResult, AntiSpoofResult 스키마 기본 검증."""

    def test_voice_response_data_defaults(self) -> None:
        """TC-S01: VoiceResponseData 기본값 확인."""
        data = VoiceResponseData()
        # 모든 필드가 안전한 기본값을 가져야 프론트엔드에서 undefined를 받지 않음
        assert data.audio == ""
        assert data.navigate_to is None
        assert data.collected_slots == {}
        assert data.awaiting_confirmation is False
        assert data.awaiting_asv_audio is False

    def test_asv_result_fields(self) -> None:
        """TC-S02: ASVResult 필드 타입 확인."""
        result = ASVResult(verified=True, score=0.72)
        assert result.verified is True
        # approx: float 비교 시 부동소수점 오차를 허용
        assert result.score == pytest.approx(0.72)

    def test_anti_spoof_result_fields(self) -> None:
        """TC-S03: AntiSpoofResult 필드 타입 확인."""
        result = AntiSpoofResult(is_real=False, confidence=0.3)
        # is_real=False: 스푸핑 감지 시나리오 — False 값도 정상 저장되는지 확인
        assert result.is_real is False
        assert result.confidence == pytest.approx(0.3)


# ── Layer A: 정상 흐름 테스트 ────────────────────────────────────────────────────


class TestNormalFlow:
    """awaiting_asv_audio=False일 때 STT → Agent → TTS 흐름 검증."""

    @pytest.mark.asyncio
    async def test_normal_flow_returns_voice_response(self) -> None:
        """TC-N01: 정상 흐름 — VoiceResponseData 반환, audio 필드에 base64 값 존재."""
        # awaiting_asv_audio=False → ASV 흐름이 아닌 일반 STT→Agent→TTS 경로 진입
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": False},
            invoke_result=_make_agent_result(FAKE_AGENT_RESPONSE),
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch(
                "app.shared.voice.service.transcribe_audio",
                new=AsyncMock(return_value=FAKE_TRANSCRIPT),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"FAKE_MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=MagicMock()
            )

        assert isinstance(result, VoiceResponseData)
        # audio가 비어 있지 않으면 TTS가 실행되어 base64 인코딩된 MP3가 담긴 것
        assert result.audio != ""
        assert result.awaiting_asv_audio is False

    @pytest.mark.asyncio
    async def test_normal_flow_calls_stt_then_agent_then_tts(self) -> None:
        """TC-N02: 정상 흐름 호출 순서 — STT → ainvoke → TTS."""
        mock_graph = _make_mock_graph(state_values={"awaiting_asv_audio": False})
        mock_stt = AsyncMock(return_value=FAKE_TRANSCRIPT)
        mock_tts = AsyncMock(return_value=b"MP3")

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch("app.shared.voice.service.transcribe_audio", new=mock_stt),
            patch("app.shared.voice.service.synthesize_speech", new=mock_tts),
        ):
            await process_voice_pipeline(FAKE_AUDIO, FAKE_USER_ID, db=MagicMock())

        # STT에 원본 오디오가 그대로 전달되는지, 각 단계가 정확히 한 번씩 호출되는지 검증
        mock_stt.assert_called_once_with(FAKE_AUDIO, "audio/wav")
        mock_graph.ainvoke.assert_called_once()
        mock_tts.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_flow_propagates_stt_error(self) -> None:
        """TC-N03: STTError 발생 시 서비스 레벨까지 전파."""
        mock_graph = _make_mock_graph(state_values={"awaiting_asv_audio": False})

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch(
                "app.shared.voice.service.transcribe_audio",
                new=AsyncMock(
                    side_effect=STTError(
                        code="VOICE_STT_FAILED",
                        message="STT 변환에 실패했습니다.",
                    )
                ),
            ),
        ):
            with pytest.raises(STTError, match="STT"):
                await process_voice_pipeline(FAKE_AUDIO, FAKE_USER_ID, db=MagicMock())

    @pytest.mark.asyncio
    async def test_normal_flow_navigate_to_forwarded(self) -> None:
        """TC-N04: 에이전트가 navigate_to를 반환하면 VoiceResponseData에 그대로 전달."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": False},
            invoke_result=_make_agent_result(navigate_to="balance"),
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch(
                "app.shared.voice.service.transcribe_audio",
                new=AsyncMock(return_value=FAKE_TRANSCRIPT),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=MagicMock()
            )

        assert result.navigate_to == "balance"

    @pytest.mark.asyncio
    async def test_confirm_flow_keeps_navigate_to_transfer(self) -> None:
        """awaiting_confirmation=True여도 navigate_to=transfer가 유지되어야 한다."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": False},
            invoke_result=_make_agent_result(
                response_text="안유민님 3천원 이체할까요?",
                navigate_to="transfer",
                collected_slots={"recipient": "안유민", "amount": "3000"},
                awaiting_confirmation=True,
                pending_action="transfer",
            ),
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch(
                "app.shared.voice.service.transcribe_audio",
                new=AsyncMock(return_value=FAKE_TRANSCRIPT),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=MagicMock()
            )

        assert result.navigate_to == "transfer"
        assert result.awaiting_confirmation is True

    @pytest.mark.asyncio
    async def test_asv_awaiting_resolves_navigate_to_transfer(self) -> None:
        """awaiting_asv + pending transfer → navigate_to fallback transfer."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": False},
            invoke_result=_make_agent_result(
                response_text="목소리로 인증해 주세요.",
                navigate_to=None,
                awaiting_asv_audio=True,
                pending_action="transfer",
                collected_slots={"recipient": "안유민", "amount": "3000"},
            ),
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch(
                "app.shared.voice.service.transcribe_audio",
                new=AsyncMock(return_value=FAKE_TRANSCRIPT),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=MagicMock()
            )

        assert result.navigate_to == "transfer"
        assert result.awaiting_asv_audio is True


class TestResolveNavigateTo:
    def test_slot_fill_pending_transfer_no_fallback(self) -> None:
        """슬롯만 보충된 턴(pending만 있음)은 navigate_to fallback 없음."""
        assert _resolve_navigate_to({"pending_action": "transfer"}) is None

    def test_awaiting_asv_fallback_transfer(self) -> None:
        assert (
            _resolve_navigate_to(
                {
                    "pending_action": "transfer",
                    "awaiting_asv_audio": True,
                }
            )
            == "transfer"
        )

    def test_awaiting_confirmation_fallback_transfer(self) -> None:
        assert (
            _resolve_navigate_to(
                {
                    "pending_action": "transfer",
                    "awaiting_confirmation": True,
                }
            )
            == "transfer"
        )

    def test_explicit_home(self) -> None:
        assert _resolve_navigate_to({"navigate_to": "home"}) == "home"

    def test_explicit_complete(self) -> None:
        assert _resolve_navigate_to({"navigate_to": "transfer/complete"}) == (
            "transfer/complete"
        )

    def test_explicit_failed(self) -> None:
        assert _resolve_navigate_to({"navigate_to": "transfer/failed"}) == (
            "transfer/failed"
        )


# ── Layer A: ASV 흐름 테스트 ─────────────────────────────────────────────────────


class TestAsvFlow:
    """awaiting_asv_audio=True일 때 ASV 인증 흐름 검증."""

    _ASV_TRANSCRIPT = "목소리 인증"

    def _asv_stt_patch(self):
        return patch(
            "app.shared.voice.service.transcribe_audio",
            new=AsyncMock(return_value=self._ASV_TRANSCRIPT),
        )

    def _asv_wav_patch(self):
        return patch(
            "app.shared.voice.service._to_wav_bytes",
            return_value=b"FAKE_WAV_BYTES",
        )

    def _make_db_with_user(self, embedding: list[float] = None) -> MagicMock:
        """embedding_vector를 가진 사용자가 있는 DB 모의 객체."""
        mock_user = MagicMock()
        mock_user.embedding_vector = embedding or FAKE_EMBEDDING
        mock_db = MagicMock()
        mock_db.get.return_value = mock_user
        return mock_db

    @pytest.mark.asyncio
    async def test_asv_success_calls_execute_node(self) -> None:
        """TC-A01: ASV 인증 성공 시 aupdate_state(execution_ready=True) 호출 후 ainvoke."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 0},
            invoke_result=_make_agent_result("엄마에게 오만 원 이체가 완료되었습니다."),
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            self._asv_stt_patch(),
            self._asv_wav_patch(),
            patch(
                "app.shared.voice.service._call_asv_ec2",
                new=AsyncMock(return_value=ASVResult(verified=True, score=0.85)),
            ),
            patch(
                "app.shared.voice.service._call_anti_spoofing_ec2",
                new=AsyncMock(
                    return_value=AntiSpoofResult(is_real=True, confidence=0.99)
                ),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=self._make_db_with_user()
            )

        # aupdate_state가 execution_ready=True로 호출되었는지 확인
        call_args = mock_graph.aupdate_state.call_args[0][1]
        assert call_args.get("execution_ready") is True
        assert call_args.get("awaiting_asv_audio") is False

        assert result.awaiting_asv_audio is False
        assert result.audio != ""

    @pytest.mark.asyncio
    async def test_asv_fail_first_attempt_retry_count_incremented(self) -> None:
        """TC-A02: ASV 실패 1회 — retry_count 1 증가, awaiting_asv_audio=True 유지."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 0},
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            self._asv_stt_patch(),
            self._asv_wav_patch(),
            patch(
                "app.shared.voice.service._call_asv_ec2",
                new=AsyncMock(return_value=ASVResult(verified=False, score=0.3)),
            ),
            patch(
                "app.shared.voice.service._call_anti_spoofing_ec2",
                new=AsyncMock(
                    return_value=AntiSpoofResult(is_real=True, confidence=0.99)
                ),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=self._make_db_with_user()
            )

        # aupdate_state에 asv_retry_count=1 전달 확인
        call_args = mock_graph.aupdate_state.call_args[0][1]
        assert call_args.get("asv_retry_count") == 1

        assert result.awaiting_asv_audio is True

    @pytest.mark.asyncio
    async def test_asv_fail_second_attempt_one_remaining(self) -> None:
        """TC-A03: ASV 실패 2회 — retry_count=2, 남은 기회 1번 안내."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 1},
        )
        mock_tts = AsyncMock(return_value=b"MP3")

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            self._asv_stt_patch(),
            self._asv_wav_patch(),
            patch(
                "app.shared.voice.service._call_asv_ec2",
                new=AsyncMock(return_value=ASVResult(verified=False, score=0.2)),
            ),
            patch(
                "app.shared.voice.service._call_anti_spoofing_ec2",
                new=AsyncMock(
                    return_value=AntiSpoofResult(is_real=True, confidence=0.99)
                ),
            ),
            patch("app.shared.voice.service.synthesize_speech", new=mock_tts),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=self._make_db_with_user()
            )

        # TTS 안내 메시지에 "1번"이 포함되어야 함
        tts_call_text: str = mock_tts.call_args[0][0]
        assert "1번" in tts_call_text

        assert result.awaiting_asv_audio is True

    @pytest.mark.asyncio
    async def test_asv_fail_third_attempt_action_cancelled(self) -> None:
        """TC-A04: ASV 실패 3회 — 취소 메시지, awaiting_asv_audio=False, 상태 초기화."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 2},
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            self._asv_stt_patch(),
            self._asv_wav_patch(),
            patch(
                "app.shared.voice.service._call_asv_ec2",
                new=AsyncMock(return_value=ASVResult(verified=False, score=0.1)),
            ),
            patch(
                "app.shared.voice.service._call_anti_spoofing_ec2",
                new=AsyncMock(
                    return_value=AntiSpoofResult(is_real=True, confidence=0.99)
                ),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"CANCEL_MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=self._make_db_with_user()
            )

        # 상태 초기화 확인
        reset_args = mock_graph.aupdate_state.call_args[0][1]
        assert reset_args.get("pending_action") is None
        assert reset_args.get("collected_slots") == {}
        assert reset_args.get("asv_retry_count") == 0
        assert reset_args.get("awaiting_asv_audio") is False

        assert result.awaiting_asv_audio is False
        assert result.awaiting_confirmation is False
        assert result.navigate_to == "home"

    @pytest.mark.asyncio
    async def test_asv_home_keyword_skips_verify(self) -> None:
        """ASV 대기 중 '홈' 발화 → verify 생략, home navigate."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 0},
        )

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            patch(
                "app.shared.voice.service.transcribe_audio",
                new=AsyncMock(return_value="홈으로"),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            result = await process_voice_pipeline(
                FAKE_AUDIO, FAKE_USER_ID, db=self._make_db_with_user()
            )

        assert result.navigate_to == "home"
        mock_graph.aupdate_state.assert_called()

    @pytest.mark.asyncio
    async def test_asv_not_enrolled_raises_error(self) -> None:
        """TC-A05: 음성 미등록 사용자 — ASVError(ASV_NOT_ENROLLED) 발생."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 0},
        )
        # embedding_vector가 없는 사용자
        mock_user = MagicMock()
        mock_user.embedding_vector = None
        mock_db = MagicMock()
        mock_db.get.return_value = mock_user

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            self._asv_stt_patch(),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MP3"),
            ),
        ):
            with pytest.raises(ASVError) as exc_info:
                await process_voice_pipeline(FAKE_AUDIO, FAKE_USER_ID, db=mock_db)

        assert exc_info.value.code == "ASV_NOT_ENROLLED"

    @pytest.mark.asyncio
    async def test_asv_user_not_found_raises_error(self) -> None:
        """TC-A06: DB에 사용자 없음 — ASVError(ASV_NOT_ENROLLED) 발생."""
        mock_graph = _make_mock_graph(
            state_values={"awaiting_asv_audio": True, "asv_retry_count": 0},
        )
        mock_db = MagicMock()
        mock_db.get.return_value = None  # 사용자 없음

        with (
            patch("app.shared.voice.service._get_graph", return_value=mock_graph),
            self._asv_stt_patch(),
        ):
            with pytest.raises(ASVError) as exc_info:
                await process_voice_pipeline(FAKE_AUDIO, FAKE_USER_ID, db=mock_db)

        assert exc_info.value.code == "ASV_NOT_ENROLLED"


# ── Layer A: DB 임베딩 조회 유닛 테스트 ──────────────────────────────────────────


class TestGetUserEmbedding:
    """_get_user_embedding() 독립 유닛 테스트."""

    def test_returns_embedding_as_list(self) -> None:
        """TC-D01: 유효한 사용자 — 192차원 float 리스트 반환."""
        mock_user = MagicMock()
        mock_user.embedding_vector = FAKE_EMBEDDING
        mock_db = MagicMock()
        mock_db.get.return_value = mock_user

        result = _get_user_embedding(FAKE_USER_ID, mock_db)
        assert isinstance(result, list)
        assert len(result) == 192

    def test_raises_if_no_embedding(self) -> None:
        """TC-D02: embedding_vector=None — ASVError(ASV_NOT_ENROLLED)."""
        mock_user = MagicMock()
        mock_user.embedding_vector = None
        mock_db = MagicMock()
        mock_db.get.return_value = mock_user

        with pytest.raises(ASVError) as exc_info:
            _get_user_embedding(FAKE_USER_ID, mock_db)

        assert exc_info.value.code == "ASV_NOT_ENROLLED"
        assert exc_info.value.status_code == 422

    def test_raises_if_invalid_uuid(self) -> None:
        """TC-D03: 잘못된 UUID 문자열 — ASVError(ASV_NOT_ENROLLED)."""
        with pytest.raises(ASVError) as exc_info:
            _get_user_embedding("not-a-uuid", MagicMock())

        assert exc_info.value.code == "ASV_NOT_ENROLLED"
        assert exc_info.value.status_code == 400


# ── Layer A: anti-spoofing 바이패스 테스트 ────────────────────────────────────────


class TestAntiSpoofBypass:
    """USE_ANTI_SPOOFING=False 시 바이패스 동작 확인."""

    @pytest.mark.asyncio
    async def test_bypass_returns_real_true(self) -> None:
        """TC-SP01: USE_ANTI_SPOOFING=False → is_real=True, confidence=1.0 반환."""
        with patch("app.shared.voice.service.settings") as mock_settings:
            mock_settings.USE_ANTI_SPOOFING = False
            result = await _call_anti_spoofing_ec2(FAKE_AUDIO)

        assert result.is_real is True
        assert result.confidence == pytest.approx(1.0)
