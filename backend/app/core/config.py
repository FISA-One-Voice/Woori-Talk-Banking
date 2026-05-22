from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./woori_talk.db"  # 기본값은 SQLite로
    ENV: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()