from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from dependencies import require_role
from models.document import Document
from models.email import Email, EmailProcessingStatus
from models.user import User, UserRole
from schemas.email import EmailRead

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("", response_model=list[EmailRead])
def list_emails(
    processing_status: EmailProcessingStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[EmailRead]:
    query = db.query(Email)
    if processing_status is not None:
        query = query.filter(Email.processing_status == processing_status)
    emails = query.order_by(Email.created_at.desc()).limit(100).all()
    doc_counts = dict(
        db.query(Document.email_id, func.count(Document.id)).group_by(Document.email_id).all()
    )
    return [
        EmailRead.model_validate(email).model_copy(
            update={"document_count": int(doc_counts.get(email.id, 0))}
        )
        for email in emails
    ]
