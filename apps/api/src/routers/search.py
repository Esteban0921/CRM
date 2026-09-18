from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.family import Family
from models.family_invoice import FamilyInvoice
from models.student import Student
from models.supplier import Supplier
from models.user import User, UserRole
from schemas.search import SearchHit, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])

_PER_TYPE = 8


def _like(query: str) -> str:
    cleaned = "".join(ch for ch in query.strip() if ch not in "%_")
    return f"%{cleaned}%"


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(min_length=2, max_length=80),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> SearchResponse:
    """TASK-0054. Solo staff: el padre no recorre el censo de menores (RULE-015)."""
    pattern = _like(q)
    if pattern == "%%":
        return SearchResponse(hits=[])

    hits: list[SearchHit] = []

    families = (
        db.query(Family)
        .filter(Family.name.ilike(pattern))
        .order_by(Family.name)
        .limit(_PER_TYPE)
        .all()
    )
    for family in families:
        hits.append(
            SearchHit(
                type="family",
                id=family.id,
                title=family.name,
                subtitle=family.address,
                family_id=family.id,
            )
        )

    students = (
        db.query(Student)
        .filter(Student.name.ilike(pattern) | Student.school.ilike(pattern))
        .order_by(Student.name)
        .limit(_PER_TYPE)
        .all()
    )
    for student in students:
        hits.append(
            SearchHit(
                type="student",
                id=student.id,
                title=student.name,
                subtitle=student.school,
                family_id=student.family_id,
            )
        )

    invoices = (
        db.query(FamilyInvoice, Family.name)
        .outerjoin(Family, Family.id == FamilyInvoice.family_id)
        .filter(
            or_(
                Family.name.ilike(pattern),
                cast(FamilyInvoice.amount, String).ilike(pattern),
            )
        )
        .order_by(FamilyInvoice.issue_date.desc().nullslast())
        .limit(_PER_TYPE)
        .all()
    )
    for invoice, family_name in invoices:
        amount = (
            f"{invoice.amount} {invoice.currency}" if invoice.amount is not None else "sin importe"
        )
        hits.append(
            SearchHit(
                type="family_invoice",
                id=invoice.id,
                title=f"Factura {amount}",
                subtitle=family_name or "Sin asignar",
                family_id=invoice.family_id,
            )
        )

    suppliers = (
        db.query(Supplier)
        .filter(Supplier.name.ilike(pattern) | Supplier.email.ilike(pattern))
        .order_by(Supplier.name)
        .limit(_PER_TYPE)
        .all()
    )
    for supplier in suppliers:
        hits.append(
            SearchHit(type="supplier", id=supplier.id, title=supplier.name, subtitle=supplier.email)
        )

    return SearchResponse(hits=hits)
