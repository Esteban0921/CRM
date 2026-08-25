from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_port: int = 8000
    cors_origin: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://crm:crm@localhost:5432/crm_transporte"
    jwt_secret: str = "dev-secret-change-me-in-every-real-environment"
    jwt_expires_minutes: int = 15


settings = Settings()
