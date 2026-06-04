"""음성 파이프라인 오케스트레이션 서비스 (Issue #7)."""

import asyncio
import base64
import io
import json
import logging
import uuid

import httpx
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

try:
    from pydub import AudioSegment as _AudioSegment
    _PYDUB_AVAILABLE = True
except ImportError:
    _PYDUB_AVAILABLE = False

from app.core.config import settings
from app.core.exception import ASVError
from app.models.user import User
from app.shared.agent import build_graph
from app.shared.agent.slot_schema import SCREEN_MAP
from app.shared.agent.tools import ALL_TOOLS
from app.shared.agent.transfer_clarification import (
    is_clarification_no,
    is_home_request,
)
from app.shared.voice.schema import AntiSpoofResult, ASVResult, VoiceResponseData
from app.shared.voice.message_utils import tts_text_from_messages
from app.shared.voice.stt_service import transcribe_audio
from app.shared.voice.tts_service import synthesize_speech

logger = logging.getLogger(__name__)

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(ALL_TOOLS)
    return _graph


_MAX_ASV_RETRIES = 3


# ── 상태 초기화 ─────────────────────────────────────────────────────────────────


def _voice_state_reset_payload() -> dict:
    """LangGraph 음성 세션 전체 초기화 필드 (graph home intent와 동일)."""
    from app.shared.agent.session_reset import clear_conversation_messages

    return {
        "pending_action": None,
        "collected_slots": {},
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "execution_ready": False,
        "recipient_validated": False,
        "asv_retry_count": 0,
        "navigate_to": None,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "last_tx_id": None,
        "last_order_id": None,
        "messages": clear_conversation_messages(),
    }


def _resolve_navigate_to(result: dict) -> str | None:
    """graph navigate_to 또는 대기 상태 기준 fallback.

    슬롯만 보충된 턴에는 pending_action만 남고 navigate_to가 없을 수 있다.
    이 경우 None을 반환해 프론트가 같은 라우트로 replace 하지 않게 한다.
    """
    explicit = result.get("navigate_to")
    if explicit:
        return explicit

    pending = result.get("pending_action")

    if result.get("awaiting_asv_audio") and pending in SCREEN_MAP:
        return SCREEN_MAP[pending]

    if result.get("awaiting_confirmation") and pending in SCREEN_MAP:
        return SCREEN_MAP[pending]

    if pending in ("balance", "history", "event", "auto_transfer"):
        return SCREEN_MAP.get(pending)

    return None


async def reset_voice_state(user_id: str) -> None:
    """유저의 LangGraph 대화 상태를 초기화한다."""
    graph = _get_graph()
    config = {"configurable": {"thread_id": user_id}}
    await graph.aupdate_state(
        config,
        _voice_state_reset_payload(),
        as_node="intent_node",
    )


# ── 공개 진입점 ─────────────────────────────────────────────────────────────────


async def process_voice_pipeline(
    audio_bytes: bytes,
    user_id: str,
    db: Session,
    content_type: str = "audio/wav",
) -> VoiceResponseData:
    graph = _get_graph()
    config = {"configurable": {"thread_id": user_id}}

    state_snapshot = graph.get_state(config)
    awaiting_asv = (
        state_snapshot.values.get("awaiting_asv_audio", False)
        if state_snapshot.values
        else False
    )
    logger.info(
        "[Pipeline] user_id=%s awaiting_asv=%s state_values=%s",
        user_id,
        awaiting_asv,
        state_snapshot.values if state_snapshot.values else "EMPTY",
    )

    if awaiting_asv:
        return await _handle_asv_flow(
            audio_bytes, user_id, config, db, graph, content_type
        )
    else:
        return await _handle_normal_flow(
            audio_bytes, user_id, config, graph, content_type
        )


async def _handle_normal_flow(
    audio_bytes: bytes,
    user_id: str,
    config: dict,
    graph,
    content_type: str = "audio/wav",
) -> VoiceResponseData:
    transcript = await transcribe_audio(audio_bytes, content_type)

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=transcript)],
            "user_id": user_id,
        },
        config=config,
    )

    response_text = tts_text_from_messages(result["messages"])

    # 3. TTS: 텍스트 → MP3
    audio_mp3 = await synthesize_speech(response_text)
    audio_b64 = base64.b64encode(audio_mp3).decode()

    navigate_to = _resolve_navigate_to(result)

    if navigate_to == "home":
        await reset_voice_state(user_id)
        reset_fields = _voice_state_reset_payload()
        collected_slots = reset_fields["collected_slots"]
        pending_action = reset_fields["pending_action"]
        awaiting_confirmation = reset_fields["awaiting_confirmation"]
        awaiting_asv_audio = reset_fields["awaiting_asv_audio"]
        awaiting_memo_decision = reset_fields["awaiting_memo_decision"]
        awaiting_transfer_clarification = reset_fields[
            "awaiting_transfer_clarification"
        ]
    else:
        collected_slots = result.get("collected_slots") or {}
        pending_action = result.get("pending_action")
        awaiting_confirmation = result.get("awaiting_confirmation", False)
        awaiting_asv_audio = result.get("awaiting_asv_audio", False)
        awaiting_memo_decision = result.get("awaiting_memo_decision", False)
        awaiting_transfer_clarification = result.get(
            "awaiting_transfer_clarification", False
        )

    return VoiceResponseData(
        audio=audio_b64,
        navigate_to=navigate_to,
        collected_slots=collected_slots,
        awaiting_confirmation=awaiting_confirmation,
        awaiting_asv_audio=awaiting_asv_audio,
        awaiting_memo_decision=awaiting_memo_decision,
        awaiting_transfer_clarification=awaiting_transfer_clarification,
        transcript=transcript,
        pending_action=pending_action,
    )


def _to_wav_bytes(audio_bytes: bytes) -> bytes:
    """m4a/AAC 등 임의 포맷 오디오 바이트를 WAV(PCM)로 변환한다."""
    if not _PYDUB_AVAILABLE:
        # pydub 미설치(Python 3.13+ 호환성 이슈) 시 원본 그대로 반환
        return audio_bytes
    audio = _AudioSegment.from_file(io.BytesIO(audio_bytes))
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    return buf.getvalue()


async def _handle_asv_flow(
    audio_bytes: bytes,
    user_id: str,
    config: dict,
    db: Session,
    graph,
    content_type: str = "audio/wav",
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
    # ASV 인증음은 짧아 STT가 텍스트를 못 뽑을 수 있으므로 실패 시 무시하고 ASV로 진행
    try:
        transcript = await transcribe_audio(audio_bytes, content_type)
    except Exception:
        transcript = ""

    if transcript and (is_home_request(transcript) or is_clarification_no(transcript)):
        await reset_voice_state(user_id)
        tts_text = "홈 화면으로 이동합니다."
        audio_mp3 = await synthesize_speech(tts_text)
        return VoiceResponseData(
            audio=base64.b64encode(audio_mp3).decode(),
            navigate_to="home",
            collected_slots={},
            awaiting_confirmation=False,
            awaiting_asv_audio=False,
            awaiting_memo_decision=False,
            transcript=transcript,
            pending_action=None,
        )

    state_snapshot = graph.get_state(config)
    pending_action = (
        state_snapshot.values.get("pending_action") if state_snapshot.values else None
    )
    retry_count = (
        state_snapshot.values.get("asv_retry_count", 0) if state_snapshot.values else 0
    )

    reference_embedding = _get_user_embedding(user_id, db)

    wav_bytes = _to_wav_bytes(audio_bytes)

    logger.info(
        "[ASV] _call_asv_ec2 호출 직전: url=%s/verify "
        "embedding_len=%d audio_bytes=%d wav_bytes=%d",
        settings.ASV_SERVER_URL,
        len(reference_embedding),
        len(audio_bytes),
        len(wav_bytes),
    )

    asv_result, spoof_result = await asyncio.gather(
        _call_asv_ec2(wav_bytes, reference_embedding),
        _call_anti_spoofing_ec2(wav_bytes),
        return_exceptions=True,
    )

    asv_ok = isinstance(asv_result, ASVResult) and asv_result.verified
    spoof_ok = isinstance(spoof_result, AntiSpoofResult) and spoof_result.is_real

    if isinstance(asv_result, ASVError):
        raise asv_result
    if isinstance(asv_result, Exception):
        logger.error("ASV EC2 호출 중 예기치 못한 오류: %s", asv_result)
        raise ASVError(
            code="ASV_SERVER_ERROR",
            message="화자 인증 서버와 통신 중 오류가 발생했습니다.",
            status_code=502,
            user_message="화자 인증 서버와 통신 중 오류가 발생했습니다.",
        )

    auth_success = asv_ok and spoof_ok

    if auth_success:
        return await _proceed_after_asv_success(user_id, config, graph)

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
        await graph.aupdate_state(
            config,
            {
                "awaiting_asv_audio": False,
                "awaiting_confirmation": False,
                "execution_ready": False,
                "pending_action": None,
                "collected_slots": {},
                "asv_retry_count": 0,
                "awaiting_memo_decision": False,
                "navigate_to": "home",
            },
            as_node="intent_node",
        )
        tts_text = (
            "본인 확인에 세 번 실패하여 작업이 취소되었습니다. 홈 화면으로 이동합니다."
        )
        navigate_to_next: str | None = "home"
        awaiting_asv_next = False
    else:
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
        navigate_to_next = SCREEN_MAP.get(pending_action) if pending_action else None
        awaiting_asv_next = True

    fail_slots = (
        state_snapshot.values.get("collected_slots", {})
        if state_snapshot.values
        else {}
    )
    audio_mp3 = await synthesize_speech(tts_text)
    return VoiceResponseData(
        audio=base64.b64encode(audio_mp3).decode(),
        navigate_to=navigate_to_next,
        collected_slots=fail_slots if awaiting_asv_next else {},
        awaiting_confirmation=False,
        awaiting_asv_audio=awaiting_asv_next,
        awaiting_memo_decision=False,
        transcript=transcript,
        pending_action=pending_action if awaiting_asv_next else None,
    )


async def _proceed_after_asv_success(
    user_id: str,
    config: dict,
    graph,
) -> VoiceResponseData:
    await graph.aupdate_state(
        config,
        {
            "awaiting_asv_audio": False,
            "execution_ready": True,
            "asv_retry_count": 0,
        },
        as_node="intent_node",
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="인증 완료")],
            "user_id": user_id,
        },
        config=config,
    )

    response_text = tts_text_from_messages(result["messages"])
    audio_mp3 = await synthesize_speech(response_text)

    return VoiceResponseData(
        audio=base64.b64encode(audio_mp3).decode(),
        navigate_to=_resolve_navigate_to(result),
        collected_slots=result.get("collected_slots") or {},
        awaiting_confirmation=result.get("awaiting_confirmation", False),
        awaiting_asv_audio=False,
        awaiting_memo_decision=result.get("awaiting_memo_decision", False),
        awaiting_transfer_clarification=result.get(
            "awaiting_transfer_clarification", False
        ),
        transcript=None,
        pending_action=result.get("pending_action"),
    )


def _get_user_embedding(user_id_str: str, db: Session) -> list[float]:
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise ASVError(
            code="ASV_NOT_ENROLLED",
            message="유효하지 않은 사용자 ID입니다.",
            status_code=400,
        )

    user: User | None = db.get(User, user_uuid)
    if user is None or user.embedding_vector is None:
        raise ASVError(
            code="ASV_NOT_ENROLLED",
            message="음성 등록이 필요합니다. 앱에서 음성 등록을 먼저 진행해 주세요.",
            status_code=422,
        )

    return [float(v) for v in user.embedding_vector]


async def _call_asv_ec2(
    audio_bytes: bytes,
    reference_embedding: list[float],
) -> ASVResult:
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
    if not settings.USE_ANTI_SPOOFING:
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
        return AntiSpoofResult(is_real=False, confidence=0.0)
    except httpx.TimeoutException as e:
        logger.warning("Anti-spoofing 서버 타임아웃: %s", e)
        return AntiSpoofResult(is_real=False, confidence=0.0)
