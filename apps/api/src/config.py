from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Literal historico que quedo publicado en el repositorio. Cualquier despliegue
# que siga firmando con el es falsificable por quien haya leido el codigo, asi
# que en `production` el arranque se aborta (TASK-0088).
DEV_JWT_SECRET = "dev-secret-change-me-in-every-real-environment"

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_port: int = 8000
    # `cors_origin` (singular) se mantiene porque hay `.env` que ya lo definen;
    # lo que se lee en la app es `cors_origin_list`, que fusiona ambos.
    cors_origin: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Servicios de docker-compose.yml por 127.0.0.1, no por `localhost`: este
    # resuelve primero a ::1, donde Docker no publica nada (TASK-0089), y cada
    # conexion nueva espera el timeout de IPv6 antes de probar IPv4 (TASK-0181).
    database_url: str = "postgresql+psycopg://crm:crm@127.0.0.1:5432/crm_transporte"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expires_minutes: int = 15
    login_max_attempts: int = 10
    login_attempt_window_seconds: int = 300
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@crm-transporte.local"
    clamav_host: str = "127.0.0.1"
    clamav_port: int = 3310
    attachments_dir: str = "./data/attachments"
    max_attachment_bytes: int = 10 * 1024 * 1024
    max_attachments_per_email: int = 20
    max_extraction_text_bytes: int = 256 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        """Varios origenes permitidos: sin esto no se puede abrir la web por
        `127.0.0.1:3000` ni por la IP de la LAN para probar la vista del padre
        en un movil real (TASK-0141).
        """
        raw = f"{self.cors_origins},{self.cors_origin}"
        seen: list[str] = []
        for origin in raw.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return seen

    @model_validator(mode="after")
    def _reject_weak_jwt_secret_in_production(self) -> "Settings":
        if not self.is_production:
            return self
        if self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET sigue siendo el valor de desarrollo publicado en el repositorio. "
                "Genera uno nuevo antes de arrancar con APP_ENV=production."
            )
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET debe tener al menos {MIN_JWT_SECRET_LENGTH} caracteres "
                f"(tiene {len(self.jwt_secret)})."
            )
        return self


settings = Settings()

if not settings.is_production and settings.jwt_secret == DEV_JWT_SECRET:
    # No es un log de aplicacion: es el aviso de que esta instancia firma con un
    # secreto que cualquiera puede leer en el repositorio.
    print(
        "\n  AVISO: JWT_SECRET no esta definido y se usa el valor de desarrollo.\n"
        "  Cualquiera que lea el repositorio puede forjar un token de staff.\n"
        "  Define JWT_SECRET en apps/api/.env antes de exponer esta API.\n",
        flush=True,
    )
