from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from dependencies import get_current_user
from models.user import User
from schemas.auth import LoginRequest, TokenResponse
from schemas.user import MeResponse
from security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contrasena incorrectos")

    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return TokenResponse(access_token=token)
