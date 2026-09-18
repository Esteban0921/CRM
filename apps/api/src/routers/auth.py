from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from dependencies import get_current_user
from models.user import User
from rate_limit import LoginRateLimiter
from schemas.auth import LoginRequest, TokenResponse
from schemas.user import MeResponse
from security import burn_password_check, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = LoginRateLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_attempt_window_seconds,
)


@router.get("/me", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


def _attempt_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "desconocido"
    return f"{client_host}|{email}"


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower()
    key = _attempt_key(request, email)

    retry_after = login_limiter.retry_after_seconds(key)
    if retry_after:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiados intentos fallidos. Prueba de nuevo en unos minutos.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        # Gastar el mismo tiempo que una verificacion real: sin esto la
        # diferencia de latencia dice si el email esta dado de alta.
        burn_password_check(payload.password)
        login_limiter.register_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contrasena incorrectos")

    if not verify_password(payload.password, user.password_hash):
        login_limiter.register_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contrasena incorrectos")

    login_limiter.reset(key)
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return TokenResponse(access_token=token)
