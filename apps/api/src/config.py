from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_port: int = 8000
    cors_origin: str = "http://localhost:3000"


settings = Settings()
