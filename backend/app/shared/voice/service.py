"""음성 파이프라인 오케스트레이션 서비스 (Issue #7).

이 모듈은 POST /api/voice 엔드포인트의 모든 비즈니스 로직을 담당한다.
두 가지 흐름을 조율한다:

  정상 흐름 (awaiting_asv_audio=False):
      오디오 → STT → LangGraph 에이전트 → TTS → VoiceResponseData

  ASV 인증 흐름 (awaiting_asv_audio=True):
      오디오 → ASV EC2 + anti-spoofing EC2 병렬 호출
            → 성공: 상태 업데이트 → 에이전트 실행 → TTS
            → 실패: 재시도 안내 TTS (최대 3회, 초과 시 취소)

Design Ref:
    §process_voice_pipeline — Issue #7 통합 파이프라인 진입점
    §_handle_asv_flow      — aupdate_state()로 graph 상태 직접 변경
    §_call_asv_ec2         — ai/asv/main.py POST /verify API 호출
"""

import asyncio
import base64
import json
import logging
import uuid

import httpx
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exception import ASVError
from app.models.user import User
from app.shared.agent import build_graph
from app.shared.agent.tools import ALL_TOOLS
from app.shared.voice.schema import AntiSpoofResult, ASVResult, VoiceResponseData
from app.shared.voice.stt_service import transcribe_audio
from app.shared.voice.tts_service import synthesize_speech

logger = logging.getLogger(__name__)

# ── 그래프 싱글턴 (지연 초기화) ────────────────────────────────────────────────
# 모듈 임포트 시점에 초기화하면 OPENAI_CHAT_API_KEY 미설정 환경(테스트 등)에서
# AgentError가 발생할 수 있다. 첫 요청 시 빌드하고 이후 재사용한다.

_graph = None


def _get_graph():
    """LangGraph 그래프 싱글턴을 반환한다. 최초 호출 시 build_graph()를 실행한다."""
    global _graph
    if _graph is None:
        _graph = build_graph(ALL_TOOLS)
    return _graph


# ── 최대 ASV 재시도 횟수 ────────────────────────────────────────────────────────
_MAX_ASV_RETRIES = 3


# ── 공개 진입점 ─────────────────────────────────────────────────────────────────


async def process_voice_pipeline(
    audio_bytes: bytes,
    user_id: str,
    db: Session,
    content_type: str = "audio/wav",
) -> VoiceResponseData:
    """음성 파이프라인 통합 진입점.

    LangGraph 멀티턴 상태(MemorySaver)를 조회해 현재 awaiting_asv_audio 여부에 따라
    정상 흐름 또는 ASV 인증 흐름으로 분기한다.

    Args:
        audio_bytes: UploadFile에서 읽은 원시 오디오 바이트.
        user_id: JWT에서 추출한 사용자 ID 문자열 (= LangGraph thread_id).
        db: FastAPI Depends로 주입된 SQLAlchemy 세션. ASV 흐름에서만 사용.

    Returns:
        VoiceResponseData: base64 MP3, 화면 이동 신호, 슬롯 상태를 담은 응답.

    Raises:
        STTError: Clova Speech API 호출 실패.
        TTSError: Azure TTS API 호출 실패.
        ASVError: ASV EC2 서버 호출 실패 또는 음성 미등록 사용자.
        AgentError: LangGraph 에이전트 초기화·실행 오류.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": user_id}}

    # 현재 그래프 상태에서 awaiting_asv_audio 플래그 확인
    state_snapshot = graph.get_state(config)
    awaiting_asv = (
        state_snapshot.values.get("awaiting_asv_audio", False)
        if state_snapshot.values
        else False
    )

    if awaiting_asv:
        return await _handle_asv_flow(audio_bytes, user_id, config, db, graph)
    else:
        return await _handle_normal_flow(
            audio_bytes, user_id, config, graph, content_type
        )


# ── 정상 흐름: STT → 에이전트 → TTS ────────────────────────────────────────────


async def _handle_normal_flow(
    audio_bytes: bytes,
    user_id: str,
    config: dict,
    graph,
    content_type: str = "audio/wav",
) -> VoiceResponseData:
    """정상 음성 처리 흐름.

    Args:
        audio_bytes: 원시 오디오 바이트.
        user_id: JWT 사용자 ID.
        config: LangGraph thread_id 설정.
        graph: 컴파일된 StateGraph 인스턴스.

    Returns:
        VoiceResponseData: TTS 오디오 + 에이전트 상태 반영.
    """
    # 1. STT: 오디오 → 텍스트
    transcript = await transcribe_audio(audio_bytes, content_type)

    # 2. LangGraph 에이전트 호출
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=transcript)],
            "user_id": user_id,
        },
        config=config,
    )

    response_text = result["messages"][-1].content

    # 3. TTS: 텍스트 → MP3
    audio_mp3 = await synthesize_speech(response_text)
    audio_b64 = base64.b64encode(audio_mp3).decode()

    return VoiceResponseData(
        audio=audio_b64,
        navigate_to=result.get("navigate_to"),
        collected_slots=result.get("collected_slots") or {},
        awaiting_confirmation=result.get("awaiting_confirmation", False),
        awaiting_asv_audio=result.get("awaiting_asv_audio", False),
        transcript=transcript,
    )


# ── ASV 인증 흐름 ───────────────────────────────────────────────────────────────


async def _handle_asv_flow(
    audio_bytes: bytes,
    user_id: str,
    config: dict,
    db: Session,
    graph,
) -> VoiceResponseData:
    """ASV 화자 인증 처리 흐름.

    ASV EC2 서버와 anti-spoofing 서버를 asyncio.gather로 병렬 호출한다.
    성공 시 aupdate_state()로 execution_ready=True를 설정하고 에이전트를 실행한다.
    실패 시 retry_count를 증가시키고 남은 횟수를 TTS로 안내한다.
    3회 초과 실패 시 작업을 취소하고 상태를 초기화한다.

    Args:
        audio_bytes: ASV 검증용 원시 오디오 바이트 (WAV 권장).
        user_id: JWT 사용자 ID.
        config: LangGraph thread_id 설정.
        db: SQLAlchemy 세션 (사용자 임베딩 조회용).
        graph: 컴파일된 StateGraph 인스턴스.

    Returns:
        VoiceResponseData: 인증 결과에 따른 TTS 응답.

    Raises:
        ASVError: 사용자 음성 미등록 또는 ASV EC2 서버 통신 오류.
    """
    state_snapshot = graph.get_state(config)
    retry_count = (
        state_snapshot.values.get("asv_retry_count", 0) if state_snapshot.values else 0
    )

    # DB에서 사용자 음성 임베딩 조회 (ASV /verify 호출에 필요)
    reference_embedding = _get_user_embedding(user_id, db)

    # ASV + anti-spoofing 병렬 호출
    asv_result, spoof_result = await asyncio.gather(
        _call_asv_ec2(audio_bytes, reference_embedding),
        _call_anti_spoofing_ec2(audio_bytes),
        return_exceptions=True,
    )

    asv_ok = isinstance(asv_result, ASVResult) and asv_result.verified
    spoof_ok = isinstance(spoof_result, AntiSpoofResult) and spoof_result.is_real

    # 실패 원인 로깅 (ASV 예외 발생 시 재raise)
    if isinstance(asv_result, ASVError):
        raise asv_result
    if isinstance(asv_result, Exception):
        logger.error("ASV EC2 호출 중 예기치 못한 오류: %s", asv_result)
        raise ASVError(
            code="ASV_SERVER_ERROR",
            message="화자 인증 서버와 통신 중 오류가 발생했습니다.",
            status_code=502,
        )

    auth_success = asv_ok and spoof_ok

    if auth_success:
        return await _proceed_after_asv_success(user_id, config, graph)

    # ── 인증 실패 처리 ─────────────────────────────────────────────────────────
    new_retry = retry_count + 1
    logger.info(
        "ASV 인증 실패: user_id=%s, retry=%d/%d, asv_ok=%s, spoof_ok=%s",
        user_id,
        new_retry,
        _MAX_ASV_RETRIES,
        asv_ok,
        spoof_ok,
    )

    if new_retry >= _MAX_ASV_RETRIES:
        # 3회 초과 → 작업 취소 및 상태 초기화
        await graph.aupdate_state(
            config,
            {
                "awaiting_asv_audio": False,
                "awaiting_confirmation": False,
                "execution_ready": False,
                "pending_action": None,
                "collected_slots": {},
                "asv_retry_count": 0,
                "navigate_to": None,
                "last_tx_id": None,
            },
            as_node="intent_node",
        )
        tts_text = (
            "본인 확인에 세 번 실패하여 작업이 취소되었습니다. "
            "처음부터 다시 말씀해 주세요."
        )
        awaiting_asv_next = False
    else:
        # 재시도 기회 남음 → retry_count만 증가
        remaining = _MAX_ASV_RETRIES - new_retry
        await graph.aupdate_state(
            config,
            {"asv_retry_count": new_retry},
            as_node="intent_node",
        )
        tts_text = (
            f"본인 확인에 실패했습니다. {remaining}번 더 시도하실 수 있습니다. "
            "다시 한번 말씀해 주세요."
        )
        awaiting_asv_next = True

    audio_mp3 = await synthesize_speech(tts_text)
    return VoiceResponseData(
        audio=base64.b64encode(audio_mp3).decode(),
        navigate_to=None,
        collected_slots={},
        awaiting_confirmation=False,
        awaiting_asv_audio=awaiting_asv_next,
        transcript=None,
    )


async def _proceed_after_asv_success(
    user_id: str,
    config: dict,
    graph,
) -> VoiceResponseData:
    """ASV 인증 성공 후 에이전트 실행 흐름.

    aupdate_state()로 execution_ready=True를 주입하면
    route_after_intent가 execute_node로 라우팅한다.

    Args:
        user_id: JWT 사용자 ID.
        config: LangGraph thread_id 설정.
        graph: 컴파일된 StateGraph 인스턴스.

    Returns:
        VoiceResponseData: 금융 작업 실행 결과 TTS 응답.
    """
    # execution_ready=True 주입 → intent_node 이후 route_after_intent가 execute_node로 라우팅
    await graph.aupdate_state(
        config,
        {
            "awaiting_asv_audio": False,
            "execution_ready": True,
            "asv_retry_count": 0,
        },
        as_node="intent_node",
    )

    # intent_node는 LLM을 호출하지만 execution_ready=True가 보존되어
    # route_after_intent → execute_node로 직행한다. (graph.py 수정 불필요)
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="인증 완료")],
            "user_id": user_id,
        },
        config=config,
    )

    response_text = result["messages"][-1].content
    audio_mp3 = await synthesize_speech(response_text)

    return VoiceResponseData(
        audio=base64.b64encode(audio_mp3).decode(),
        navigate_to=result.get("navigate_to"),
        collected_slots=result.get("collected_slots") or {},
        awaiting_confirmation=result.get("awaiting_confirmation", False),
        awaiting_asv_audio=False,
        transcript=None,
    )


# ── DB 조회 ─────────────────────────────────────────────────────────────────────


def _get_user_embedding(user_id_str: str, db: Session) -> list[float]:
    """DB에서 사용자의 음성 임베딩 벡터를 조회한다.

    Args:
        user_id_str: JWT sub 값 (UUID 문자열).
        db: SQLAlchemy 세션.

    Returns:
        192차원 float 배열 (CAM++ ASV 모델 임베딩).

    Raises:
        ASVError(code="ASV_NOT_ENROLLED"): 사용자를 찾을 수 없거나 임베딩이 없는 경우.
    """
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise ASVError(
            code="ASV_NOT_ENROLLED",
            message="유효하지 않은 사용자 ID입니다.",
            status_code=400,
        )

    user: User | None = db.get(User, user_uuid)
    if user is None or not user.embedding_vector:
        raise ASVError(
            code="ASV_NOT_ENROLLED",
            message="음성 등록이 필요합니다. 앱에서 음성 등록을 먼저 진행해 주세요.",
            status_code=422,
        )

    # pgvector는 list 또는 numpy array 반환. list[float]로 변환
    return list(user.embedding_vector)


# ── 외부 EC2 서버 호출 ──────────────────────────────────────────────────────────


async def _call_asv_ec2(
    audio_bytes: bytes,
    reference_embedding: list[float],
) -> ASVResult:
    """ASV EC2 서버(ai/asv/main.py, POST /verify)를 호출한다.

    multipart/form-data로 오디오 파일과 reference_embedding(JSON 직렬화)을 전송한다.

    Args:
        audio_bytes: WAV 오디오 바이트 (16kHz 권장).
        reference_embedding: DB에서 가져온 192차원 임베딩 벡터.

    Returns:
        ASVResult: verified(bool) + score(float) 결과.

    Raises:
        ASVError: HTTP 오류 또는 타임아웃.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ASV_SERVER_URL}/verify",
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                data={"reference_embedding": json.dumps(reference_embedding)},
            )
            resp.raise_for_status()
            data = resp.json()
            return ASVResult(
                verified=data["is_same_speaker"],
                score=data["similarity_score"],
            )
    except httpx.HTTPStatusError as e:
        logger.error("ASV 서버 HTTP 오류 %d: %s", e.response.status_code, e)
        raise ASVError(
            code="ASV_SERVER_ERROR",
            message="화자 인증 서버 오류가 발생했습니다.",
            status_code=502,
        ) from e
    except httpx.TimeoutException as e:
        logger.error("ASV 서버 타임아웃: %s", e)
        raise ASVError(
            code="ASV_TIMEOUT",
            message="화자 인증 서버 응답 시간이 초과되었습니다.",
            status_code=504,
        ) from e


async def _call_anti_spoofing_ec2(audio_bytes: bytes) -> AntiSpoofResult:
    """Anti-spoofing EC2 서버(POST /detect)를 호출한다.

    ai/anti-spoofing/이 미구현 상태이므로 settings.USE_ANTI_SPOOFING=False(기본값)이면
    is_real=True를 즉시 반환하여 바이패스한다.

    Args:
        audio_bytes: 검사할 오디오 바이트.

    Returns:
        AntiSpoofResult: is_real(bool) + confidence(float).
    """
    if not settings.USE_ANTI_SPOOFING:
        # anti-spoofing 서버 미구현 — 바이패스 (항상 실제 음성으로 간주)
        return AntiSpoofResult(is_real=True, confidence=1.0)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ANTI_SPOOFING_EC2_URL}/detect",
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            )
            resp.raise_for_status()
            data = resp.json()
            return AntiSpoofResult(
                is_real=data["is_real"],
                confidence=data.get("confidence", 0.0),
            )
    except httpx.HTTPStatusError as e:
        logger.warning("Anti-spoofing 서버 HTTP 오류 %d: %s", e.response.status_code, e)
        # anti-spoofing 실패 시 보수적으로 is_real=False 반환
        return AntiSpoofResult(is_real=False, confidence=0.0)
    except httpx.TimeoutException as e:
        logger.warning("Anti-spoofing 서버 타임아웃: %s", e)
        return AntiSpoofResult(is_real=False, confidence=0.0)
