"""음성 파이프라인 오케스트레이션 서비스 (Issue #7).

이 모듈은 POST /api/voice 엔드포인트의 모든 비즈니스 로직을 담당한다.
두 가지 흐름을 조율한다:

  정상 흐름 (awaiting_asv_audio=False):
      오디오 → STT → LangGraph 에이전트 → TTS → VoiceResponseData

  ASV 인증 흐름 (awaiting_asv_audio=True):
      오디오 → ASV EC2 호출
            → 성공: 상태 업데이트 → 에이전트 실행 → TTS
            → 실패: 재시도 안내 TTS (최대 3회, 초과 시 취소)

Design Ref:
    §process_voice_pipeline — Issue #7 통합 파이프라인 진입점
    §_handle_asv_flow      — aupdate_state()로 graph 상태 직접 변경
    §_call_asv_ec2         — ai/asv/main.py POST /verify API 호출
"""

import asyncio
import base64
import io
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from langchain_core.messages import HumanMessage
from pydub import AudioSegment
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exception import ASVError
from app.core.metrics import (
    agent_routing_duration_seconds,
    agent_total_duration_seconds,
    asv_duration_seconds,
    asv_verification_total,
    pipeline_total_duration_seconds,
    voice_stage_duration,
)
from app.core.opensearch_writer import write_voice_pipeline_record_async
from app.core.request_context import get_request_id
from app.models.user import User
from app.shared.agent.slot_schema import SCREEN_MAP
from app.shared.agent.supervisor import build_supervisor
from app.shared.voice.message_utils import tts_text_from_messages
from app.shared.voice.schema import ASVResult, VoiceResponseData
from app.shared.voice.stt_service import transcribe_audio
from app.shared.voice.tts_service import synthesize_speech

logger = logging.getLogger(__name__)

# ── 백그라운드 태스크 참조 보관 (GC 방지) ──────────────────────────────────────
# asyncio.create_task() 결과를 저장하지 않으면 이벤트 루프가 weak reference만 유지해
# 실행 중에 GC로 수거될 수 있다. 완료 시 자동 제거된다.
_background_tasks: set[asyncio.Task] = set()

# ── 그래프 싱글턴 (지연 초기화) ────────────────────────────────────────────────
# 모듈 임포트 시점에 초기화하면 OPENAI_CHAT_API_KEY 미설정 환경(테스트 등)에서
# AgentError가 발생할 수 있다. 첫 요청 시 빌드하고 이후 재사용한다.

_graph = None


def _get_graph():
    """LangGraph 그래프 싱글턴을 반환한다. 최초 호출 시 build_supervisor()를 실행한다."""
    global _graph
    if _graph is None:
        _graph = build_supervisor()
    return _graph


# ── 최대 ASV 재시도 횟수 ────────────────────────────────────────────────────────
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
        "agent_domain": None,
        "analytics_period": None,
        "pending_consent_tts_text": None,
        "pending_consent_audio_b64": None,
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

    if pending in ("balance", "history", "event", "auto_transfer", "transfer"):
        return SCREEN_MAP.get(pending)

    return None


async def reset_voice_state(user_id: str) -> None:
    """유저의 LangGraph 대화 상태를 초기화한다."""
    graph = _get_graph()
    config = {"configurable": {"thread_id": user_id}}
    await graph.aupdate_state(
        config,
        _voice_state_reset_payload(),
        as_node="supervisor_node",
    )


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
    logger.info(
        "[Pipeline] user_id=%s awaiting_asv=%s state_values=%s",
        user_id,
        awaiting_asv,
        state_snapshot.values if state_snapshot.values else "EMPTY",
    )

    execution_ready = (
        state_snapshot.values.get("execution_ready", False)
        if state_snapshot.values
        else False
    )
    if execution_ready:
        audio_mp3 = await synthesize_speech(
            "이체를 처리하고 있습니다. 잠시만 기다려주세요."
        )
        return VoiceResponseData(
            audio=base64.b64encode(audio_mp3).decode(),
            navigate_to=None,
            collected_slots=state_snapshot.values.get("collected_slots", {}),
            awaiting_confirmation=False,
            awaiting_asv_audio=False,
            execution_pending=True,
            awaiting_memo_decision=False,
            transcript=None,
            pending_action=state_snapshot.values.get("pending_action"),
        )

    if awaiting_asv:
        return await _handle_asv_flow(
            audio_bytes, user_id, config, db, graph, content_type
        )
    else:
        return await _handle_normal_flow(
            audio_bytes, user_id, config, graph, content_type
        )


# ── 정상 흐름: STT → 에이전트 → TTS ────────────────────────────────────────────

_NAVIGATE_TO_INTENT: dict[str, str] = {
    "transfer": "transfer",
    "transfer/complete": "transfer",
    "transfer/failed": "transfer",
    "auto-transfer": "auto_transfer",
    "auto-transfer/complete": "auto_transfer",
    "balance": "balance",
    "event": "event",
    "home": "home",
}


def _infer_intent(result: dict) -> str | None:
    """에이전트 결과에서 인텐트를 추출한다.

    execute_node 실행 후 pending_action이 None으로 리셋되므로,
    pending_action이 없으면 navigate_to로 역추론한다.
    """
    pending = result.get("pending_action")
    if pending:
        return pending
    return _NAVIGATE_TO_INTENT.get(result.get("navigate_to") or "")


async def _record_voice_pipeline(
    user_id: str,
    stt_ms: int,
    agent_ms: int,
    tts_ms: int,
    total_ms: int,
    routing_ms: int | None,
    tool_execution_ms: int | None,
    intent: str | None,
    navigate_to: str | None,
) -> None:
    """음성 파이프라인 완료 이벤트를 로그와 OpenSearch에 기록합니다.

    Args:
        user_id: JWT 사용자 ID.
        stt_ms: STT 단계 소요 시간 (ms).
        agent_ms: Supervisor + Subagent + tool + DB 전체 소요 시간 (ms).
        tts_ms: TTS 단계 소요 시간 (ms).
        total_ms: audio in → TTS 완료 전체 소요 시간 (ms).
        routing_ms: Supervisor + Subagent + tool 선택까지만의 소요 시간 (ms).
            tool이 실행되지 않은 턴(슬롯 수집 등)에는 None.
        tool_execution_ms: tool 실행 + DB 적재 소요 시간 (ms).
            tool이 실행되지 않은 턴에는 None.
        intent: 감지된 인텐트 (pending_action).
        navigate_to: 에이전트가 설정한 화면 이동 경로.
    """
    record: dict = {
        "timestamp": datetime.now(timezone(timedelta(hours=9))).strftime(
            "%Y-%m-%dT%H:%M:%S+09:00"
        ),
        "request_id": get_request_id(),
        "user_id": user_id,
        "stt_ms": stt_ms,
        "agent_ms": agent_ms,
        "routing_ms": routing_ms,
        "tool_execution_ms": tool_execution_ms,
        "tts_ms": tts_ms,
        "total_ms": total_ms,
        "intent": intent or "unknown",
        "navigate_to": navigate_to,
        "success": True,
        "error_code": None,
    }
    logger.info(
        "voice_pipeline_complete", extra={"event": "voice_pipeline_complete", **record}
    )
    asyncio.create_task(write_voice_pipeline_record_async(record))
    voice_stage_duration.labels(stage="stt").observe(stt_ms / 1000)
    voice_stage_duration.labels(stage="agent").observe(agent_ms / 1000)
    voice_stage_duration.labels(stage="tts").observe(tts_ms / 1000)
    pipeline_total_duration_seconds.observe(total_ms / 1000)
    agent_total_duration_seconds.observe(agent_ms / 1000)
    if routing_ms is not None:
        agent_routing_duration_seconds.observe(routing_ms / 1000)


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
        db: SQLAlchemy DB 세션.
        content_type: 오디오 포맷.
        config: LangGraph thread_id 설정.
        graph: 컴파일된 StateGraph 인스턴스.

    Returns:
        VoiceResponseData: TTS 오디오 + 에이전트 상태 반영.
    """
    # 에이전트 호출 전 현재 state에서 awaiting_confirmation 확인
    state_before = graph.get_state(config)
    was_awaiting_confirmation = (
        state_before.values.get("awaiting_confirmation", False)
        if state_before.values
        else False
    )

    # 4-b: 현재 확인 대기 중이면 사용자 동의 음성을 base64로 임시 저장 (voice-consent-s3)
    # Plan SC: pending_consent_audio_b64 캡처 — 요청 B에 해당
    if was_awaiting_confirmation:
        try:
            consent_wav = _to_wav_bytes(audio_bytes)
            await graph.aupdate_state(
                config,
                {"pending_consent_audio_b64": base64.b64encode(consent_wav).decode()},
                as_node="supervisor_node",
            )
        except Exception:
            logger.warning("동의 음성 임시 저장 실패 — 계속 진행", exc_info=True)

    # 1. STT: 오디오 → 텍스트
    pipeline_start = time.monotonic()

    transcript = await transcribe_audio(audio_bytes, content_type)
    stt_ms = int((time.monotonic() - pipeline_start) * 1000)

    # 2. LangGraph 에이전트 호출 (LLM + tool + DB 시간 포함)
    t0 = time.monotonic()
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=transcript)],
            "user_id": user_id,
            "tool_execution_ms": None,
        },
        config=config,
    )
    agent_ms = int((time.monotonic() - t0) * 1000)
    tool_exec_ms: int | None = result.get("tool_execution_ms")
    routing_ms = (agent_ms - tool_exec_ms) if tool_exec_ms is not None else None

    response_text = tts_text_from_messages(result["messages"])

    # 4-a: awaiting_confirmation이 False→True로 전환되면 TTS 텍스트를 임시 저장 (voice-consent-s3)
    # Plan SC: pending_consent_tts_text 캡처 — 요청 A에 해당
    now_awaiting_confirmation = result.get("awaiting_confirmation", False)
    if not was_awaiting_confirmation and now_awaiting_confirmation:
        try:
            await graph.aupdate_state(
                config,
                {"pending_consent_tts_text": response_text},
                as_node="supervisor_node",
            )
        except Exception:
            logger.warning("TTS 텍스트 임시 저장 실패 — 계속 진행", exc_info=True)

    # 3. TTS: 텍스트 → MP3
    t0 = time.monotonic()
    audio_mp3 = await synthesize_speech(response_text)
    tts_ms = int((time.monotonic() - t0) * 1000)
    total_ms = int((time.monotonic() - pipeline_start) * 1000)

    audio_b64 = base64.b64encode(audio_mp3).decode()

    navigate_to = _resolve_navigate_to(result)
    await _record_voice_pipeline(
        user_id=user_id,
        stt_ms=stt_ms,
        agent_ms=agent_ms,
        tts_ms=tts_ms,
        total_ms=total_ms,
        routing_ms=routing_ms,
        tool_execution_ms=tool_exec_ms,
        intent=_infer_intent(result),
        navigate_to=navigate_to,
    )

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


# ── ASV 인증 흐름 ───────────────────────────────────────────────────────────────


def _to_wav_bytes(audio_bytes: bytes) -> bytes:
    """m4a/AAC 등 임의 포맷 오디오 바이트를 WAV(PCM)로 변환한다.

    ASV 서버의 soundfile은 m4a를 디코딩하지 못하므로 ASV 흐름 진입 시 호출한다.
    ffmpeg이 시스템에 설치되어 있어야 한다.

    Args:
        audio_bytes: 변환할 원시 오디오 바이트 (m4a, AAC 등).

    Returns:
        WAV PCM 포맷 바이트.
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
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

    ASV EC2 서버를 호출한다.
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
    pending_action = (
        state_snapshot.values.get("pending_action") if state_snapshot.values else None
    )
    retry_count = (
        state_snapshot.values.get("asv_retry_count", 0) if state_snapshot.values else 0
    )

    # DB에서 사용자 음성 임베딩 조회 (ASV /verify 호출에 필요)
    try:
        reference_embedding = _get_user_embedding(user_id, db)
    except ASVError as e:
        # 음성 미등록 → 인증 흐름 취소 후 홈으로 이동
        await reset_voice_state(user_id)
        tts_text = e.user_message or "음성 등록이 필요합니다. 앱에서 음성 등록을 먼저 진행해 주세요."
        audio_mp3 = await synthesize_speech(tts_text)
        return VoiceResponseData(
            audio=base64.b64encode(audio_mp3).decode(),
            navigate_to="home",
            collected_slots={},
            awaiting_confirmation=False,
            awaiting_asv_audio=False,
            awaiting_memo_decision=False,
            transcript=None,
            pending_action=None,
        )

    # m4a/AAC → WAV 변환 (soundfile은 m4a 디코딩 불가)
    wav_bytes = _to_wav_bytes(audio_bytes)

    logger.info(
        "[ASV] _call_asv_ec2 호출 직전: url=%s/verify "
        "embedding_len=%d audio_bytes=%d wav_bytes=%d",
        settings.ASV_SERVER_URL,
        len(reference_embedding),
        len(audio_bytes),
        len(wav_bytes),
    )

    # ASV 호출 — 서버 오류 시 슬롯·ASV 상태를 보존하고 재시도 안내
    _asv_error: ASVError | None = None
    t0 = time.monotonic()
    try:
        asv_result = await _call_asv_ec2(wav_bytes, reference_embedding)
    except ASVError as e:
        _asv_error = e
    except Exception as e:
        logger.error("ASV EC2 호출 중 예기치 못한 오류: %s", e)
        _asv_error = ASVError(
            code="ASV_SERVER_ERROR",
            message="화자 인증 서버와 통신 중 오류가 발생했습니다.",
            status_code=502,
            user_message="화자 인증 서버와 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )
    finally:
        duration_sec = time.monotonic() - t0
        asv_duration_seconds.observe(duration_sec)
        asv_ms = int(duration_sec * 1000)

    if _asv_error is not None:
        # 서버 오류: 슬롯·ASV 대기 상태를 보존하고 에러 TTS 반환 (슬롯 리셋 방지)
        current_slots = (
            state_snapshot.values.get("collected_slots", {})
            if state_snapshot.values
            else {}
        )
        tts_text = (
            _asv_error.user_message
            or "화자 인증 서버와 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        )
        logger.warning(
            "[ASV] 서버 오류 — 슬롯 보존 후 재시도 안내: user_id=%s code=%s",
            user_id,
            _asv_error.code,
        )
        audio_mp3 = await synthesize_speech(tts_text)
        return VoiceResponseData(
            audio=base64.b64encode(audio_mp3).decode(),
            navigate_to=SCREEN_MAP.get(pending_action) if pending_action else None,
            collected_slots=current_slots,
            awaiting_confirmation=False,
            awaiting_asv_audio=True,
            awaiting_memo_decision=False,
            transcript=None,
            pending_action=pending_action,
        )

    asv_ok = isinstance(asv_result, ASVResult) and asv_result.verified
    auth_success = asv_ok

    if auth_success:
        asv_verification_total.labels(result="pass").inc()
        asyncio.create_task(
            write_voice_pipeline_record_async(
                {
                    "timestamp": datetime.now(timezone(timedelta(hours=9))).strftime(
                        "%Y-%m-%dT%H:%M:%S+09:00"
                    ),
                    "request_id": get_request_id(),
                    "user_id": user_id,
                    "asv_result": "pass",
                    "asv_ms": asv_ms,
                    "similarity_score": round(asv_result.score, 4),
                    "success": True,
                }
            )
        )
        return await _return_processing_tts(config, graph)

    asv_verification_total.labels(result="fail").inc()
    asyncio.create_task(
        write_voice_pipeline_record_async(
            {
                "timestamp": datetime.now(timezone(timedelta(hours=9))).strftime(
                    "%Y-%m-%dT%H:%M:%S+09:00"
                ),
                "request_id": get_request_id(),
                "user_id": user_id,
                "asv_result": "fail",
                "asv_ms": asv_ms,
                "similarity_score": round(asv_result.score, 4),
                "success": False,
            }
        )
    )

    # ── 인증 실패 처리 ─────────────────────────────────────────────────────────
    new_retry = retry_count + 1
    logger.info(
        "ASV 인증 실패: user_id=%s, retry=%d/%d, asv_ok=%s",
        user_id,
        new_retry,
        _MAX_ASV_RETRIES,
        asv_ok,
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
                "awaiting_memo_decision": False,
                "navigate_to": "home",
                "agent_domain": None,
                "pending_consent_tts_text": None,
                "pending_consent_audio_b64": None,
            },
            as_node="supervisor_node",
        )
        tts_text = (
            "본인 확인에 세 번 실패하여 작업이 취소되었습니다. 홈 화면으로 이동합니다."
        )
        navigate_to_next: str | None = "home"
        awaiting_asv_next = False
    else:
        # 재시도 기회 남음 → retry_count만 증가
        remaining = _MAX_ASV_RETRIES - new_retry
        await graph.aupdate_state(
            config,
            {"asv_retry_count": new_retry},
            as_node="supervisor_node",
        )
        tts_text = (
            f"본인 확인에 실패했습니다. {remaining}번 더 시도하실 수 있습니다. "
            "다시 한번 말씀해 주세요."
        )
        # ASV 재시도 중 화면 이동 없음 — 수취인 입력 화면으로 되돌아가는 버그 방지
        navigate_to_next = None
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
        transcript=None,
        pending_action=pending_action if awaiting_asv_next else None,
    )


async def _return_processing_tts(
    config: dict,
    graph,
) -> VoiceResponseData:
    """ASV 인증 성공 직후 "처리 중" TTS를 즉시 반환한다.

    execution_ready=True를 graph 상태에 설정하되 ainvoke는 호출하지 않는다.
    프론트엔드는 execution_pending=True 수신 시 TTS를 재생한 뒤
    POST /api/voice/proceed를 자동 호출해 실제 이체를 실행한다.
    pending_consent_* 필드는 /proceed 에서 필요하므로 여기서 지우지 않는다.
    """
    state_snapshot = graph.get_state(config)
    state_vals = state_snapshot.values if state_snapshot.values else {}
    pending_action = state_vals.get("pending_action")
    collected_slots = state_vals.get("collected_slots", {})

    await graph.aupdate_state(
        config,
        {
            "awaiting_asv_audio": False,
            "execution_ready": True,
            "asv_retry_count": 0,
            "agent_domain": "transfer",
        },
        as_node="supervisor_node",
    )

    audio_mp3 = await synthesize_speech(
        "인증이 완료되었습니다. 이체 처리와 이체 확인 음성을 업로드 중입니다. 잠시만 기다려주십시오."
    )
    navigate_to = SCREEN_MAP.get(pending_action) if pending_action else None

    return VoiceResponseData(
        audio=base64.b64encode(audio_mp3).decode(),
        navigate_to=navigate_to,
        collected_slots=collected_slots,
        awaiting_confirmation=False,
        awaiting_asv_audio=False,
        execution_pending=True,
        awaiting_memo_decision=False,
        awaiting_transfer_clarification=False,
        transcript=None,
        pending_action=pending_action,
    )


async def _execute_pending_transfer(
    user_id: str,
    config: dict,
    graph,
) -> VoiceResponseData:
    """execution_ready=True 상태에서 실제 이체를 실행하고 결과 TTS를 반환한다.

    POST /api/voice/proceed 엔드포인트의 실제 처리 함수.
    """
    # 동의 음성 업로드에 필요한 임시 필드를 읽은 뒤 즉시 초기화한다
    state_snapshot = graph.get_state(config)
    state_vals = state_snapshot.values if state_snapshot.values else {}
    pending_tts_text: str | None = state_vals.get("pending_consent_tts_text")
    pending_audio_b64: str | None = state_vals.get("pending_consent_audio_b64")

    await graph.aupdate_state(
        config,
        {
            "pending_consent_tts_text": None,
            "pending_consent_audio_b64": None,
        },
        as_node="supervisor_node",
    )

    pipeline_start = time.monotonic()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="인증 완료")], "user_id": user_id},
        config=config,
    )
    agent_ms = int((time.monotonic() - pipeline_start) * 1000)
    tool_exec_ms: int | None = result.get("tool_execution_ms")
    routing_ms = (agent_ms - tool_exec_ms) if tool_exec_ms is not None else None

    response_text = tts_text_from_messages(result["messages"])
    tx_id: str | None = result.get("last_tx_id") or result.get("last_order_id")
    logger.info(
        "[ConsentS3] pending_tts=%s pending_audio=%s tx_id=%s",
        bool(pending_tts_text),
        bool(pending_audio_b64),
        tx_id,
    )

    tts_start = time.monotonic()
    if pending_tts_text and pending_audio_b64 and tx_id:
        from app.shared.voice import s3_service

        # 결과 TTS와 동의 TTS(S3용)를 동시에 합성한다.
        # 백그라운드 task는 TTS 합성 없이 즉시 S3 업로드를 시작하므로
        # 사용자가 "업로드하고 있습니다" 메시지를 듣는 시점에 실제 업로드가 진행 중이다.
        audio_mp3, consent_tts_mp3 = await asyncio.gather(
            synthesize_speech(response_text),
            synthesize_speech(pending_tts_text),
        )
        tts_ms = int((time.monotonic() - tts_start) * 1000)

        async def _upload_consent_task(
            _user_id: str,
            _tx_id: str,
            _tts_mp3: bytes,
            _audio_b64: str,
        ) -> None:
            try:
                tts_wav = s3_service.mp3_to_wav(_tts_mp3)
                consent_wav = base64.b64decode(_audio_b64)
                combined = s3_service.concat_wav(tts_wav, consent_wav)
                await s3_service.upload_consent_audio(_user_id, _tx_id, combined)
            except Exception:
                logger.error(
                    "동의 음성 S3 업로드 실패 (이체 결과 영향 없음)", exc_info=True
                )

        task = asyncio.create_task(
            _upload_consent_task(user_id, tx_id, consent_tts_mp3, pending_audio_b64)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    else:
        audio_mp3 = await synthesize_speech(response_text)
        tts_ms = int((time.monotonic() - tts_start) * 1000)

    total_ms = int((time.monotonic() - pipeline_start) * 1000)
    await _record_voice_pipeline(
        user_id=user_id,
        stt_ms=0,
        agent_ms=agent_ms,
        tts_ms=tts_ms,
        total_ms=total_ms,
        routing_ms=routing_ms,
        tool_execution_ms=tool_exec_ms,
        intent=_infer_intent(result),
        navigate_to=_resolve_navigate_to(result),
    )

    return VoiceResponseData(
        audio=base64.b64encode(audio_mp3).decode(),
        navigate_to=_resolve_navigate_to(result),
        collected_slots=result.get("collected_slots") or {},
        awaiting_confirmation=result.get("awaiting_confirmation", False),
        awaiting_asv_audio=False,
        execution_pending=False,
        awaiting_memo_decision=result.get("awaiting_memo_decision", False),
        awaiting_transfer_clarification=result.get(
            "awaiting_transfer_clarification", False
        ),
        transcript=None,
        pending_action=result.get("pending_action"),
    )


async def execute_pending_transfer(user_id: str) -> VoiceResponseData:
    """POST /api/voice/proceed 엔드포인트 진입점.

    Args:
        user_id: JWT에서 추출한 사용자 ID.

    Returns:
        VoiceResponseData: 이체 결과 TTS + 상태 플래그.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": user_id}}
    return await _execute_pending_transfer(user_id, config, graph)


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
    if user is None or user.embedding_vector is None:
        raise ASVError(
            code="ASV_NOT_ENROLLED",
            message="음성 등록이 필요합니다. 앱에서 음성 등록을 먼저 진행해 주세요.",
            status_code=422,
        )

    # pgvector는 numpy array를 반환. float32 → Python float으로 변환해야
    # json.dumps가 가능하다.
    return [float(v) for v in user.embedding_vector]


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
        async with httpx.AsyncClient(timeout=30.0) as client:
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
