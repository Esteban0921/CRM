import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from audit import record_field_changes
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from models.audit_log import AuditedEntityType
from models.student import Student
from models.user import User, UserRole
from schemas.student import StudentCreate, StudentRead, StudentUpdate

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Student:
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("", response_model=list[StudentRead])
def list_students(
    family_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Student]:
    # RULE-005: un padre nunca decide por que family_id filtra, se le impone.
    if user.role == UserRole.PARENT:
        if user.family_id is None:
            return []
        family_id = user.family_id

    query = db.query(Student)
    if family_id is not None:
        query = query.filter(Student.family_id == family_id)
    return query.order_by(Student.name).all()


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alumno no encontrado")
    ensure_family_access(user, student.family_id)
    return student


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alumno no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(student, field) for field in changes}
    for field, value in changes.items():
        setattr(student, field, value)
    record_field_changes(
        db,
        entity_type=AuditedEntityType.STUDENT,
        entity_id=student.id,
        editor_id=staff.id,
        before=before,
        after=changes,
    )
    db.commit()
    db.refresh(student)
    return student
