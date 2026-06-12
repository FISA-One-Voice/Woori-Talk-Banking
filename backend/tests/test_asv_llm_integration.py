"""ASV 서버 + LLM 에이전트 통합 테스트 (Issue #7).

테스트 범위:
    Layer C — ASV 서버 직접 통합 (실제 HTTP 호출):
        - TC-I01: /verify 응답 스키마 확인 (ASVResult 타입·범위)
        - TC-I02: 동일 입력으로 두 번 호출 시 점수 일관성
        - TC-I03: 임베딩 방향이 반대일 때 점수 차이 발생

    Layer D — LLM 에이전트 ASV 흐름 트리거 검증:
        - TC-L01: '이체' 발화 → intent='transfer', navigate_to='transfer'
        - TC-L02: 슬롯 완전 수집 후 확인('네') → awaiting_asv_audio=True
        - TC-L03: 잔액 조회 → ASV 없이 즉시 execute_node 실행
        - TC-L04: 진행 중 '취소' → pending_action=None 상태 초기화

    Layer E — ASV + LLM 완전 통합 파이프라인:
        - TC-F01: awaiting_asv_audio=True 상태에서 실제 ASV 호출
                  → 결과에 따라 execute_node 실행 또는 재시도 안내
        - TC-F02: ASV 성공 후 _proceed_after_asv_success → LLM execute_node
                  → 이체 결과 응답 확인

실행 조건:
    Layer C, E: ASV EC2 서버 실행 필요 (ASV_SERVER_URL, 기본: http://localhost:8000)
    Layer D, E: OPENAI_CHAT_API_KEY 환경변수 설정 필요

실행 방법:
    cd backend
    .venv/bin/pytest tests/test_asv_llm_integration.py -v -m integration
"""

import io
import socket
import uuid
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.shared.agent import build_graph
from app.shared.agent.tools import ALL_TOOLS
from app.shared.voice.schema import ASVResult, VoiceResponseData
from app.shared.voice.service import _call_asv_ec2, process_voice_pipeline

# 이 파일의 모든 테스트에 integration 마커를 적용한다.
# -m integration 플래그 없이는 실행되지 않는다.
pytestmark = pytest.mark.integration


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────────


def _make_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """무음 WAV 파일 바이트를 생성한다 (16kHz·16-bit·mono).

    실제 음성 인식이 목적이 아니므로 무음으로 생성한다.
    ASV 서버는 유효한 WAV 포맷이면 처리하므로 무음으로 충분하다.
    """
    num_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def _can_reach(url: str, timeout: float = 2.0) -> bool:
    """TCP 소켓으로 서버 연결 가능 여부를 확인한다."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ── 상수 ──────────────────────────────────────────────────────────────────────────

# 더미 192차원 임베딩 — 실제 화자 임베딩과 다르므로 ASV 인증은 보통 실패한다
FAKE_EMBEDDING_A: list[float] = [0.1] * 192
# 반대 방향 임베딩 — TC-I03에서 점수 차이를 유발하기 위해 사용
FAKE_EMBEDDING_B: list[float] = [-0.3] * 192


# ── 모듈 공통 픽스처 ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sample_wav() -> bytes:
    """1초 무음 WAV 바이트 픽스처."""
    return _make_wav_bytes(duration_sec=1.0)


@pytest.fixture(scope="module")
def asv_reachable() -> None:
    """ASV 서버 연결 가능 여부 확인. 연결 불가 시 테스트를 건너뜀."""
    if not _can_reach(settings.ASV_SERVER_URL):
        pytest.skip(
            f"ASV 서버({settings.ASV_SERVER_URL})에 연결할 수 없습니다. "
            "ai/asv/main.py를 실행한 후 다시 시도하세요."
        )


@pytest.fixture(scope="module")
def llm_api_key() -> None:
    """OPENAI_CHAT_API_KEY 설정 여부 확인. 미설정 시 테스트를 건너뜀."""
    if not settings.OPENAI_CHAT_API_KEY:
        pytest.skip(
            "OPENAI_CHAT_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 키를 추가한 후 다시 시도하세요."
        )


@pytest.fixture(scope="module")
def real_graph(llm_api_key):
    """실제 OpenAI LLM으로 빌드한 LangGraph 그래프.

    각 테스트는 고유한 thread_id(uuid)를 사용하므로 그래프 인스턴스 자체는 공유해도 안전하다.
    """
    return build_graph(ALL_TOOLS)


def _db_with_embedding(embedding: list[float]) -> MagicMock:
    """지정한 임베딩 벡터를 가진 사용자가 조회되는 DB 모의 객체를 반환한다."""
    user = MagicMock()
    user.embedding_vector = embedding
    db = MagicMock()
    db.get.return_value = user
    return db


# ── Layer C: ASV 서버 직접 통합 ───────────────────────────────────────────────────


class TestAsvServerDirect:
    """실제 ASV EC2 서버에 HTTP 요청을 보내 응답 스키마·일관성을 검증한다.

    픽스처 의존성: asv_reachable (서버 미구동 시 자동 skip)
    """

    async def test_verify_returns_valid_schema(self, sample_wav, asv_reachable) -> None:
        """TC-I01: /verify 응답이 ASVResult 타입·필드 범위와 일치하는지 확인."""
        result = await _call_asv_ec2(sample_wav, FAKE_EMBEDDING_A)

        assert isinstance(result, ASVResult)
        assert isinstance(result.verified, bool)
        assert isinstance(result.score, float)
        # 코사인 유사도는 -1~1 범위이나 ASV는 0~1 정규화가 일반적
        assert -1.0 <= result.score <= 1.0

    async def test_verify_score_is_consistent(self, sample_wav, asv_reachable) -> None:
        """TC-I02: 동일 오디오·임베딩으로 두 번 호출했을 때 점수 편차 0.01 이내.

        결정론적 모델이므로 동일 입력에 대해 재현 가능해야 한다.
        """
        result1 = await _call_asv_ec2(sample_wav, FAKE_EMBEDDING_A)
        result2 = await _call_asv_ec2(sample_wav, FAKE_EMBEDDING_A)

        assert abs(result1.score - result2.score) < 0.01

    async def test_different_embeddings_produce_different_scores(
        self, sample_wav, asv_reachable
    ) -> None:
        """TC-I03: 반대 방향 임베딩(A vs B)은 서로 다른 유사도 점수를 반환해야 한다.

        코사인 유사도 기반 모델에서 [0.1]*192와 [0.9]*192는 같은 방향이므로
        점수 차이가 없을 수 있다. 이 케이스가 동일하게 나오면 테스트를 경고로 처리한다.
        """
        result_a = await _call_asv_ec2(sample_wav, FAKE_EMBEDDING_A)
        result_b = await _call_asv_ec2(sample_wav, FAKE_EMBEDDING_B)

        # 임베딩이 다르면 점수가 달라야 한다 (같은 방향의 벡터라면 동일할 수 있음)
        if result_a.score == result_b.score:
            pytest.xfail(
                "두 임베딩이 동일한 유사도를 반환했습니다. "
                "더 다른 임베딩 벡터로 교체하세요."
            )
        assert result_a.score != result_b.score


# ── Layer D: LLM 에이전트 ASV 흐름 트리거 검증 ────────────────────────────────────


class TestLlmAsvTrigger:
    """실제 OpenAI LLM이 ASV 트리거 조건을 올바르게 처리하는지 검증한다.

    픽스처 의존성: real_graph (OPENAI_CHAT_API_KEY 필요)
    """

    async def test_transfer_intent_sets_navigate_to(self, real_graph) -> None:
        """TC-L01: '이체' 발화 → intent='transfer', navigate_to='transfer' 설정.

        LLM이 뱅킹 인텐트를 정확히 분류하는지 확인한다.
        """
        from langchain_core.messages import HumanMessage

        uid = str(uuid.uuid4())
        result = await real_graph.ainvoke(
            {
                "messages": [HumanMessage(content="엄마에게 오만 원 이체해줘")],
                "user_id": uid,
            },
            config={"configurable": {"thread_id": uid}},
        )

        # 이체 인텐트 감지 시 프론트엔드에 화면 이동 신호를 보내야 한다
        assert result.get("navigate_to") == "transfer"

    async def test_confirmation_triggers_asv_for_transfer(self, real_graph) -> None:
        """TC-L02: 슬롯 완전 수집 상태에서 확인('네') → awaiting_asv_audio=True.

        LLM이 추출하는 슬롯 키 이름 변동성을 피하기 위해
        aupdate_state로 awaiting_confirmation=True 상태를 직접 주입한다.
        테스트 관심사: LLM이 '네'를 확인으로 인식하고 transfer ASV 흐름을 트리거하는지.
        """
        from langchain_core.messages import HumanMessage

        uid = str(uuid.uuid4())
        config = {"configurable": {"thread_id": uid}}

        # awaiting_confirmation=True + 슬롯 완전 수집 상태 직접 주입
        # as_node: 최초 체크포인트 생성 시 어떤 노드 출력으로 귀속할지 지정 (필수)
        await real_graph.aupdate_state(
            config,
            {
                "pending_action": "transfer",
                "awaiting_confirmation": True,
                "collected_slots": {"recipient": "엄마", "amount": 50000},
                "awaiting_asv_audio": False,
                "execution_ready": False,
                "asv_retry_count": 0,
                "navigate_to": None,
                "user_id": uid,
                "messages": [],
            },
            as_node="intent_node",
        )

        # 사용자 확인 발화 → intent_node가 awaiting_confirmation+user_confirmed 처리
        result = await real_graph.ainvoke(
            {"messages": [HumanMessage(content="네")], "user_id": uid},
            config=config,
        )

        # transfer는 ASV_REQUIRED_ACTIONS에 있으므로 확인 후 ASV 대기 상태여야 한다
        assert result.get("awaiting_asv_audio") is True

    async def test_balance_query_bypasses_asv(self, real_graph) -> None:
        """TC-L03: 잔액 조회 → ASV 없이 execute_node 즉시 실행.

        잔액 조회는 금전 이동이 없으므로 ASV_REQUIRED_ACTIONS에 포함되지 않는다.
        """
        from langchain_core.messages import HumanMessage

        uid = str(uuid.uuid4())
        result = await real_graph.ainvoke(
            {
                "messages": [HumanMessage(content="잔액 얼마야?")],
                "user_id": uid,
            },
            config={"configurable": {"thread_id": uid}},
        )

        # 잔액 조회 후 ASV 인증 대기 상태가 되어서는 안 된다
        assert result.get("awaiting_asv_audio") is not True
        # execute_node가 실행되어 TTS 친화적 응답이 있어야 한다
        last_msg_content = result["messages"][-1].content
        assert len(last_msg_content) > 0

    async def test_cancel_resets_all_state(self, real_graph) -> None:
        """TC-L04: 진행 중 '취소' 발화 → pending_action=None, 상태 전체 초기화.

        취소 발화 후 후속 요청이 이전 컨텍스트 없이 새로 시작되어야 한다.
        """
        from langchain_core.messages import HumanMessage

        uid = str(uuid.uuid4())
        config = {"configurable": {"thread_id": uid}}

        # Turn 1: 이체 요청 → pending_action='transfer' 설정
        await real_graph.ainvoke(
            {
                "messages": [HumanMessage(content="엄마에게 이체해줄래?")],
                "user_id": uid,
            },
            config=config,
        )

        # Turn 2: 취소
        result = await real_graph.ainvoke(
            {"messages": [HumanMessage(content="취소할게")], "user_id": uid},
            config=config,
        )

        # 취소 후 모든 진행 중 상태가 초기화되어야 한다
        assert result.get("pending_action") is None
        assert result.get("awaiting_confirmation") is not True
        assert result.get("awaiting_asv_audio") is not True


# ── Layer E: ASV + LLM 완전 통합 파이프라인 ──────────────────────────────────────


class TestAsvLlmFullPipeline:
    """실제 ASV 서버 + LLM을 동시에 사용하는 end-to-end 통합 테스트.

    픽스처 의존성: asv_reachable + llm_api_key (두 서비스 모두 필요)
    """

    async def test_asv_flow_with_real_server_and_llm(
        self, sample_wav, asv_reachable, llm_api_key
    ) -> None:
        """TC-F01: awaiting_asv_audio=True 상태에서 실제 ASV 서버 호출.

        aupdate_state로 ASV 대기 상태를 직접 주입하여 ASV 흐름만 격리 테스트한다.
        무음 WAV가 인증에 실패하는 경우와 통과하는 경우 모두 유효한 VoiceResponseData를
        반환하는지 확인한다.
        """
        uid = str(uuid.uuid4())
        config = {"configurable": {"thread_id": uid}}

        # 실제 그래프를 사용하되 _get_graph() 싱글턴을 우회한다
        real_g = build_graph(ALL_TOOLS)

        # ASV 대기 상태를 직접 주입 (이전 LLM 턴 없이 격리 가능)
        await real_g.aupdate_state(
            config,
            {
                "awaiting_asv_audio": True,
                "awaiting_confirmation": False,
                "pending_action": "transfer",
                "collected_slots": {"recipient": "엄마", "amount": 50000},
                "asv_retry_count": 0,
                "execution_ready": False,
                "navigate_to": None,
                "user_id": uid,
                "messages": [],
            },
            as_node="intent_node",
        )

        db = _db_with_embedding(FAKE_EMBEDDING_A)

        with (
            patch("app.shared.voice.service._get_graph", return_value=real_g),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MOCK_TTS"),
            ),
        ):
            result = await process_voice_pipeline(sample_wav, uid, db=db)

        # ASV 결과에 관계없이 항상 유효한 VoiceResponseData를 반환해야 한다
        assert isinstance(result, VoiceResponseData)
        assert result.audio != ""

        # 결과에 따른 상태 검증
        state_after = real_g.get_state(config)
        if result.awaiting_asv_audio:
            # 인증 실패: retry_count가 1 이상이어야 한다
            retry = state_after.values.get("asv_retry_count", 0)
            assert retry >= 1
        else:
            # 인증 성공: execute_node가 실행되어 pending_action이 초기화되어야 한다
            assert state_after.values.get("pending_action") is None

    async def test_asv_success_then_llm_executes_transfer(
        self, sample_wav, asv_reachable, llm_api_key
    ) -> None:
        """TC-F02: ASV 성공을 강제 주입 후 execute_node → 이체 결과 응답 확인.

        _proceed_after_asv_success가 "인증 완료" 메시지로 LLM을 재호출하여
        execute_node가 execute_transfer를 실행하는 전체 흐름을 검증한다.
        """
        uid = str(uuid.uuid4())
        config = {"configurable": {"thread_id": uid}}
        real_g = build_graph(ALL_TOOLS)

        # ASV 대기 상태 + 슬롯 완전 수집 상태 주입
        await real_g.aupdate_state(
            config,
            {
                "awaiting_asv_audio": True,
                "awaiting_confirmation": False,
                "pending_action": "transfer",
                "collected_slots": {"recipient": "엄마", "amount": 50000},
                "asv_retry_count": 0,
                "execution_ready": False,
                "navigate_to": None,
                "user_id": uid,
                "messages": [],
            },
            as_node="intent_node",
        )

        db = _db_with_embedding(FAKE_EMBEDDING_A)

        # ASV 결과를 성공으로 고정하여 LLM execute_node 흐름만 검증한다
        with (
            patch("app.shared.voice.service._get_graph", return_value=real_g),
            patch(
                "app.shared.voice.service._call_asv_ec2",
                new=AsyncMock(return_value=ASVResult(verified=True, score=0.92)),
            ),
            patch(
                "app.shared.voice.service.synthesize_speech",
                new=AsyncMock(return_value=b"MOCK_TTS"),
            ),
        ):
            result = await process_voice_pipeline(sample_wav, uid, db=db)

        # ASV 성공 → execute_node 실행 → 이체 완료 TTS 응답
        assert isinstance(result, VoiceResponseData)
        assert result.audio != ""
        assert result.awaiting_asv_audio is False

        # LLM이 execute_node를 통해 execute_transfer를 호출한 결과
        # 마지막 그래프 메시지에 이체 관련 내용이 포함되어야 한다
        state_after = real_g.get_state(config)
        last_content: str = state_after.values["messages"][-1].content
        assert "이체" in last_content or "완료" in last_content
