import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db import get_db
from models.user import User, UserRole
from security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise credentials_error from exc

    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado para este recurso")
        return user

    return dependency


def ensure_family_access(user: User, family_id: uuid.UUID | None) -> None:
    """Invariante RULE-005: un padre solo accede a datos de su propia familia.

    404 en vez de 403 para no confirmar la existencia de otras familias.
    Un recurso sin `family_id` (factura aún sin enlazar) nunca es del padre.
    """
    if user.role == UserRole.PARENT and (family_id is None or user.family_id != family_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")
