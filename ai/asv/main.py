"""ASV (Automatic Speaker Verification) FastAPI 서버.

CAM++ 모델 기반 화자 인증 서버.
/enroll (임베딩 추출) + /verify (화자 비교) + /health 엔드포인트 제공.

# Design Ref: §3.3 — FastAPI 앱, lifespan 초기화, 인라인 Pydantic 스키마
# Design Ref: §10.2 — multipart+JSON 동시 수신: Form(json.loads) 패턴
"""

import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Form, HTTPException, UploadFile
from pydantic import BaseModel

from config import settings
from model import ASVModel

# 앱 수준 싱글턴 — lifespan에서 초기화, 이후 불변
# Design Ref: §3.3 — 의존성 주입 미적용, 단일 책임 서버에 적합
asv_model: ASVModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """서버 시작 시 ASV 모델을 로딩합니다.

    모델 로딩 실패 시 RuntimeError를 발생시켜 서버 시작을 차단합니다.
    (Fail-Fast 원칙 — Plan SC: FR-05)
    """
    global asv_model
    asv_model = ASVModel()
    yield
    # Shutdown: PyTorch 모델의 명시적 해제는 불필요


# ── FastAPI 앱 ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="ASV Speaker Verification Server",
    description=(
        "CAM++ 기반 화자 인증 서버.\n\n"
        "- `/enroll`: 오디오 → 192차원 임베딩 반환\n"
        "- `/verify`: 오디오 + 참조 임베딩 → 동일 화자 여부 판별\n"
        "- `/health`: 서버 상태 확인"
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── 응답 스키마 (인라인 Pydantic 모델) ─────────────────────────────────────

class EnrollResponse(BaseModel):
    """POST /enroll 응답 스키마."""

    embedding: list[float]
    """192차원 float 배열. 메인 백엔드가 users.embedding_vector에 저장."""


class VerifyResponse(BaseModel):
    """POST /verify 응답 스키마."""

    is_same_speaker: bool
    """코사인 유사도 >= ASV_THRESHOLD이면 True."""

    similarity_score: float
    """0.0 ~ 1.0 사이의 코사인 유사도 값."""


class HealthResponse(BaseModel):
    """GET /health 응답 스키마."""

    status: str
    """'ok' 또는 'error'."""

    model_loaded: bool
    """모델이 로딩되어 있으면 True."""


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def _require_model() -> ASVModel:
    """모델이 로딩되어 있지 않으면 503을 반환합니다.

    Returns:
        로딩된 ASVModel 인스턴스.

    Raises:
        HTTPException(503): 모델이 None인 경우.
    """
    if asv_model is None:
        raise HTTPException(
            status_code=503,
            detail="ASV model not loaded",
        )
    return asv_model


# ── 엔드포인트 ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["monitoring"])
async def health_check() -> HealthResponse:
    """서버 상태 및 모델 로딩 여부를 반환합니다.

    Returns:
        HealthResponse: status='ok' + model_loaded=True 이면 정상.

    # Plan SC: FR-06 — 서버 상태 + 모델 로딩 여부 반환
    """
    loaded = asv_model is not None
    return HealthResponse(
        status="ok" if loaded else "error",
        model_loaded=loaded,
    )


@app.post("/enroll", response_model=EnrollResponse, tags=["speaker-verification"])
async def enroll(file: UploadFile) -> EnrollResponse:
    """오디오 파일에서 192차원 화자 임베딩 벡터를 추출합니다.

    임베딩은 메인 백엔드가 수신 후 users.embedding_vector에 저장합니다.
    이 서버는 계산만 수행하며 어떤 데이터도 저장하지 않습니다.

    Args:
        file: WAV 형식의 오디오 파일 (multipart/form-data). 16kHz 권장.

    Returns:
        EnrollResponse: 192차원 float 배열.

    Raises:
        HTTPException(400): 오디오 디코딩 실패.
        HTTPException(500): 모델 추론 실패.
        HTTPException(503): 모델 미로딩.

    # Plan SC: FR-01 — POST /enroll: 오디오 → 192차원 float 배열 반환
    """
    model = _require_model()
    audio_bytes = await file.read()

    try:
        embedding = model.extract_embedding(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EnrollResponse(embedding=embedding)


@app.post("/verify", response_model=VerifyResponse, tags=["speaker-verification"])
async def verify(
    file: UploadFile,
    reference_embedding: str = Form(...),
) -> VerifyResponse:
    """오디오와 참조 임베딩을 비교해 동일 화자 여부를 판별합니다.

    참조 임베딩은 메인 백엔드가 DB(users.embedding_vector)에서 조회해 전달합니다.

    Args:
        file: WAV 형식의 오디오 파일 (multipart/form-data).
        reference_embedding: JSON 문자열로 직렬화된 192차원 참조 임베딩.
            메인 백엔드 호출 예시::

                httpx.post(
                    url,
                    files={"file": ("a.wav", wav_bytes, "audio/wav")},
                    data={"reference_embedding": json.dumps(emb_list)},
                )

    Returns:
        VerifyResponse: is_same_speaker + similarity_score.

    Raises:
        HTTPException(400): 임베딩 차원 오류 / JSON 파싱 실패 / 오디오 오류.
        HTTPException(500): 모델 추론 실패.
        HTTPException(503): 모델 미로딩.

    # Plan SC: FR-02 — POST /verify: 오디오+참조임베딩 → {is_same_speaker, similarity_score}
    # Plan SC: FR-03 — 코사인 유사도 >= ASV_THRESHOLD → is_same_speaker=True
    # Design Ref: §10.2 — Form(json.loads) 패턴: multipart+JSON 동시 수신
    """
    model = _require_model()

    # reference_embedding JSON 파싱 및 차원 검증
    try:
        ref_emb: list[float] = json.loads(reference_embedding)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="reference_embedding must be a valid JSON array of floats",
        ) from exc

    if len(ref_emb) != 192:
        raise HTTPException(
            status_code=400,
            detail=(
                f"reference_embedding must have 192 dimensions, "
                f"got {len(ref_emb)}"
            ),
        )

    # 오디오에서 현재 임베딩 추출
    audio_bytes = await file.read()

    try:
        current_emb = model.extract_embedding(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 코사인 유사도 계산 및 임계값 비교
    similarity = model.cosine_similarity(current_emb, ref_emb)
    is_same = similarity >= settings.asv_threshold

    return VerifyResponse(
        is_same_speaker=is_same,
        similarity_score=round(similarity, 6),
    )
