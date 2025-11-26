from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEFAULT_CHANNEL: str = "music-player"
    IDLE_TIMEOUT: int = 60 * 3


configs = Settings()
