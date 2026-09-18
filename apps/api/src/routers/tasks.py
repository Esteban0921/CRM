import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.family import Family
from models.task import Task, TaskStatus
from models.user import User, UserRole
from schemas.task import TaskCreate, TaskRead, TaskUpdate

# Solo staff/admin: seguimiento interno, nunca visible para un padre.
router = APIRouter(prefix="/tasks", tags=["tasks"])


def _with_family_names(db: Session, tasks: list[Task]) -> list[TaskRead]:
    family_ids = {task.family_id for task in tasks}
    names = (
        dict(db.query(Family.id, Family.name).filter(Family.id.in_(family_ids)).all())
        if family_ids
        else {}
    )
    return [
        TaskRead.model_validate(task).model_copy(update={"family_name": names.get(task.family_id)})
        for task in tasks
    ]


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> TaskRead:
    if payload.family_id is not None and db.get(Family, payload.family_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Familia no encontrada")
    task = Task(**payload.model_dump(), created_by=staff.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return _with_family_names(db, [task])[0]


@router.get("", response_model=list[TaskRead])
def list_tasks(
    family_id: uuid.UUID | None = Query(default=None),
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[TaskRead]:
    query = db.query(Task)
    if family_id is not None:
        query = query.filter(Task.family_id == family_id)
    if task_status is not None:
        query = query.filter(Task.status == task_status)
    tasks = query.order_by(Task.due_date.asc().nullslast()).all()
    return _with_family_names(db, tasks)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> TaskRead:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarea no encontrada")
    return _with_family_names(db, [task])[0]


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> TaskRead:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarea no encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return _with_family_names(db, [task])[0]
