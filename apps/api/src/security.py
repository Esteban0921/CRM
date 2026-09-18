import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from config import settings

MAX_LIFETIME_LEEWAY = timedelta(minutes=5)

# Hash de una contrasena que nadie usa. Sirve para gastar el mismo tiempo de
# bcrypt cuando el email no existe: sin esto, el login responde en 18 ms si el
# usuario no existe y en 327 ms si existe, que es un oraculo de enumeracion
# perfecto (TASK-0094).
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def burn_password_check(password: str) -> None:
    """Verifica contra un hash de descarte. Se llama cuando el email no existe
    para que el tiempo de respuesta no revele si la cuenta esta dada de alta.
    """
    bcrypt.checkpw(password.encode("utf-8"), _DUMMY_PASSWORD_HASH.encode("utf-8"))


def create_access_token(*, user_id: uuid.UUID, role: str, family_id: uuid.UUID | None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "family_id": str(family_id) if family_id else None,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Exige `exp`, `iat` y `sub`: sin `require`, PyJWT acepta un token sin
    claim de caducidad, y entonces la expiracion de `jwt_expires_minutes` es
    voluntaria para quien forje el token (TASK-0088).
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        options={"require": ["exp", "iat", "sub"]},
    )
    _reject_overlong_lifetime(payload)
    return payload


def _reject_overlong_lifetime(payload: dict[str, Any]) -> None:
    """Un `exp` valido pero lejanisimo (ano 2100) pasa la verificacion normal y
    es una sesion eterna de facto. El token nunca puede durar mas de lo que la
    propia API emite, con un margen de holgura.
    """
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    if not isinstance(issued_at, (int, float)) or not isinstance(expires_at, (int, float)):
        raise jwt.InvalidTokenError("Token sin marcas de tiempo utilizables")
    max_lifetime = timedelta(minutes=settings.jwt_expires_minutes) + MAX_LIFETIME_LEEWAY
    if expires_at - issued_at > max_lifetime.total_seconds():
        raise jwt.InvalidTokenError("Token con una vigencia mayor que la que emite esta API")
