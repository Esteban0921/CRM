import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.supplier import Supplier
from models.user import User, UserRole
from schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
def list_suppliers(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.name.asc()).all()


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Supplier:
    email = payload.email.lower() if payload.email else None
    supplier = Supplier(
        name=payload.name.strip(),
        tax_id=payload.tax_id,
        email=email,
        category=payload.category,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"] is not None:
        changes["email"] = changes["email"].lower()
    if "name" in changes and isinstance(changes["name"], str):
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier
