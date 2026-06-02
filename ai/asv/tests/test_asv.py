"""ASV 서버 pytest 단위 테스트 — 실제 CAM++ 모델 사용.

모든 테스트는 실제 CAM++ 모델을 로딩하여 실행합니다.
torchaudio, modelscope, torch가 설치된 환경과 모델 캐시가 필요합니다.

# Design Ref: §8 — Test Plan, L1 단위 테스트 8개 시나리오
"""

import json
import struct
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from model import ASVModel


# ── 공통 상수 ────────────────────────────────────────────────────────────────

EMBEDDING_DIM: int = 192
"""CAM++ 모델 출력 임베딩 차원."""

THRESHOLD: float = 0.75
"""동일 화자 판별 임계값 (config.py ASV_THRESHOLD 기본값)."""


# ── 픽스처 ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def real_model() -> ASVModel:
    """실제 ASVModel 인스턴스 (모듈 스코프 — 모델 로딩은 1회만).

    Returns:
        ASVModel: CAM++ 모델이 로딩된 실제 인스턴스.
    """
    return ASVModel()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """FastAPI TestClient — 실제 lifespan으로 모델 로딩.

    모델 로딩이 1회만 발생하도록 모듈 스코프를 사용합니다.

    Yields:
        TestClient: 실제 모델이 로딩된 테스트용 HTTP 클라이언트.
    """
    from main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def wav_bytes() -> bytes:
    """유효한 16kHz 모노 WAV 파일 바이트 (1초, 무음).

    결정적(deterministic) 데이터이므로 모듈 스코프로 1회만 생성합니다.

    Returns:
        WAV 헤더 + PCM 데이터 바이트.
    """
    sample_rate = 16000
    num_samples = sample_rate  # 1초
    pcm_data = b"\x00\x00" * num_samples  # 16-bit 무음

    # RIFF WAV 헤더 생성
    data_size = len(pcm_data)
    header = struct.pack("<4sI4s", b"RIFF", 36 + data_size, b"WAVE")
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ",
        16,  # chunk size
        1,  # PCM format
        1,  # 모노
        sample_rate,
        sample_rate * 2,  # byte rate
        2,  # block align
        16,  # bits per sample
    )
    data_chunk = struct.pack("<4sI", b"data", data_size) + pcm_data
    return header + fmt_chunk + data_chunk


# ── TestExtractEmbedding ─────────────────────────────────────────────────────


class TestExtractEmbedding:
    """ASVModel.extract_embedding 실제 모델 동작 검증."""

    def test_returns_list_of_192_floats(
        self, real_model: ASVModel, wav_bytes: bytes
    ) -> None:
        """실제 CAM++ 모델이 192차원 float 리스트를 반환한다.

        # Design Ref: §8.2 시나리오 #1
        """
        result = real_model.extract_embedding(wav_bytes)

        assert isinstance(result, list), "반환값이 list여야 합니다"
        assert len(result) == EMBEDDING_DIM, (
            f"192차원이어야 합니다. 실제: {len(result)}"
        )
        assert all(isinstance(v, float) for v in result), (
            "모든 원소가 float이어야 합니다"
        )


# ── TestCosineSimilarity ─────────────────────────────────────────────────────


class TestCosineSimilarity:
    """ASVModel.cosine_similarity 수학적 검증 (staticmethod — 모델 불필요)."""

    def test_identical_vectors_return_one(self) -> None:
        """동일 벡터의 코사인 유사도는 1.0이다.

        # Design Ref: §8.2 시나리오 #2
        """
        v = [1.0] + [0.0] * 191
        result = ASVModel.cosine_similarity(v, v)
        assert abs(result - 1.0) < 1e-6, f"1.0 이어야 합니다. 실제: {result}"

    def test_opposite_vectors_return_minus_one(self) -> None:
        """반대 방향 벡터의 코사인 유사도는 -1.0이다.

        # Design Ref: §8.2 시나리오 #3
        """
        v1 = [1.0] + [0.0] * 191
        v2 = [-1.0] + [0.0] * 191
        result = ASVModel.cosine_similarity(v1, v2)
        assert abs(result - (-1.0)) < 1e-6, f"-1.0 이어야 합니다. 실제: {result}"

    def test_zero_vector_returns_zero(self) -> None:
        """영 벡터가 포함된 경우 0.0을 반환한다."""
        zero = [0.0] * 192
        unit = [1.0] + [0.0] * 191
        assert ASVModel.cosine_similarity(zero, unit) == 0.0
        assert ASVModel.cosine_similarity(unit, zero) == 0.0


# ── TestHealthEndpoint ───────────────────────────────────────────────────────


class TestHealthEndpoint:
    """GET /health 엔드포인트 테스트.

    # Design Ref: §4.1 — GET /health 응답 스키마
    """

    def test_health_returns_ok_when_model_loaded(self, client: TestClient) -> None:
        """실제 모델이 로딩된 경우 status=ok, model_loaded=True를 반환한다.

        # Design Ref: §8.2 시나리오 #7
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True


# ── TestEnrollEndpoint ───────────────────────────────────────────────────────


class TestEnrollEndpoint:
    """POST /enroll 엔드포인트 테스트.

    # Design Ref: §4.2 — POST /enroll 요청/응답 스키마
    """

    def test_enroll_returns_192_dimension_embedding(
        self,
        client: TestClient,
        wav_bytes: bytes,
    ) -> None:
        """실제 CAM++ 모델이 192차원 임베딩을 반환한다.

        # Design Ref: §8.2 시나리오 #4
        """
        response = client.post(
            "/enroll",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data, "응답에 'embedding' 키가 있어야 합니다"
        assert len(data["embedding"]) == EMBEDDING_DIM, (
            f"192차원이어야 합니다. 실제: {len(data['embedding'])}"
        )

    def test_enroll_returns_503_when_model_not_loaded(
        self,
        client: TestClient,
        wav_bytes: bytes,
    ) -> None:
        """모델 미로딩 시 503을 반환한다."""
        with patch("main.asv_model", None):
            response = client.post(
                "/enroll",
                files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
            )

        assert response.status_code == 503


# ── TestVerifyEndpoint ───────────────────────────────────────────────────────


class TestVerifyEndpoint:
    """POST /verify 엔드포인트 테스트.

    # Design Ref: §4.3 — POST /verify 요청/응답 스키마
    """

    def test_verify_returns_true_for_same_speaker(
        self,
        client: TestClient,
        wav_bytes: bytes,
    ) -> None:
        """동일 오디오로 enroll 후 verify → is_same_speaker=True.

        동일 오디오에서 추출한 임베딩끼리의 코사인 유사도 = 1.0.
        임계값(0.75) 이상이므로 is_same_speaker=True가 보장됩니다.

        # Design Ref: §8.2 시나리오 #5
        """
        # 1. enroll로 참조 임베딩 추출
        enroll_resp = client.post(
            "/enroll",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
        )
        assert enroll_resp.status_code == 200
        reference_embedding: list[float] = enroll_resp.json()["embedding"]

        # 2. 동일 오디오로 verify
        verify_resp = client.post(
            "/verify",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
            data={"reference_embedding": json.dumps(reference_embedding)},
        )

        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["is_same_speaker"] is True, (
            f"동일 오디오는 is_same_speaker=True여야 합니다. "
            f"similarity_score={data['similarity_score']:.4f}"
        )
        assert 0.0 <= data["similarity_score"] <= 1.0

    def test_verify_returns_false_for_different_speaker(
        self,
        client: TestClient,
        wav_bytes: bytes,
    ) -> None:
        """실제 임베딩의 반대 방향 벡터를 참조로 사용 → is_same_speaker=False.

        반대 방향 벡터와의 코사인 유사도 ≈ -1.0.
        임계값(0.75) 미만이므로 is_same_speaker=False가 수학적으로 보장됩니다.

        # Design Ref: §8.2 시나리오 #6
        """
        # 1. enroll로 실제 임베딩 추출
        enroll_resp = client.post(
            "/enroll",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
        )
        assert enroll_resp.status_code == 200
        actual_embedding: list[float] = enroll_resp.json()["embedding"]

        # 2. 반대 방향 벡터를 참조 임베딩으로 사용 (코사인 유사도 ≈ -1.0)
        opposite_reference = [-v for v in actual_embedding]

        verify_resp = client.post(
            "/verify",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
            data={"reference_embedding": json.dumps(opposite_reference)},
        )

        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["is_same_speaker"] is False, (
            f"반대 방향 임베딩은 is_same_speaker=False여야 합니다. "
            f"similarity_score={data['similarity_score']:.4f}"
        )

    def test_verify_returns_400_for_invalid_embedding_dimension(
        self,
        client: TestClient,
        wav_bytes: bytes,
    ) -> None:
        """192차원이 아닌 임베딩은 400을 반환한다.

        # Design Ref: §8.2 시나리오 #8
        """
        response = client.post(
            "/verify",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
            data={"reference_embedding": json.dumps([0.1] * 10)},  # 10차원 (잘못됨)
        )

        assert response.status_code == 400
        assert "192" in response.json()["detail"]

    def test_verify_returns_400_for_invalid_json(
        self,
        client: TestClient,
        wav_bytes: bytes,
    ) -> None:
        """JSON이 아닌 reference_embedding은 400을 반환한다."""
        response = client.post(
            "/verify",
            files={"file": ("test.wav", BytesIO(wav_bytes), "audio/wav")},
            data={"reference_embedding": "not_valid_json"},
        )

        assert response.status_code == 400
