"""CAM++ 화자 인증 모델 래퍼 모듈.

# Design Ref: §3.2 — ASVModel, modelscope 파이프라인 래퍼, Stateless 설계
"""

import io
import os
import tempfile

import numpy as np
import soundfile as sf
import torch
import torchaudio
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

from config import settings

_SAMPLE_RATE: int = 16000
"""CAM++ 모델 요구 샘플레이트 (Hz)."""

_EMBEDDING_DIM: int = 192
"""CAM++ 모델 출력 임베딩 차원 (고정값)."""


class ASVModel:
    """CAM++ 화자 인증 모델 래퍼.

    modelscope의 speaker-verification 파이프라인을 감싸
    바이트 수준 인터페이스를 제공합니다.

    임베딩 추출과 유사도 계산만 담당하며 어떤 상태도 영속하지 않습니다.

    # Design Ref: §2.0 Option C — Stateless, model.py 책임 분리
    """

    def __init__(self) -> None:
        """CAM++ 모델을 로딩합니다.

        Raises:
            RuntimeError: 모델 로딩 실패 시. 서버 시작을 차단합니다.
        """
        try:
            self._pipeline = pipeline(
                task=Tasks.speaker_verification,
                model=settings.model_name,
                model_revision="v1.0.0",
                model_cache_dir=settings.model_cache_dir,
            )
        except Exception as exc:
            raise RuntimeError(f"ASV 모델 로딩 실패: {exc}") from exc

    def extract_embedding(self, audio_bytes: bytes) -> list[float]:
        """WAV 오디오 바이트에서 192차원 임베딩 벡터를 추출합니다.

        오디오를 16kHz 모노로 정규화한 뒤 CAM++ 모델에 입력합니다.
        임시 파일을 생성하고 추론 후 즉시 삭제합니다.

        오디오 I/O는 soundfile을 사용합니다. torchaudio 2.9+는 TorchCodec 백엔드를
        요구하므로 별도 의존성 없이 동작하는 soundfile로 대체합니다.
        리샘플링에는 torchaudio.transforms.Resample을 사용합니다 (torchcodec 불필요).

        Args:
            audio_bytes: WAV 형식의 원시 바이트. 16kHz 권장.

        Returns:
            192개의 float로 구성된 화자 임베딩 벡터.

        Raises:
            ValueError: 오디오 디코딩 또는 전처리 실패.
            RuntimeError: 모델 추론 실패.

        # Plan SC: FR-01 — 오디오 파일 수신 → 192차원 임베딩 반환
        """
        tmp_path: str = ""
        try:
            # 1. 오디오 바이트 디코딩 (soundfile — torchcodec 불필요)
            try:
                audio_data, sample_rate = sf.read(
                    io.BytesIO(audio_bytes),
                    dtype="float32",
                    always_2d=True,  # 항상 [time, channels] 형태
                )
            except Exception as exc:
                raise ValueError(f"오디오 디코딩 실패: {exc}") from exc

            # 2. [time, channels] → [channels, time] 텐서 변환
            waveform = torch.from_numpy(audio_data.T)  # shape: [C, T]

            # 3. 스테레오 → 모노 변환
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)

            # 4. 16kHz 리샘플링 (torchaudio.transforms.Resample은 torchcodec 불필요)
            if sample_rate != _SAMPLE_RATE:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate,
                    new_freq=_SAMPLE_RATE,
                )
                waveform = resampler(waveform)

            # 5. 전처리된 오디오를 임시 파일에 저장 (파이프라인은 파일 경로 입력)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            sf.write(
                tmp_path,
                waveform.numpy().T,  # [C, T] → [T, C] (soundfile 입력 형식)
                _SAMPLE_RATE,
            )

            # 6. 파이프라인 실행 (in_audios는 list[str] — 문자열 자체는 문자 순회됨)
            try:
                result = self._pipeline([tmp_path], output_emb=True)
            except Exception as exc:
                raise RuntimeError(f"모델 추론 실패: {exc}") from exc

            # 7. 임베딩 추출: output_emb=True 시 {"embs": ndarray[N, 192], "outputs": ...}
            if isinstance(result, dict) and "embs" in result:
                embedding: list[float] = (
                    np.array(result["embs"]).flatten().tolist()
                )
            elif isinstance(result, dict) and "spk_embedding" in result:
                # 일부 버전 호환성 유지
                embedding = np.array(result["spk_embedding"]).flatten().tolist()
            elif hasattr(result, "tolist"):
                embedding = result.flatten().tolist()
            else:
                raise RuntimeError(
                    f"모델 출력에서 임베딩을 찾을 수 없습니다. 출력 형식: {type(result)}, "
                    f"키: {list(result.keys()) if isinstance(result, dict) else 'N/A'}"
                )

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return embedding

    @staticmethod
    def cosine_similarity(
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """두 임베딩 벡터 간 코사인 유사도를 계산합니다.

        Args:
            embedding1: 첫 번째 화자 임베딩 벡터.
            embedding2: 두 번째 화자 임베딩 벡터.

        Returns:
            0.0 ~ 1.0 사이의 float. 1.0에 가까울수록 동일 화자.
            영 벡터가 입력되면 0.0을 반환합니다.

        # Plan SC: FR-03 — 코사인 유사도 >= ASV_THRESHOLD → is_same_speaker=True
        """
        a = np.array(embedding1, dtype=np.float32)
        b = np.array(embedding2, dtype=np.float32)

        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))
