from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./woori_talk.db"
    ENV: str = "development"

    # NAVER CLOVA Speech (STT)
    CLOVA_SECRET_KEY: str = ""
    CLOVA_URL: str = "https://clovaspeech-gw.ncloud.com/recog/v1/stt?lang=Kor"

    # Azure Cognitive Services Text-to-Speech (TTS)
    AZURE_TTS_KEY: str = ""
    AZURE_TTS_REGION: str = "koreacentral"

    class Config:
        env_file = "../.env"
        extra = "ignore"


settings = Settings()
