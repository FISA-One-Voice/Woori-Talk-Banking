import httpx
import tempfile
import subprocess
import os
from sqlalchemy.orm import Session
from app.core.exception import AppError, VoiceServiceError
from app.core.config import settings
from app.models.user import User


def convert_to_wav_with_ffmpeg(audio_bytes: bytes) -> bytes:
    """오디오 바이트 데이터를 16-bit PCM WAV 포맷으로 변환하여 반환합니다.

    Args:
        audio_bytes: 변환할 원본 오디오 파일의 바이너리 데이터.

    Returns:
        변환된 WAV 파일의 바이너리 데이터.

    Raises:
        VoiceServiceError: ffmpeg 변환 프로세스 중 오류가 발생한 경우.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as temp_in:
        temp_in.write(audio_bytes)
        temp_in_path = temp_in.name

    temp_out_path = temp_in_path + ".wav"
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            temp_in_path,
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            temp_out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)

        with open(temp_out_path, "rb") as f:
            wav_bytes = f.read()
        return wav_bytes
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode("utf-8", errors="ignore")
        raise VoiceServiceError(
            code="VOICE_AUDIO_INVALID_FORMAT",
            message=f"오디오 변환 실패(ffmpeg): {error_msg}",
            status_code=500,
            user_message="음성 파일 처리 중 오류가 발생했습니다.",
        )
    except Exception as e:
        raise VoiceServiceError(
            code="VOICE_AUDIO_INVALID_FORMAT",
            message=f"알 수 없는 오디오 변환 오류: {str(e)}",
            status_code=500,
            user_message="음성 파일 처리 중 오류가 발생했습니다.",
        )
    finally:
        if os.path.exists(temp_in_path):
            os.remove(temp_in_path)
        if os.path.exists(temp_out_path):
            os.remove(temp_out_path)


def merge_and_convert_with_ffmpeg(audio_bytes_list: list[bytes]) -> bytes:
    """여러 개의 오디오 바이트 데이터를 하나로 병합한 뒤 16-bit PCM WAV로 변환합니다.

    Args:
        audio_bytes_list: 병합할 오디오 바이너리 데이터들의 리스트.

    Returns:
        병합 및 변환이 완료된 단일 WAV 파일의 바이너리 데이터.

    Raises:
        VoiceServiceError: ffmpeg 병합 및 변환 프로세스 중 오류가 발생한 경우.
    """
    temp_files = []
    list_file_path = None
    out_path = None
    try:
        for b in audio_bytes_list:
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
            tf.write(b)
            tf.close()
            temp_files.append(tf.name)

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w"
        ) as list_file:
            for tf_name in temp_files:
                list_file.write(f"file '{tf_name}'\n")
            list_file_path = list_file.name

        out_path = list_file_path + "_out.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file_path,
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)

        with open(out_path, "rb") as f:
            wav_bytes = f.read()
        return wav_bytes
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode("utf-8", errors="ignore")
        raise VoiceServiceError(
            code="VOICE_AUDIO_INVALID_FORMAT",
            message=f"오디오 병합 실패(ffmpeg): {error_msg}",
            status_code=500,
            user_message="음성 파일 처리 중 오류가 발생했습니다.",
        )
    finally:
        for tf_name in temp_files:
            if os.path.exists(tf_name):
                os.remove(tf_name)
        if list_file_path and os.path.exists(list_file_path):
            os.remove(list_file_path)
        if out_path and os.path.exists(out_path):
            os.remove(out_path)


async def extract_voice_vector(files_bytes: list[bytes]) -> list[float]:
    """여러 개의 오디오 파일을 병합하여 192차원 음성 임베딩 벡터를 추출합니다.

    Args:
        files_bytes: 프론트엔드에서 분할 전송된 오디오 파일들의 바이너리 데이터 리스트.

    Returns:
        ASV 서버가 추출한 192차원 실수(float) 배열.

    Raises:
        VoiceServiceError: 외부 ASV 서버 통신 실패, 내부 오디오 병합 실패,
                           또는 반환된 벡터가 192차원이 아닌 경우 발생.
    """
    merged_wav_bytes = merge_and_convert_with_ffmpeg(files_bytes)
    filename = "merged_voice.wav"
    content_type = "audio/wav"

    try:
        async with httpx.AsyncClient() as client:
            files = {"file": (filename, merged_wav_bytes, content_type)}
            response = await client.post(
                f"{settings.ASV_SERVER_URL}/enroll", files=files, timeout=60.0
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")

            if not embedding or len(embedding) != 192:
                raise VoiceServiceError(
                    code="VOICE_VECTOR_EXTRACT_FAILED",
                    message="ASV 서버에서 유효한 192차원 벡터를 반환하지 않았습니다.",
                    status_code=500,
                    user_message="화자 인증 중 오류가 발생했습니다.",
                )
            return embedding
    except httpx.HTTPStatusError as e:
        raise VoiceServiceError(
            code="VOICE_VECTOR_EXTRACT_FAILED",
            message=f"ASV 서버 오류 (상태 코드: {e.response.status_code})",
            status_code=502,
            user_message="화자 인증 중 오류가 발생했습니다.",
        )
    except VoiceServiceError:
        raise
    except Exception as e:
        raise VoiceServiceError(
            code="SERVICE_UNAVAILABLE",
            message=f"ASV 서버와 통신할 수 없습니다: {str(e)}",
            status_code=503,
            user_message="화자 인증 서버에 연결할 수 없습니다.",
        )


def register_voice_vector(db: Session, user_id: str, vector: list[float]) -> dict:
    """유저 정보에 맞게 192차원 음성 벡터를 DB에 저장합니다.

    Args:
        db: 데이터베이스 세션.
        user_id: 토큰에서 추출한 사용자 고유 ID.
        vector: 등록할 192차원의 실수 리스트.

    Returns:
        성공 여부 및 안내 메시지를 포함한 딕셔너리.

    Raises:
        AppError: 음성 벡터가 192차원이 아니거나(INVALID_REQUEST),
                  해당 유저를 찾을 수 없는 경우(USER_NOT_FOUND) 발생.
    """
    if len(vector) != 192:
        raise AppError(
            code="INVALID_REQUEST",
            message="음성 벡터는 정확히 192차원이어야 합니다.",
            status_code=400,
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise AppError(
            code="USER_NOT_FOUND", message="사용자를 찾을 수 없습니다.", status_code=404
        )

    # DB에 벡터 업데이트
    user.embedding_vector = vector
    db.commit()

    return {
        "success": True,
        "data": None,
        "message": "음성 벡터(192차원)가 사용자의 계정에 성공적으로 등록되었습니다.",
    }
