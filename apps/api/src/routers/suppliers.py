from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.supplier import Supplier
from models.user import User, UserRole
from schemas.supplier import SupplierRead

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
def list_suppliers(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.name.asc()).all()
