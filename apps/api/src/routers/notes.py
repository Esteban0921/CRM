import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.note import Note, NoteEntityType
from models.user import User, UserRole
from schemas.note import NoteCreate, NoteRead

# Solo staff/admin: notas internas de trabajo, nunca visibles para un padre.
router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Note:
    note = Note(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        body=payload.body,
        created_by=staff.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=list[NoteRead])
def list_notes(
    entity_type: NoteEntityType = Query(...),
    entity_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Note]:
    return (
        db.query(Note)
        .filter(Note.entity_type == entity_type, Note.entity_id == entity_id)
        .order_by(Note.created_at.desc())
        .all()
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> None:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nota no encontrada")
    db.delete(note)
    db.commit()
