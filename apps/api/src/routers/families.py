import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.family import Family
from models.user import User, UserRole
from schemas.family import FamilyCreate, FamilyRead, FamilyUpdate

router = APIRouter(prefix="/families", tags=["families"])


@router.post("", response_model=FamilyRead, status_code=status.HTTP_201_CREATED)
def create_family(
    payload: FamilyCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Family:
    family = Family(**payload.model_dump())
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@router.get("", response_model=list[FamilyRead])
def list_families(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Family]:
    return db.query(Family).order_by(Family.name).all()


@router.get("/{family_id}", response_model=FamilyRead)
def get_family(
    family_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Family:
    ensure_family_access(user, family_id)
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")
    return family


@router.patch("/{family_id}", response_model=FamilyRead)
def update_family(
    family_id: uuid.UUID,
    payload: FamilyUpdate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Family:
    family = db.get(Family, family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(family, field, value)
    db.commit()
    db.refresh(family)
    return family
