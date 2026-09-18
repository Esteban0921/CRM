import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.family import Family
from models.user import User, UserRole
from schemas.user import UserCreate, UserRead
from security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> User:
    if payload.role == UserRole.ADMIN and actor.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo un admin puede crear otro admin")
    if payload.role == UserRole.PARENT and payload.family_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "family_id es obligatorio para role=parent"
        )
    if payload.family_id is not None and db.get(Family, payload.family_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "family_id no encontrado")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        family_id=payload.family_id if payload.role == UserRole.PARENT else None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese email ya esta registrado") from exc
    db.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    family_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[User]:
    query = db.query(User)
    if family_id is not None:
        query = query.filter(User.family_id == family_id)
    return query.order_by(User.name).all()
