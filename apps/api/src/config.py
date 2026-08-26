from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_port: int = 8000
    cors_origin: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://crm:crm@localhost:5432/crm_transporte"
    jwt_secret: str = "dev-secret-change-me-in-every-real-environment"
    jwt_expires_minutes: int = 15
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@crm-transporte.local"
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    attachments_dir: str = "./data/attachments"


settings = Settings()
