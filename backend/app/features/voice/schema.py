from pydantic import BaseModel, Field


class VoiceRegistrationRequest(BaseModel):
    """음성 등록 테스트를 위한 임시 요청 스키마"""

    embedding_vector: list[float] = Field(
        ...,
        min_length=192,
        max_length=192,
        description="음성 추출 모델에서 반환된 192차원 벡터 데이터",
    )
