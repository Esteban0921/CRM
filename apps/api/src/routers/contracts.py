import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.contract import Contract
from models.student import Student
from models.user import User, UserRole
from schemas.contract import ContractCreate, ContractRead, ContractUpdate

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _get_student_or_404(db: Session, student_id: uuid.UUID) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alumno no encontrado")
    return student


@router.post("", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Contract:
    _get_student_or_404(db, payload.student_id)
    contract = Contract(**payload.model_dump())
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@router.get("", response_model=list[ContractRead])
def list_contracts(
    student_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Contract]:
    query = db.query(Contract)
    if user.role == UserRole.PARENT:
        if user.family_id is None:
            return []
        query = query.join(Student).filter(Student.family_id == user.family_id)
        if student_id is not None:
            query = query.filter(Contract.student_id == student_id)
    else:
        if student_id is not None:
            query = query.filter(Contract.student_id == student_id)
    return query.order_by(Contract.start_date.desc()).all()


@router.get("/{contract_id}", response_model=ContractRead)
def get_contract(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrato no encontrado")
    student = _get_student_or_404(db, contract.student_id)
    ensure_family_access(user, student.family_id)
    return contract


@router.patch("/{contract_id}", response_model=ContractRead)
def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrato no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)
    db.commit()
    db.refresh(contract)
    return contract
